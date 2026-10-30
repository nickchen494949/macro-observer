from pathlib import Path
import subprocess,os,json,time,concurrent.futures,hashlib
R=Path(__file__).resolve().parents[1];H=R/'research/sector_stock_momentum';P='/Library/Frameworks/Python.framework/Versions/3.11/bin/python3';rows=[]
code="import tempfile; from pathlib import Path; import backtest as bt; p=Path('../../audit_v2/selection_price_diagnostics').resolve(); p.mkdir(exist_ok=True); bt.RES=str(p); import pit_truncation_test as t; x=tempfile.TemporaryDirectory(prefix='codex_pit_'); tempfile.gettempdir=lambda:x.name; t.main()"
def run(name,cmd):
 t=time.monotonic();log=R/'audit_v2'/f'root_{name}.log'
 with log.open('w') as f:p=subprocess.run(cmd,cwd=H,stdout=f,stderr=subprocess.STDOUT,env={**os.environ,'OPENBLAS_NUM_THREADS':'2','OMP_NUM_THREADS':'2'})
 r={'name':name,'exit':p.returncode,'seconds':time.monotonic()-t,'log':str(log.relative_to(R)),'sources':{n:hashlib.sha256((H/n).read_bytes()).hexdigest() for n in ['backtest.py','pit_truncation_test.py','determinism_test.py']}};rows.append(r);(R/'audit_v2/root_selection_checks.json').write_text(json.dumps(rows,indent=2));print(r,flush=True)
 assert p.returncode==0,(name,log.read_text()[-3000:])
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
 jobs=[ex.submit(run,'price_truncation',[P,'-c',code]),ex.submit(run,'determinism',[P,'determinism_test.py'])]
 for j in jobs:j.result()
