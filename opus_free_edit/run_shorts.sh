#!/usr/bin/env bash
# Shorts mode: Opus plans and edits vertical shorts for the SNS post queue from one long video.
# Usage: run_shorts.sh <long-form job dir | YouTube video id | video file> <shorts job dir>
#   job dir / video id: a long video edited by this repository (the id is looked up in
#     ~/video-jobs/*/out/youtube_upload.json); its finished out/final.mp4 is the input and the job is linked as long/
#     (raw recording, slides, えびフライ clips, EDIT_NOTES).
#   video file: any finished long video (no long/ then).
# Env: EDIT_MODEL, VIDEO_JOBS (default ~/video-jobs), NOTIFY_THREAD / DISCORD_THREAD_ID (voice warnings).
# <shorts job dir>/appendix.md (optional) is appended to the brief. STATUS ends as done or failed.
# Nothing is uploaded or posted; out/shorts.json is what the post queue registration reads.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/.." && pwd)
[[ $# -ge 2 ]] || { echo "usage: run_shorts.sh <long job dir | video id | video file> <shorts job dir>" >&2; exit 2; }
ARG=$1; JOB=$(realpath -m "$2")
MODEL=${EDIT_MODEL:-claude-opus-5-5}
VIDEO_JOBS=${VIDEO_JOBS:-$HOME/video-jobs}
log() { printf '[shorts %s] %s\n' "$(date +%H:%M:%S)" "$*"; }
mkdir -p "$JOB"
trap 'rc=$?; [[ $rc -eq 0 ]] && echo done > "$JOB/STATUS" || echo failed > "$JOB/STATUS"' EXIT
trap 'exit 143' TERM INT HUP
echo running > "$JOB/STATUS"

LONG=""; VIDEO_ID=""
if [[ -d "$ARG" ]]; then
  LONG=$(realpath "$ARG")
elif [[ -f "$ARG" ]]; then
  SOURCE=$(realpath "$ARG")
elif [[ "$ARG" =~ ^[A-Za-z0-9_-]{11}$ ]]; then
  VIDEO_ID=$ARG
  hit=$(grep -l "\"video_id\": \"$ARG\"" "$VIDEO_JOBS"/*/out/youtube_upload.json 2>/dev/null | head -1 || true)
  [[ -n "$hit" ]] || { log "no long-form job in $VIDEO_JOBS uploaded $ARG; pass the video file instead"; exit 2; }
  LONG=$(dirname "$(dirname "$hit")")
else
  log "not a job dir, video file or video id: $ARG"; exit 2
fi
if [[ -n "$LONG" ]]; then
  SOURCE="$LONG/out/final.mp4"
  [[ -s "$SOURCE" ]] || { log "$LONG has no out/final.mp4"; exit 2; }
  ln -sfn "$LONG" "$JOB/long"
  if [[ -z "$VIDEO_ID" && -s "$LONG/out/youtube_upload.json" ]]; then
    VIDEO_ID=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("video_id",""))' "$LONG/out/youtube_upload.json")
  fi
fi
log "source: $SOURCE${LONG:+ (long job $LONG)}${VIDEO_ID:+ video $VIDEO_ID}"
printf '%s\n' "$VIDEO_ID" > "$JOB/VIDEO_ID"

t0=$(date +%s)
# Transcript, proxy, frames and contact sheets of the finished video (Whisper on the GPU host).
WHISPER_PROMPT=${WHISPER_PROMPT:-"話し手は胡田昌彦（えびすだ まさひこ）。相づちを打つキャラクターはえびフライ。"} \
  "$HERE/prepare.sh" "$SOURCE" "$JOB"
t1=$(date +%s)

mkdir -p "$JOB/tools" "$JOB/work" "$JOB/out"
ln -sfn "$REPO/assets" "$JOB/assets"
ln -sfn "$HERE/reference" "$JOB/reference"
cp "$HERE/shorts-brief.md" "$JOB/BRIEF.md"
if [[ -s "$JOB/appendix.md" ]]; then cat "$JOB/appendix.md" >> "$JOB/BRIEF.md"; fi
cp "$HERE/shorts_platforms.json" "$JOB/platforms.json"
cp "$HERE/check_stereo.py" "$HERE/check_silence.py" "$HERE/check_shorts.py" "$HERE/editing-techniques.md" "$JOB/"
cp "$HERE/tools/ebifry_clip.py" "$JOB/tools/"

log "agent shorts edit with $MODEL"
cd "$JOB"
claude -p "Read BRIEF.md in the current directory and carry it out completely." \
  --model "$MODEL" --output-format stream-json --verbose \
  --permission-mode bypassPermissions > work/agent.jsonl 2> work/agent.stderr || log "agent exited non-zero"
t2=$(date +%s)

python3 "$HERE/usage_report.py" work/agent.jsonl > out/USAGE.md || log "usage report could not run"
# Flags new えびフライ lines made with a fallback voice (out/VOICE_WARNING.md).
python3 "$HERE/tts_guard.py" report "$JOB" || log "voice report could not run"
python3 "$HERE/check_shorts.py" "$JOB" --platforms platforms.json || { log "shorts failed the checks"; exit 1; }
printf '\n## Wall time\n\n| stage | seconds |\n|---|---|\n| prepare | %d |\n| agent | %d |\n| total | %d |\n' \
  $((t1-t0)) $((t2-t1)) $((t2-t0)) >> out/USAGE.md
log "done"; cat out/USAGE.md
