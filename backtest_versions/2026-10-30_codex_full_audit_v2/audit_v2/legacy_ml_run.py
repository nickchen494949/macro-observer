"""One bounded cached-data rerun with file fingerprints and actual exit status."""
import hashlib, json, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'research/sector_stock_momentum'
OUT = ROOT / 'audit_v2'
STEPS = [('features_final', ['ml_features.py']), ('explosive_v1_final', ['explosive_factors.py']),
         ('explosive_v2_final', ['explosive_v2.py']), ('ear_final', ['earnings_factor.py']),
         ('dev_final', ['ml_pipeline.py', 'dev']), ('holdout_final', ['ml_pipeline.py', 'holdout']),
         ('explosive_v3_final', ['improve_v3.py']),
         ('risk_final', ['risk_report.py'])]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
report = {'status': 'RUNNING', 'python': sys.executable, 'runs': [], 'network': 'none; frozen local caches only'}
report_path = OUT / 'legacy_ml_runs.json'
def save():
    report_path.write_text(json.dumps(report, indent=2))
def files():
    return [p for d in ('ml', 'explosive') for p in (SRC / 'results' / d).glob('*') if p.is_file()]
save()
for name, args in STEPS:
    before = {str(p.relative_to(ROOT)): sha(p) for p in files()}
    source_before = {str(p.relative_to(ROOT)): sha(p) for p in SRC.glob('*.py')}
    rec = {'name': name, 'command': [sys.executable, *args], 'cwd': str(SRC), 'started': time.time(),
           'log': str((OUT / ('legacy_ml_' + name + '.log')).relative_to(ROOT)), 'source_sha256': source_before}
    report['runs'].append(rec); save()
    with (ROOT / rec['log']).open('w') as log:
        result = subprocess.run(rec['command'], cwd=SRC, stdout=log, stderr=subprocess.STDOUT)
    rec.update(exit_code=result.returncode, seconds=time.time() - rec['started'], finished=time.time())
    rec['changed_outputs'] = {str(p.relative_to(ROOT)): sha(p) for p in files()
                              if before.get(str(p.relative_to(ROOT))) != sha(p)}
    rec['source_changed_during_run'] = [p for p, h in source_before.items() if sha(ROOT / p) != h]
    save()
    print(name, 'exit', result.returncode, 'seconds', round(rec['seconds'], 1), flush=True)
    if result.returncode:
        report['status'] = 'FAILED'; save(); sys.exit(result.returncode)
report['status'] = 'COMPLETED_PENDING_INDEPENDENT_REVIEW'; save()
