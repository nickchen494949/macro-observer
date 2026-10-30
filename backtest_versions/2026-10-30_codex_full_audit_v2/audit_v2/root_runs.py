from pathlib import Path
import subprocess,os,json,time,hashlib,sys
R=Path(__file__).resolve().parents[1];P='/Library/Frameworks/Python.framework/Versions/3.11/bin/python3'
steps=[('ledger',[P,'audit_v2/root_ledger_gate.py'],0),('stock_regression',[P,'research/sector_stock_momentum/test_codex_regressions.py'],0),('ledger_original',[P,'research/sector_stock_momentum/test_portfolio_ledger.py'],0),('fundamentals',[P,'research/sector_stock_momentum/test_fundamentals_pit.py'],0),('additional',[P,'audit/test_additional_regressions.py'],0),('macro',['node','test/codex_macro_regressions.js'],0),('forward_labels',['node','test/forward_labels_test.js'],0),('macro_replay',['node','backtest_v3.js','--revised-history'],0),('macro_source_gate',['node','backtest_v3.js'],2),('data_gate',['node','backtest/audit_data_coverage.js'],2)]
steps += [(p.stem,[P,str(p.relative_to(R))],0) for folder in ['phase3_validation','phase4_composite_validation','phase5_exploratory'] for p in sorted((R/'test'/folder).glob('*.py'))]
steps += [('vc',['node','test/phase6_construct_audit/vc_external_benchmark_validation.js'],0),('rp',['node','test/phase6_construct_audit/rp_external_benchmark_validation.js'],0),('main',[P,'research/sector_stock_momentum/backtest.py'],0),('stock_pool',[P,'audit/audit_stock_pool.py'],0),('ndx_pool',[P,'audit/audit_ndx_pool.py'],0)]
records=[]
for name,cmd,want in steps:
 log=R/'audit_v2'/f'root_{name}.log';t=time.monotonic()
 with log.open('w') as f:p=subprocess.run(cmd,cwd=R,stdout=f,stderr=subprocess.STDOUT,env={**os.environ,'OPENBLAS_NUM_THREADS':'2','OMP_NUM_THREADS':'2','MPLCONFIGDIR':str(R/'audit_v2/matplotlib')})
 rec={'name':name,'command':cmd,'exit':p.returncode,'expected':want,'pass':p.returncode==want,'seconds':round(time.monotonic()-t,2),'log':str(log.relative_to(R)),'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest()};records.append(rec)
 (R/'audit_v2/root_runs.json').write_text(json.dumps(records,indent=2));print(rec,flush=True)
 if p.returncode!=want: print(log.read_text()[-3000:],flush=True)
