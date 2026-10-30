#!/usr/bin/env bash
# One agentic edit: prepare -> claude -p (Opus decides everything) -> private upload -> usage report.
# Usage: run.sh <source video | latest> <job dir> [--no-upload]
#   latest   = the newest .mp4/.mkv/.mov in $INBOX (default ~/tmp/movies, any letter case, e.g. C2078.MP4);
#              waits until the upload has finished (no partial files, size stable 2 min, ffprobe reads it).
# Env: DECK_SLUG (deck he talked through; captured from a clean origin/main worktree unless
#      PRESENTATIONS_REPO is set), EDIT_MODEL, WINNING_PATTERN, INBOX.
# A per-recording addendum in <job dir>/appendix.md is appended to the brief. <job dir>/STATUS ends as
# done or failed, so a waiter can poll it.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/.." && pwd)
JOB=$(realpath -m "$2"); UPLOAD=${3:-}
INBOX=${INBOX:-$HOME/tmp/movies}
MODEL=${EDIT_MODEL:-claude-opus-5-5}
WINNING_PATTERN=${WINNING_PATTERN:-$HOME/obsidian/02_Contexts/Youtuber活動/メインチャンネル/YouTube勝ちパターン（正本）.md}
log() { printf '[run %s] %s\n' "$(date +%H:%M:%S)" "$*"; }
mkdir -p "$JOB"
trap 'rc=$?; [[ $rc -eq 0 ]] && echo done > "$JOB/STATUS" || echo failed > "$JOB/STATUS"' EXIT

latest_in_inbox() {
  find "$INBOX" -maxdepth 1 -type f -iregex '.*\.\(mp4\|mkv\|mov\)' -printf '%T@ %p\n' 2>/dev/null \
    | sort -rn | head -1 | cut -d' ' -f2-
}

if [[ "$1" == latest ]]; then
  echo waiting > "$JOB/STATUS"
  log "wait for the newest recording in $INBOX to finish uploading"
  prev=-1; stable=0
  while :; do
    SOURCE=$(latest_in_inbox)
    if [[ -n "$SOURCE" ]] && ! compgen -G "$INBOX/*.partial" >/dev/null && ! compgen -G "$INBOX/*.part" >/dev/null; then
      size=$(stat -c %s "$SOURCE")
      if [[ "$size" == "$prev" ]]; then stable=$((stable + 20)); else stable=0; prev=$size; fi
      if (( stable >= 120 )) && ffprobe -v error -show_entries format=duration -of csv=p=0 "$SOURCE" >/dev/null 2>&1; then
        break
      fi
    fi
    sleep 20
  done
else
  SOURCE=$1
fi
SOURCE=$(realpath "$SOURCE")
log "source: $SOURCE"
echo running > "$JOB/STATUS"

if [[ -n "${DECK_SLUG:-}" && -z "${PRESENTATIONS_REPO:-}" ]]; then
  # The shared checkout may sit on someone's branch; capture the deck from a clean origin/main.
  PRESENTATIONS_REPO="$JOB/work/presentations-web"
  if [[ ! -d "$PRESENTATIONS_REPO" ]]; then
    (cd "$HOME/presentations-web" && git fetch -q origin && git worktree add -q --detach "$PRESENTATIONS_REPO" origin/main)
    (cd "$PRESENTATIONS_REPO" && npm ci --silent)
  fi
  export PRESENTATIONS_REPO
fi

t0=$(date +%s)
"$HERE/prepare.sh" "$SOURCE" "$JOB"
t1=$(date +%s)

mkdir -p "$JOB/context" "$JOB/tools"
ln -sfn "$REPO/assets" "$JOB/assets"
ln -sfn "$HERE/reference" "$JOB/reference"
[[ -f "$WINNING_PATTERN" ]] && cp "$WINNING_PATTERN" "$JOB/context/youtube-winning-pattern.md"
cp "$HERE/brief.md" "$JOB/BRIEF.md"
if [[ -s "$JOB/appendix.md" ]]; then cat "$JOB/appendix.md" >> "$JOB/BRIEF.md"; fi
cp "$HERE/check_thumbnail.py" "$HERE/ai_thumbnail.py" "$HERE/check_silence.py" "$HERE/check_stereo.py" \
  "$HERE/editing-techniques.md" "$JOB/"
cp "$HERE/tools/ebifry_clip.py" "$JOB/tools/"

log "agent edit with $MODEL"
cd "$JOB"
claude -p "Read BRIEF.md in the current directory and carry it out completely." \
  --model "$MODEL" --output-format stream-json --verbose \
  --permission-mode bypassPermissions > work/agent.jsonl 2> work/agent.stderr || log "agent exited non-zero"
t2=$(date +%s)

python3 "$HERE/usage_report.py" work/agent.jsonl > out/USAGE.md
[[ -s out/final.mp4 ]] || { log "no out/final.mp4 – stopping before upload"; exit 1; }
python3 "$HERE/check_stereo.py" out/final.mp4 || { log "audio is on one channel only – stopping before upload"; exit 1; }
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
