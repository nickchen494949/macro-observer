# Mac Auto-Sync for Macro Observer

This setup keeps the local dashboard at `http://localhost:8765` synchronized with the GitHub branch `agent/phase4-composite-validation`.

## One-time install

```bash
cd /Users/happygolucky/Projects/宏观观察器
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

## Runtime data vs code safety

The dashboard is expected to update files under `data/` and `csv/` during normal operation. Those uncommitted runtime-data changes do **not** block auto-sync.

Auto-sync still refuses to pull when:

- there are uncommitted changes outside `data/` and `csv/` (for example JS, HTML, schema, config, scripts, docs, or other code files);
- the local checkout is on a different branch;
- the local branch has local commits that are not already contained in the remote branch;
- the local branch has diverged from the remote branch;
- `git fetch` or fast-forward pull fails.

If a remote commit would overwrite a locally modified runtime-data file, Git itself refuses the pull. Auto-sync logs the failure and leaves the local files untouched.

It never uses `git reset --hard`, never force-pulls, and never auto-stashes local edits.

Important: daily `data/` / `csv/` refreshes should normally remain uncommitted local runtime changes. If you intentionally create a local commit, that commit is **not** ignored by auto-sync; push/reconcile it normally before automatic code pulls can continue.

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
cd /Users/happygolucky/Projects/宏观观察器
bash scripts/uninstall_autosync.sh
```

The uninstall command removes the launchd agents but keeps logs and repository files.

## Auto-sync test marker

Remote test pushed at `2026-08-10T12:51+08:00`. If auto-sync is healthy, this commit should appear locally within about 30 seconds and trigger a dashboard server restart.

Second live test pushed at `2026-08-10T12:54+08:00`. If the closed loop is healthy, this newer commit should also appear locally automatically without any manual `git pull`.
