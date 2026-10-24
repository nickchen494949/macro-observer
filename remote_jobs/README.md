# Remote Runner Jobs

This directory is the inbox for the project-scoped remote runner.

Each job is a JSON file named `<job-id>.json`, where `job.id` exactly matches the filename.
The runner processes at most one pending job per 30-second auto-sync cycle and writes the result to `remote_results/<job-id>.json`.

Allowed actions:

- `health` — GET `http://127.0.0.1:8765/health`
- `api_get` — GET localhost `/health` or `/api/*`
- `git_status` — read current Git status and HEAD
- `node_check` — `node --check` on repository JS files
- `node_script` — run a repository JS file with Node
- `python_script` — run a repository Python file
- `npm_script` — run an existing finite npm script (`start` and `dev` are blocked)

The runner does not accept arbitrary shell strings, `sudo`, system paths, `.git`, `node_modules`, runtime data, or secrets. Output is capped and obvious credentials are redacted before results are pushed.

Example:

```json
{
  "id": "20260810-1300-health",
  "enabled": true,
  "action": "health",
  "timeoutMs": 15000
}
```
