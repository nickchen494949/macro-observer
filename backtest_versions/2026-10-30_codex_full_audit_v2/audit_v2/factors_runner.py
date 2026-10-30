"""Offline, isolated-output real entry-point runner and evidence log for factor branches."""
import datetime
import fcntl
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'research/sector_stock_momentum'
AUDIT = ROOT / 'audit_v2'
TASKS = {
 'eps': ('eps_momentum.py', [], ['results/eps_momentum/*']),
 'sma': ('sma200_overlay.py', [], ['results/ml/sma200_*.csv']),
 'composite': ('composite3.py', [], ['results/ml/composite3_*.csv']),
 'roe': ('mom30_roe.py', [], ['results/ml/mom30roe_*.csv']),
 'tech': ('tech_only.py', [], ['results/ml/tech_*.csv']),
 'screen_build': ('factor_screen.py', ['build'], ['results/factor_screen/*.parquet']),
 'screen': ('factor_screen.py', ['screen'], ['results/factor_screen/*.csv']),
 'combo': ('factor_combo.py', [], ['results/factor_combo/*.csv']),
 'ndx': ('ndx_expand.py', [], ['results/ndx/*.csv', 'results/ndx/*.parquet']),
}
def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()

if '--child' in sys.argv:
    task = sys.argv[sys.argv.index('--child')+1]
    script, args, _ = TASKS[task]
    sys.path.insert(0, str(SRC))
    import backtest as bt
    diag = AUDIT / 'factors_price_diagnostics' / task
    diag.mkdir(parents=True, exist_ok=True)
    bt.RES = str(diag)
    sys.argv = [str(SRC/script), *args]
    runpy.run_path(str(SRC/script), run_name='__main__')
else:
    history = AUDIT / 'factors_runs.json'
    records = json.loads(history.read_text()) if history.exists() else []
    for task in sys.argv[1:]:
        script, args, patterns = TASKS[task]
        inputs = [SRC / p for p in ['backtest.py', 'portfolio_accounting.py', 'legacy_portfolio.py', script,
                  'ml_features.py', 'fundamentals_pit.py', 'explosive_factors.py', 'sma200_overlay.py',
                  'factor_screen.py', 'improve_v3.py', 'ndx_universe.py', 'results/explosive/v2_selected_factors.json',
                  'results/ml/panel.parquet', 'results/explosive/panel_explosive_ear.parquet',
                  'results/factor_screen/panel_screen.parquet']]
        before = {str(p.relative_to(ROOT)): sha(p) for p in inputs if p.exists()}
        before_outputs = {p: p.stat().st_mtime_ns for pattern in patterns for p in SRC.glob(pattern) if p.is_file()}
        log = AUDIT / f'factors_{task}_{len(records)+1:02d}.log'
        command = [sys.executable, str(Path(__file__).resolve()), '--child', task]
        start = time.monotonic()
        started = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with log.open('w') as f:
            cp = subprocess.run(command, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
        outputs = sorted({p for pattern in patterns for p in SRC.glob(pattern) if p.is_file()})
        rec = {'task': task, 'script': script, 'command': command, 'started_utc': started,
               'elapsed_seconds': time.monotonic()-start, 'exit_code': cp.returncode,
               'log': str(log.relative_to(ROOT)), 'input_hashes': before,
               'outputs_after_run': {str(p.relative_to(ROOT)): sha(p) for p in outputs},
               'outputs_written_this_run': {str(p.relative_to(ROOT)): sha(p) for p in outputs
                                          if p.stat().st_mtime_ns != before_outputs.get(p)},
               'stale_outputs_not_revalidated': [str(p.relative_to(ROOT)) for p in outputs
                                                if p.stat().st_mtime_ns == before_outputs.get(p)],
               'frozen_input_manifest': 'audit_v2/baseline.json',
               'outputs_status': 'REAL_RUN_COMPLETED_PENDING_REVIEW' if cp.returncode == 0 else 'FAILED_OUTPUTS_NOT_CERTIFIED'}
        archive = AUDIT / 'factors_run_archive'
        archive.mkdir(exist_ok=True)
        token = started.replace(':', '').replace('+', '_')
        (archive/f'{task}_{token}.json').write_text(json.dumps(rec, ensure_ascii=False, indent=2))
        with (AUDIT/'factors_runs.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            records = json.loads(history.read_text()) if history.exists() else []
            records.append(rec)
            history.write_text(json.dumps(records, ensure_ascii=False, indent=2))
        print(json.dumps({k:rec[k] for k in ['task','exit_code','elapsed_seconds','log']}, ensure_ascii=False), flush=True)
        if cp.returncode:
            sys.exit(cp.returncode)
