#!/bin/bash
set -euo pipefail

UID_NUM="$(id -u)"
DOMAIN="gui/$UID_NUM"
LAUNCH_DIR="$HOME/Library/LaunchAgents"
SERVER_LABEL="com.macro-observer.dashboard"
SYNC_LABEL="com.macro-observer.autosync"
SERVER_PLIST="$LAUNCH_DIR/$SERVER_LABEL.plist"
SYNC_PLIST="$LAUNCH_DIR/$SYNC_LABEL.plist"

launchctl bootout "$DOMAIN" "$SERVER_PLIST" >/dev/null 2>&1 || true
launchctl bootout "$DOMAIN" "$SYNC_PLIST" >/dev/null 2>&1 || true
rm -f "$SERVER_PLIST" "$SYNC_PLIST"

echo "✅ Macro Observer auto-sync removed"
echo "Logs were kept in ~/Library/Logs/macro-observer/"
