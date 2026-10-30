"""Preserve records from already-started sequential runners before final merge."""
import json
from pathlib import Path
import time
root=Path(__file__).resolve().parent
dest=root/'factors_run_archive'
dest.mkdir(exist_ok=True)
for _ in range(18000):
    try:
        for r in json.loads((root/'factors_runs.json').read_text()):
            key=r['started_utc'].replace(':','').replace('+','_')
            p=dest/f"{r['task']}_{key}.json"
            if not p.exists():
                p.write_text(json.dumps(r,ensure_ascii=False,indent=2))
    except (json.JSONDecodeError,FileNotFoundError):
        pass
    if (root/'factors_runs_finished.flag').exists():
        break
    time.sleep(.2)
