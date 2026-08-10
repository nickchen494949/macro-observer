# Mac Auto-Sync for Macro Observer

This setup keeps the local dashboard at `http://localhost:8765` synchronized with the GitHub branch `agent/phase4-composite-validation`.

## One-time install

```bash
cd /Users/happygolucky/Desktop/宏观观察器
git pull --ff-only origin agent/phase4-composite-validation
bash scripts/install_autosync.sh
```

After installation, Terminal does not need to remain open.

## What it does

Two macOS `launchd` agents are installed:

1. `com.macro-observer.dashboard`
   - Runs `npm start` from the repository.
   - Keeps the dashboard server alive on `http://localhost:8765`.
   - Restarts automatically if the process exits.

2. `com.macro-observer.autosync`
   - Checks `origin/agent/phase4-composite-validation` every 30 seconds.
   - Pulls only when the local checkout can be fast-forwarded safely.
   - Restarts the managed dashboard server after an update.
   - Best-effort refreshes open Chrome/Safari tabs pointing at localhost:8765.

## Safety behavior

Auto-sync refuses to pull when:

- the local working tree has uncommitted changes;
- the local checkout is on a different branch;
- the local branch has diverged from the remote branch;
- `git fetch` or fast-forward pull fails.

It never uses `git reset --hard`, never force-pulls, and never overwrites local edits.

## Logs

```text
~/Library/Logs/macro-observer/autosync.log
~/Library/Logs/macro-observer/autosync.launchd.log
~/Library/Logs/macro-observer/autosync.err.log
~/Library/Logs/macro-observer/server.log
~/Library/Logs/macro-observer/server.err.log
```

To watch synchronization activity:

```bash
tail -f ~/Library/Logs/macro-observer/autosync.log
```

## Uninstall

```bash
cd /Users/happygolucky/Desktop/宏观观察器
bash scripts/uninstall_autosync.sh
```

The uninstall command removes the launchd agents but keeps logs and repository files.
