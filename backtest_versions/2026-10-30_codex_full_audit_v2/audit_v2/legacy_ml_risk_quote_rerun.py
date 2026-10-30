"""Bounded risk-only rerun after independent missing-quote review."""
from pathlib import Path
import hashlib, json, os, subprocess, sys, time
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'research/sector_stock_momentum'
AUD = ROOT / 'audit_v2'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
old = json.loads((AUD/'legacy_ml_verification.json').read_text())
before = {x['path']: sha(ROOT/x['path']) for x in old['ledgers']}
oldrisk = SRC/'results/explosive/risk_report.csv'
(AUD/'legacy_ml_risk_before_quote_fix.csv').write_bytes(oldrisk.read_bytes())
checks = subprocess.run([sys.executable,str(AUD/'legacy_ml_gate.py')],capture_output=True,text=True,check=True)
gate = json.loads(checks.stdout.strip().splitlines()[-1])
(AUD/'legacy_ml_gate.json').write_text(json.dumps(gate,indent=2))
log = AUD/'legacy_ml_risk_quote_rerun.log'
source = {p.name:sha(p) for p in SRC.glob('*.py')}
cmd = [sys.executable,'-c',"import runpy;from pathlib import Path;import backtest as bt;p=Path('../../audit_v2/legacy_risk_price_diagnostics');p.mkdir(exist_ok=True);bt.RES=str(p.resolve());runpy.run_path('risk_report.py',run_name='__main__')"]
t=time.monotonic()
with log.open('w') as f:
    run=subprocess.run(cmd,cwd=SRC,stdout=f,stderr=subprocess.STDOUT,
                       env={**os.environ,'OPENBLAS_NUM_THREADS':'2','OMP_NUM_THREADS':'2'})
after = {p:sha(ROOT/p) for p in before}
record = {'command':cmd,'cwd':str(SRC),'exit_code':run.returncode,'seconds':time.monotonic()-t,
          'log':str(log.relative_to(ROOT)),'source_sha256':source,
          'monthly_ledgers_before':before,'monthly_ledgers_after':after,'all_monthly_ledgers_unchanged':before==after,
          'output_sha256':{str(p.relative_to(ROOT)):sha(p) for p in (SRC/'results/explosive').glob('risk_*')},
          'independent_review_trigger':'factors_writer: missing intra-month quote was forward-filled and called observed'}
(AUD/'legacy_ml_risk_quote_rerun.json').write_text(json.dumps(record,indent=2))
assert run.returncode==0 and before==after
for name in ['legacy_ml_verify.py','legacy_ml_index.py']:
    subprocess.run([sys.executable,str(AUD/name)],cwd=ROOT,check=True)
import pandas as pd
new=pd.read_csv(oldrisk)
prev=pd.read_csv(AUD/'legacy_ml_risk_before_quote_fix.csv')
pd.testing.assert_frame_equal(new,prev)
record['risk_values_and_status_unchanged']=True
(AUD/'legacy_ml_risk_quote_rerun.json').write_text(json.dumps(record,indent=2))
report=json.loads((AUD/'legacy_ml_disposition.json').read_text())
report['actual_execution']['counterexample_count']=len(gate['checks'])
report['actual_execution']['risk_quote_followup']='audit_v2/legacy_ml_risk_quote_rerun.json'
report['findings']=[x for x in report['findings'] if x['id']!='L13']+[
    {'id':'L13','verified':True,'issue':'Forward fill silently treated missing intra-month held quotes as observed prices',
     'correction':'Reject any nonfinite/nonpositive held quote; no fill; no observed path claim for incomplete marks',
     'test':'missing_nonpositive_daily_held_quote_not_filled',
     'actual':'Only risk_report rerun; all 83 monthly ledger hashes unchanged. Four existing observed paths had no missing marks, so existing daily values/statuses also unchanged.'}]
(AUD/'legacy_ml_disposition.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
print(json.dumps({'exit_code':run.returncode,'seconds':record['seconds'],'monthly_ledgers_unchanged':len(before),
                  'risk_values_and_status_unchanged':True,'counterexamples':len(gate['checks'])}))
