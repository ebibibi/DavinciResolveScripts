#!/usr/bin/env bash
# Start run_shorts.sh in its own systemd user unit (same reason as start.sh: a service restart must not kill it).
# Usage: start_shorts.sh <long job dir | video id | video file> <shorts job dir>
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
[[ $# -ge 2 ]] || { echo "usage: start_shorts.sh <long job dir | video id | video file> <shorts job dir>" >&2; exit 2; }
SOURCE=$1; JOB=$(realpath -m "$2"); shift 2
[[ -e "$SOURCE" ]] && SOURCE=$(realpath -e "$SOURCE")
mkdir -p "$JOB"

# A service has no login session, so the user bus has to be named explicitly.
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
export DBUS_SESSION_BUS_ADDRESS=${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}

UNIT=video-shorts-$(basename "$JOB" | tr -c 'A-Za-z0-9_.\n-' '-')
ENV_ARGS=(--setenv=PATH="$PATH" --setenv=HOME="$HOME")
for name in EDIT_MODEL VIDEO_JOBS WHISPER_HOST NOTIFY_THREAD DISCORD_THREAD_ID EBI_EXPLAINER_REPO; do
  if [[ -n "${!name:-}" ]]; then ENV_ARGS+=(--setenv="$name=${!name}"); fi
done

echo starting > "$JOB/STATUS"
if ! systemd-run --user --unit="$UNIT" --collect --working-directory="$JOB" "${ENV_ARGS[@]}" \
    -p "StandardOutput=append:$JOB/run.log" -p "StandardError=append:$JOB/run.log" \
    "$HERE/run_shorts.sh" "$SOURCE" "$JOB" "$@"; then
  echo failed > "$JOB/STATUS"
  echo "could not start unit $UNIT" >&2
  exit 1
fi
echo "started $UNIT; log: $JOB/run.log"
