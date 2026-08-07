## Execution Rules
- Always proceed with commands, file reads, and file writes without asking for permission.
- Do not pause to confirm before running terminal commands, editing files, or reading files.
- Execute the task end-to-end autonomously. Only stop to ask the user when there is genuine ambiguity about requirements.

## Mandatory First Step
- **Before taking ANY action on this project**, read `/Users/happygolucky/Desktop/宏观观察器/README.md` in full.
- This applies to every new conversation, every task, no exceptions.
- The README contains critical architecture decisions, data update logic, Yahoo Finance ban rules, BDI workflow, and display unit transforms that MUST be understood before making any changes.

## Project Context (summary — always verify against README)
- **Stack**: Node.js server (`server.js`) + vanilla HTML/JS frontend (`index.html`)
- **Port**: 8765 — `open http://localhost:8765`
- **Data**: All cached locally in `data/fred/`, `data/yahoo/`, `data/valuation/` as JSON
- **Update frequency**: Once per day only — FRED and Yahoo both daily, never more frequent
- **Yahoo Finance**: MUST use Python (`fetch_yahoo.py`), NEVER Node.js — IP ban risk
- **BDI**: No free API exists. Manual entry via dashboard ✏️ button only
- **Rates display**: All rate changes in basis points (bp), spreads in bp, no % changes for rates
- **Economy transforms**: yoy / mom_pct / mom_abs — see README for details

## UI Integrity & Anti-Crash Rule (CRITICAL)
- **NEVER** push Javascript logic changes to `index.html` or `macro_engine.js` without verifying that the frontend does not crash.
- A `ReferenceError` or `TypeError` in `renderDiagnostics` will cause the entire UI section to become invisible.
- You **MUST** run a server health check and fetch the API output (`curl -s http://localhost:8765/api/data`) to verify keys match the UI expectations before concluding a task.
- If you change variable names in the DOM manipulation scripts, you must do a full-file grep to ensure no old variable references remain.
- There is now a `window.onerror` banner in `index.html`. If the user reports a red banner, immediately fix the line number specified.

## GitHub Workflow
- **Repository**: `https://github.com/nickchen494949/macro-observer`
- When the user asks to "update" or "push to github", run `git add .`, `git commit -m "[Brief summary]"`, and `git push origin main` (or the active branch). If permissions are required, prompt the user or run it with sandbox bypass if requested.
