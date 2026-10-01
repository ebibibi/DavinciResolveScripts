#!/usr/bin/env bash
# Deterministic preprocessing for one recording. Everything editorial is left to the agent.
# Usage: prepare.sh <source video> <job dir>
set -euo pipefail
PROXY_PID=

SOURCE=$(realpath "$1")
JOB=$(realpath -m "$2")
FRAME_EVERY=${FRAME_EVERY:-10}
WHISPER_HOST=${WHISPER_HOST:-spark}
WHISPER_MODEL=${WHISPER_MODEL:-large-v3-turbo}

mkdir -p "$JOB"/{input,work,frames,sheets,out}
cd "$JOB"
ln -sfn "$SOURCE" input/source.mkv
log() { printf '[prepare %s] %s\n' "$(date +%H:%M:%S)" "$*"; }

log "probe"
ffprobe -v error -print_format json -show_format -show_streams input/source.mkv > input/probe.json

if [[ ! -s input/audio.wav ]]; then
  log "extract 16 kHz mono audio"
  ffmpeg -nostdin -v error -y -i input/source.mkv -vn -ac 1 -ar 16000 input/audio.wav
fi

if [[ ! -s input/proxy.mp4 ]]; then
  # runs in the background while Whisper works on the GPU host
  log "render 540p proxy for fast previews"
  ffmpeg -nostdin -v error -y -i input/source.mkv -vf "scale=-2:540,fps=30" \
    -c:v libx264 -preset veryfast -crf 26 -c:a aac -b:a 128k input/proxy.mp4.tmp.mp4 \
    && mv input/proxy.mp4.tmp.mp4 input/proxy.mp4 &
  PROXY_PID=$!
fi

if [[ ! -s input/transcript.json ]]; then
  log "whisper on $WHISPER_HOST ($WHISPER_MODEL, word timestamps)"
  remote=$(ssh "$WHISPER_HOST" 'mktemp -d /tmp/whisper-job.XXXXXX')
  trap 'ssh "$WHISPER_HOST" "rm -rf $remote" || true' EXIT
  scp -q input/audio.wav "$WHISPER_HOST:$remote/audio.wav"
  ssh "$WHISPER_HOST" "~/whisper-env/bin/whisper '$remote/audio.wav' --device cuda --model $WHISPER_MODEL \
    --language Japanese --word_timestamps True --output_dir '$remote' --output_format all" > work/whisper.log 2>&1
  for ext in json srt txt vtt tsv; do scp -q "$WHISPER_HOST:$remote/audio.$ext" "input/transcript.$ext"; done
fi

if [[ -n "${PROXY_PID:-}" ]]; then log "wait for proxy"; wait "$PROXY_PID"; fi

log "silence map"
ffmpeg -nostdin -v info -i input/audio.wav -af silencedetect=noise=-35dB:d=0.4 -f null - 2>&1 \
  | grep -E 'silence_(start|end)' > input/silences.txt || true

if [[ -z "$(ls frames)" ]]; then
  log "sample a frame every ${FRAME_EVERY}s"
  ffmpeg -nostdin -v error -i input/proxy.mp4 -vf "fps=1/${FRAME_EVERY},scale=480:-2" -q:v 4 frames/f_%05d.jpg
  log "contact sheets (4x4, each tile = ${FRAME_EVERY}s)"
  ffmpeg -nostdin -v error -i input/proxy.mp4 \
    -vf "fps=1/${FRAME_EVERY},scale=480:-2,drawtext=text='%{pts\:hms}':x=8:y=8:fontsize=28:fontcolor=yellow:box=1:boxcolor=black@0.6,tile=4x4" \
    -q:v 4 sheets/sheet_%03d.jpg
fi

python3 - <<PY
import json, pathlib
p = json.load(open("input/probe.json"))
t = json.load(open("input/transcript.json"))
segs = [{"i": i, "start": round(s["start"], 2), "end": round(s["end"], 2), "text": s["text"].strip()}
        for i, s in enumerate(t["segments"])]
pathlib.Path("input/segments.jsonl").write_text("\n".join(json.dumps(s, ensure_ascii=False) for s in segs) + "\n")
print(f"duration={float(p['format']['duration']):.1f}s segments={len(segs)}")
PY
log "done: $JOB"
