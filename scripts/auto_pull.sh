#!/bin/bash
set -u

BRANCH="${MACRO_BRANCH:-agent/phase4-composite-validation}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$HOME/Library/Logs/macro-observer"
LOG_FILE="$LOG_DIR/autosync.log"
LOCK_DIR="/tmp/macro-observer-autosync.lock"
LABEL_SERVER="com.macro-observer.dashboard"
DOMAIN="gui/$(id -u)"

mkdir -p "$LOG_DIR"

log() {
  printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG_FILE"
}

# Runtime data is expected to change as the dashboard refreshes market data.
# Generated remote_results are also allowed so the runner can recover/publish them.
# All code/config/job edits still block automatic pulls.
blocking_worktree_changes() {
  git status --porcelain --untracked-files=all -- \
    . \
    ':(exclude)data' ':(exclude)data/**' \
    ':(exclude)csv' ':(exclude)csv/**' \
    ':(exclude)remote_results' ':(exclude)remote_results/**'
}

run_remote_runner() {
  if [ -f "$REPO_DIR/scripts/remote_runner.js" ]; then
    node "$REPO_DIR/scripts/remote_runner.js" >> "$LOG_FILE" 2>&1 || log "WARN: remote runner returned non-zero"
  fi
}

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

cd "$REPO_DIR" || exit 1

CURRENT_BRANCH="$(git branch --show-current 2>/dev/null || true)"
if [ "$CURRENT_BRANCH" != "$BRANCH" ]; then
  log "SKIP: current branch '$CURRENT_BRANCH' != '$BRANCH'"
  exit 0
fi

BLOCKING_CHANGES="$(blocking_worktree_changes)"
if [ -n "$BLOCKING_CHANGES" ]; then
  log "SKIP: local CODE/config/job worktree changes detected; refusing to overwrite"
  while IFS= read -r line; do
    [ -n "$line" ] && log "  $line"
  done <<< "$BLOCKING_CHANGES"
  exit 0
fi

# First pass lets the runner recover an unpublished result or finish a previously pulled job.
run_remote_runner

if ! git fetch --quiet origin "$BRANCH"; then
  log "ERROR: git fetch failed"
  exit 0
fi

LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse "origin/$BRANCH")"

if [ "$LOCAL" = "$REMOTE" ]; then
  exit 0
fi

# Local commits are never ignored. If local HEAD is not an ancestor of remote,
# require manual review rather than rewriting history.
if ! git merge-base --is-ancestor "$LOCAL" "$REMOTE"; then
  log "SKIP: local branch has diverged from origin/$BRANCH; manual review required"
  exit 0
fi

# Uncommitted data/csv/result changes are allowed. Git itself will still refuse
# a pull if a remote commit would overwrite one of those modified files.
if ! git pull --ff-only --quiet origin "$BRANCH"; then
  log "ERROR: fast-forward pull failed (possible overlap with local runtime/result changes)"
  exit 0
fi

NEW_HEAD="$(git rev-parse --short=12 HEAD)"
log "UPDATED: pulled $NEW_HEAD"

# Restart the managed dashboard server so server-side code is immediately live.
launchctl kickstart -k "$DOMAIN/$LABEL_SERVER" >/dev/null 2>&1 || true
sleep 2

# Process a job that may have arrived in the commit we just pulled.
run_remote_runner

# Best-effort browser refresh for open local dashboard tabs.
# Failure here is non-fatal; the code has already been updated and the server restarted.
osascript >/dev/null 2>&1 <<'APPLESCRIPT' || true
if application "Google Chrome" is running then
  tell application "Google Chrome"
    repeat with w in windows
      repeat with t in tabs of w
        set u to URL of t
        if u starts with "http://localhost:8765" or u starts with "http://127.0.0.1:8765" then
          reload t
        end if
      end repeat
    end repeat
  end tell
end if

if application "Safari" is running then
  tell application "Safari"
    repeat with w in windows
      repeat with t in tabs of w
        set u to URL of t
        if u starts with "http://localhost:8765" or u starts with "http://127.0.0.1:8765" then
          set URL of t to u
        end if
      end repeat
    end repeat
  end tell
end if
APPLESCRIPT

log "LIVE: dashboard server restarted; browser refresh attempted"
