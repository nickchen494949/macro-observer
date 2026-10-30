from pathlib import Path
import subprocess,os,json,time,hashlib,shutil,concurrent.futures
R=Path(__file__).resolve().parents[1];H=R/'research/sector_stock_momentum';P='/Library/Frameworks/Python.framework/Versions/3.11/bin/python3'
a=R/'audit_v2/superseded_execution';a.mkdir(exist_ok=True);shutil.copytree(H/'results/ml2',a/'ml2_before_last_trade_entry_fix',dirs_exist_ok=True)
for f in [H/'results/summary.json',H/'results/winners_holdout/summary.csv',H/'results/winners_holdout/summary_STRICT.csv']:
 shutil.copy2(f,a/('_'.join(f.parts[-2:])))
records=[]
def run(name,cmd,cwd):
 log=R/'audit_v2'/f'root_{name}.log';start=time.monotonic();src={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in H.glob('*.py')}
 with log.open('w') as f:p=subprocess.run(cmd,cwd=cwd,stdout=f,stderr=subprocess.STDOUT,env={**os.environ,'OPENBLAS_NUM_THREADS':'2','OMP_NUM_THREADS':'2','MPLCONFIGDIR':str(R/'audit_v2/matplotlib')})
 rec={'name':name,'exit':p.returncode,'seconds':round(time.monotonic()-start,2),'log':str(log.relative_to(R)),'source_hashes':src};records.append(rec);(R/'audit_v2/root_closeout_runs.json').write_text(json.dumps(records,indent=2));print({k:v for k,v in rec.items() if k!='source_hashes'},flush=True)
 assert p.returncode==0,(name,log.read_text()[-2500:])
def risks():
 run('winners_final',[P,'winners_tracks.py'],H)
 run('daily_refresh',[P,'audit_v2/root_refresh_daily.py'],R)
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 jobs=[pool.submit(run,'ml2_complete',[P,'ml2_run.py','run'],H),pool.submit(risks)]
 for j in jobs:j.result()
