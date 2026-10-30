from pathlib import Path
import subprocess,os,json,time,hashlib,shutil,concurrent.futures
R=Path(__file__).resolve().parents[1];H=R/'research/sector_stock_momentum';P='/Library/Frameworks/Python.framework/Versions/3.11/bin/python3'
archive=R/'audit_v2/superseded_execution';archive.mkdir(exist_ok=True)
shutil.copytree(H/'results/ml2',archive/'ml2_before_execution_fix',dirs_exist_ok=True)
for p in (H/'results').glob('*'):
 if p.is_file() and (p.suffix in ['.json','.csv']):shutil.copy2(p,archive/p.name)
steps=[('ml2_final',[P,'ml2_run.py','run'],H),('main_final',[P,'backtest.py'],H)]
records=[]
def run(task):
 name,cmd,cwd=task;log=R/'audit_v2'/f'root_{name}.log';start=time.monotonic()
 src={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in H.glob('*.py')}
 with log.open('w') as f:
  p=subprocess.run(cmd,cwd=cwd,stdout=f,stderr=subprocess.STDOUT,env={**os.environ,'OPENBLAS_NUM_THREADS':'2','OMP_NUM_THREADS':'2','MPLCONFIGDIR':str(R/'audit_v2/matplotlib')})
 return {'name':name,'exit':p.returncode,'seconds':time.monotonic()-start,'log':str(log.relative_to(R)),'source_hashes':src}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 for fut in concurrent.futures.as_completed([pool.submit(run,t) for t in steps]):
  row=fut.result();records.append(row);(R/'audit_v2/root_final_execution_runs.json').write_text(json.dumps(records,indent=2));print({k:v for k,v in row.items() if k!='source_hashes'},flush=True)
