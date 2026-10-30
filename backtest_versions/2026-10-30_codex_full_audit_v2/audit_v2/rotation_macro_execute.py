"""Run one frozen entry with network disabled; capture actual inputs/results."""
import hashlib, json, os, pathlib, runpy, sys, time, traceback

ROOT = pathlib.Path(__file__).resolve().parents[1]
entry = (ROOT / sys.argv[1]).resolve()
args = sys.argv[2:]
out = ROOT / 'audit_v2' / 'rotation_macro_runs' / entry.parent.name / entry.stem
out.mkdir(parents=True, exist_ok=True)
reads = set()

def hook(event, values):
    if event in ('socket.connect', 'socket.getaddrinfo'):
        raise RuntimeError('Network disabled in frozen audit run')
    if event == 'open' and isinstance(values[0], (str, bytes, os.PathLike)):
        p = pathlib.Path(os.fsdecode(values[0])).resolve()
        mode = values[1]
        if p.is_relative_to(ROOT) and p.is_file() and (mode is None or 'r' in str(mode)):
            reads.add(p)

sys.addaudithook(hook)
sys.path.insert(0, str(entry.parent))
sys.argv = [str(entry), *args]
start = time.time(); status = 'SUCCESS'; code = 0; error = None; ns = {}
try:
    ns = runpy.run_path(str(entry), run_name='__main__')
except SystemExit as e:
    code = e.code if isinstance(e.code, int) else 1
    status = 'BLOCKED' if str(e).startswith('BLOCK') else ('SUCCESS' if not code else 'FAILED')
    error = str(e);print(error)
except BaseException as e:
    status = 'FAILED';code = 1;error = repr(e);traceback.print_exc()

outputs = []
if status == 'SUCCESS':
    import pandas as pd
    for k in ['res_df','results','rdf_ref','rdf_t1','rdf_no22','drop_df','rise_df','ep_df','episodes_df']:
        v = ns.get(k)
        if isinstance(v, list) and v and isinstance(v[0],dict): v = pd.DataFrame(v)
        if isinstance(v, pd.DataFrame):
            p = out / (k+'.csv');v.to_csv(p,index=False);outputs.append(str(p.relative_to(ROOT)))

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
for mod in list(sys.modules.values()):
    f=getattr(mod,'__file__',None)
    if f:
        p=pathlib.Path(f).resolve()
        if p.is_relative_to(ROOT) and p.is_file() and p.suffix=='.py':reads.add(p)
record = {'entry':str(entry.relative_to(ROOT)), 'args':args, 'status':status,
          'exit_code':code,'error':error,'duration_seconds':time.time()-start,
          'source_status':'not_certified_point_in_time','outputs':outputs,
          'inputs':[{'path':str(p.relative_to(ROOT)),'sha256':digest(p)} for p in sorted(reads)
                    if p.suffix in ['.csv','.json','.pdf','.py'] and 'audit_v2/rotation_macro_runs' not in str(p)]}
(out/('execution_revised.json' if '--revised-history' in args else 'execution_gate.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2))
raise SystemExit(code)
