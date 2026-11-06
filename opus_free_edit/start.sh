#!/usr/bin/env bash
# Start run.sh in its own systemd user unit, outside the caller's cgroup, so a service restart does not kill the edit.
# Usage: start.sh <source video | latest> <job dir> [--no-upload]
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
[[ $# -ge 2 ]] || { echo "usage: start.sh <source video | latest> <job dir> [--no-upload]" >&2; exit 2; }
SOURCE=$1; JOB=$(realpath -m "$2"); shift 2
[[ "$SOURCE" == latest ]] || SOURCE=$(realpath -e "$SOURCE")
mkdir -p "$JOB"

# A service has no login session, so the user bus has to be named explicitly.
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
export DBUS_SESSION_BUS_ADDRESS=${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}

UNIT=video-edit-$(basename "$JOB" | tr -c 'A-Za-z0-9_.\n-' '-')
ENV_ARGS=(--setenv=PATH="$PATH" --setenv=HOME="$HOME")
for name in DECK_SLUG PRESENTATIONS_REPO EDIT_MODEL WINNING_PATTERN INBOX YT_TOKEN EDIT_HANDOFF_DIR; do
  if [[ -n "${!name:-}" ]]; then ENV_ARGS+=(--setenv="$name=${!name}"); fi
done

echo starting > "$JOB/STATUS"
if ! systemd-run --user --unit="$UNIT" --collect --working-directory="$JOB" "${ENV_ARGS[@]}" \
    -p "StandardOutput=append:$JOB/run.log" -p "StandardError=append:$JOB/run.log" \
    "$HERE/run.sh" "$SOURCE" "$JOB" "$@"; then
  echo failed > "$JOB/STATUS"
  echo "could not start unit $UNIT" >&2
  exit 1
fi
echo "started $UNIT; log: $JOB/run.log"
