from pathlib import Path
import subprocess,os,json,time,hashlib
R=Path(__file__).resolve().parents[1];P='/Library/Frameworks/Python.framework/Versions/3.11/bin/python3';H=R/'research/sector_stock_momentum'
steps=[('fundamental_truncation',['pit_fundamentals_truncation_test.py']),('ml2',['ml2_run.py','run']),('winners',['winners_tracks.py']),('holdout',['winners_holdout.py','run']),('holdout_strict',['winners_holdout.py','run_strict'])]
rows=[]
for name,args in steps:
 t=time.monotonic();log=R/'audit_v2'/f'root_{name}.log'
 hashes={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in H.glob('*.py')}
 with log.open('w') as f:
  code="import sys,runpy;from pathlib import Path;import backtest as bt;p=Path('../../audit_v2/root_price_diagnostics');p.mkdir(exist_ok=True);bt.RES=str(p.resolve());sys.argv="+repr(args)+";runpy.run_path(sys.argv[0],run_name='__main__')"
  cmd=[P,'-c',code];p=subprocess.run(cmd,cwd=H,stdout=f,stderr=subprocess.STDOUT,env={**os.environ,'OPENBLAS_NUM_THREADS':'2','OMP_NUM_THREADS':'2'})
 row={'name':name,'command':[P]+args,'exit':p.returncode,'seconds':round(time.monotonic()-t,2),'log':str(log.relative_to(R)),'source_hashes':hashes};rows.append(row)
 (R/'audit_v2/root_dependent_runs.json').write_text(json.dumps(rows,indent=2));print({k:v for k,v in row.items() if k!='source_hashes'},flush=True)
 if p.returncode!=0:
  print(log.read_text()[-5000:],flush=True)
  if name=='fundamental_truncation':break
