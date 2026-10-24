# Remote Runner Results

The Mac remote runner writes one JSON result per job here and pushes it back to the same branch.

Each result includes:

- action and job id
- pass/fail/rejected status
- exit code and signal
- stdout/stderr (capped and redacted)
- start/end timestamps and duration
- local Git HEAD before execution
- any code/config worktree changes observed after the job

These files let the coding loop read actual local execution results from GitHub without requiring a separate coding agent.
