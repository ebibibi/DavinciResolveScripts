#!/usr/bin/env bash
# One agentic edit: prepare -> claude -p (Opus decides everything) -> private upload -> usage report.
# Usage: run.sh <source video> <job dir> [--no-upload]
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/.." && pwd)
SOURCE=$(realpath "$1"); JOB=$(realpath -m "$2"); UPLOAD=${3:-}
MODEL=${EDIT_MODEL:-claude-opus-5-5}
WINNING_PATTERN=${WINNING_PATTERN:-}
log() { printf '[run %s] %s\n' "$(date +%H:%M:%S)" "$*"; }

t0=$(date +%s)
"$HERE/prepare.sh" "$SOURCE" "$JOB"
t1=$(date +%s)

mkdir -p "$JOB/context"
ln -sfn "$REPO/assets" "$JOB/assets"
[[ -n "$WINNING_PATTERN" && -f "$WINNING_PATTERN" ]] && cp "$WINNING_PATTERN" "$JOB/context/youtube-winning-pattern.md"
cp "$HERE/brief.md" "$JOB/BRIEF.md"
cp "$HERE/check_thumbnail.py" "$HERE/check_silence.py" "$JOB/"

log "agent edit with $MODEL"
cd "$JOB"
claude -p "Read BRIEF.md in the current directory and carry it out completely." \
  --model "$MODEL" --output-format stream-json --verbose \
  --permission-mode bypassPermissions > work/agent.jsonl 2> work/agent.stderr || log "agent exited non-zero"
t2=$(date +%s)

python3 "$HERE/usage_report.py" work/agent.jsonl > out/USAGE.md
[[ -s out/final.mp4 ]] || { log "no out/final.mp4 – stopping before upload"; exit 1; }
THUMB_SOURCE=()
[[ -s work/thumbnail_source.png ]] && THUMB_SOURCE=(--source work/thumbnail_source.png)
if [[ -s out/thumbnail.png ]] && ! python3 "$HERE/check_thumbnail.py" out/thumbnail.png "${THUMB_SOURCE[@]}"; then
  log "thumbnail hides the presenter's face – stopping before upload (fix out/thumbnail.png and rerun the upload)"
  exit 1
fi

if [[ "$UPLOAD" != "--no-upload" ]]; then
  log "private upload"
  python3 "$HERE/upload_private.py" "$JOB"
fi
t3=$(date +%s)
printf '\n## Wall time\n\n| stage | seconds |\n|---|---|\n| prepare | %d |\n| agent | %d |\n| upload | %d |\n| total | %d |\n' \
  $((t1-t0)) $((t2-t1)) $((t3-t2)) $((t3-t0)) >> out/USAGE.md
log "done"; cat out/USAGE.md
