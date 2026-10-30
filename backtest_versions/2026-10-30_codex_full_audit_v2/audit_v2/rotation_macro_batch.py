"""Single-process queue; retain one log and execution record for every entry."""
import json, pathlib, subprocess, sys, time
ROOT=pathlib.Path(__file__).resolve().parents[1]
families=['sector_rotation','strategy_comparison','hawkish_path']
mode=sys.argv[1]
skip={'engine.py','audit_scope.py','source_gate.py','strategy_engine.py'}
records=[]
for family in families:
    for p in sorted((ROOT/'research'/family).glob('*.py')):
        if p.name in skip:continue
        if mode=='gates':
            if family=='strategy_comparison' and p.name=='sep_falsification_test.py':continue
            args=[]
        else:
            if family=='strategy_comparison':continue
            if p.name in {'run_backtest.py','rf_backtest.py','fetch_sector_data.py','waterfall_autopsy.py','rf_audit.py'}:continue
            args=['--revised-history']
        log=ROOT/'audit_v2'/f'rotation_macro_{mode}_{family}_{p.stem}.log'
        print(f'START {family}/{p.name}',flush=True)
        start=time.time()
        with log.open('w') as fh:
            cp=subprocess.run([sys.executable,str(ROOT/'audit_v2/rotation_macro_execute.py'),str(p.relative_to(ROOT)),*args],cwd=ROOT,stdout=fh,stderr=subprocess.STDOUT)
        records.append({'entry':str(p.relative_to(ROOT)),'exit_code':cp.returncode,'seconds':time.time()-start,'log':str(log.relative_to(ROOT))})
        (ROOT/'audit_v2'/f'rotation_macro_{mode}_batch.json').write_text(json.dumps(records,indent=2))
        print(f'END {family}/{p.name} code={cp.returncode}',flush=True)
