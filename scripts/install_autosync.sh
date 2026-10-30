#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BRANCH="${MACRO_BRANCH:-agent/phase4-composite-validation}"
UID_NUM="$(id -u)"
DOMAIN="gui/$UID_NUM"
LAUNCH_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/Library/Logs/macro-observer"
SERVER_LABEL="com.macro-observer.dashboard"
SYNC_LABEL="com.macro-observer.autosync"
SERVER_PLIST="$LAUNCH_DIR/$SERVER_LABEL.plist"
SYNC_PLIST="$LAUNCH_DIR/$SYNC_LABEL.plist"

mkdir -p "$LAUNCH_DIR" "$LOG_DIR"

cd "$REPO_DIR"

if ! command -v git >/dev/null 2>&1; then
  echo "ERROR: git not found"
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "ERROR: npm not found"
  exit 1
fi

NPM_BIN="$(command -v npm)"
GIT_BIN="$(command -v git)"

CURRENT_BRANCH="$(git branch --show-current)"
if [ "$CURRENT_BRANCH" != "$BRANCH" ]; then
  echo "Switching to $BRANCH ..."
  git checkout "$BRANCH"
fi

BLOCKING_CHANGES="$(git status --porcelain --untracked-files=all -- \
  . \
  ':(exclude)data' ':(exclude)data/**' \
  ':(exclude)csv' ':(exclude)csv/**')"
if [ -n "$BLOCKING_CHANGES" ]; then
  echo "ERROR: local code/config worktree has uncommitted changes. Commit/stash those before installing auto-sync."
  echo "$BLOCKING_CHANGES"
  exit 1
fi

git fetch origin "$BRANCH"
git pull --ff-only origin "$BRANCH"

# Stop any manually-started dashboard currently occupying the dedicated local port.
if command -v lsof >/dev/null 2>&1; then
  PIDS="$(lsof -tiTCP:8765 -sTCP:LISTEN 2>/dev/null || true)"
  if [ -n "$PIDS" ]; then
    echo "Stopping existing process on localhost:8765 ..."
    kill $PIDS 2>/dev/null || true
    sleep 1
  fi
fi

# Remove previous launchd definitions if present.
launchctl bootout "$DOMAIN" "$SERVER_PLIST" >/dev/null 2>&1 || true
launchctl bootout "$DOMAIN" "$SYNC_PLIST" >/dev/null 2>&1 || true

cat > "$SERVER_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$SERVER_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$NPM_BIN</string>
    <string>start</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$REPO_DIR</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>5</integer>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>$(dirname "$NPM_BIN"):$(dirname "$GIT_BIN"):/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/server.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/server.err.log</string>
</dict>
</plist>
EOF

cat > "$SYNC_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$SYNC_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$REPO_DIR/scripts/auto_pull.sh</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$REPO_DIR</string>
  <key>RunAtLoad</key>
  <true/>
  <key>StartInterval</key>
  <integer>30</integer>
  <key>EnvironmentVariables</key>
  <dict>
    <key>MACRO_BRANCH</key>
    <string>$BRANCH</string>
    <key>PATH</key>
    <string>$(dirname "$NPM_BIN"):$(dirname "$GIT_BIN"):/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/autosync.launchd.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/autosync.err.log</string>
</dict>
</plist>
EOF

plutil -lint "$SERVER_PLIST" >/dev/null
plutil -lint "$SYNC_PLIST" >/dev/null

launchctl bootstrap "$DOMAIN" "$SERVER_PLIST"
launchctl bootstrap "$DOMAIN" "$SYNC_PLIST"
launchctl enable "$DOMAIN/$SERVER_LABEL" >/dev/null 2>&1 || true
launchctl enable "$DOMAIN/$SYNC_LABEL" >/dev/null 2>&1 || true
launchctl kickstart -k "$DOMAIN/$SERVER_LABEL"
launchctl kickstart -k "$DOMAIN/$SYNC_LABEL" >/dev/null 2>&1 || true

sleep 2

echo ""
echo "✅ Macro Observer auto-sync installed"
echo "   Repo:   $REPO_DIR"
echo "   Branch: $BRANCH"
echo "   Check:  every 30 seconds"
echo "   Server: http://localhost:8765"
echo ""
echo "Safety rules:"
echo "  • Runtime data changes in data/ and csv/ do NOT block auto-pull"
echo "  • Uncommitted code/config changes => auto-pull SKIPS"
echo "  • Local commits/diverged branch => auto-pull SKIPS"
echo "  • Updates are fast-forward only"
echo ""
echo "Logs:"
echo "  $LOG_DIR/autosync.log"
echo "  $LOG_DIR/server.log"
echo "  $LOG_DIR/server.err.log"
echo ""
echo "You can close Terminal after this. launchd keeps both services running."
