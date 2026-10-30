from pathlib import Path
import json,hashlib,datetime,concurrent.futures
R=Path(__file__).resolve().parents[1];ROOT=R.parents[1];A=R/'audit_v2';OUT=ROOT/'outputs/backtest_full_audit_v2_20261030'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
original=[];bad=[]
for x in json.loads((R/'audit/claude_copy_manifest.json').read_text())['files']:
 p=ROOT/x['path']
 if p.is_file() and p.suffix in ['.py','.js'] and not x['path'].startswith('audit/'):
  original.append(x['path'])
  if sha(p)!=x['sha256']:bad.append(x['path'])
assert not bad,bad
(A/'original_source_check_v2.json').write_text(json.dumps({'status':'PASS','original_source_files_checked':len(original),'changes':bad,'basis':'first Claude-labeled copy manifest; original root remains untouched'},indent=2))
# Provenance covers the full local snapshot; transient bytecode and this manifest's own envelope are excluded.
exclude={'audit_v2/final_manifest_v2.json','audit_v2/final_seal_v2.json','audit_v2/git_publication.json','audit_v2/git_publication.log','audit_v2/seal_console.log'}
paths=[p for p in sorted(R.rglob('*')) if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts and str(p.relative_to(R)) not in exclude]
def record(p):return {'path':str(p.relative_to(R)),'bytes':p.stat().st_size,'sha256':sha(p)}
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:records=list(ex.map(record,paths))
m={'label':'Codex audited and modified — full audit v2','sealed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':records,'scope':'full local snapshot; current admitted results identified by final_strategy_register.json, not merely presence','exclusions':sorted(exclude)+['__pycache__/**']}
(A/'final_manifest_v2.json').write_text(json.dumps(m,ensure_ascii=False,indent=2))
w=OUT/'全部回测审核与同期比较_Codex_v2.xlsx'
seal={'status':'SEALED_AUDIT_COMPLETE_WITH_EXPLICIT_BLOCKS','manifest_sha256':sha(A/'final_manifest_v2.json'),'files':len(records),'bytes':sum(x['bytes'] for x in records),'workbook':str(w),'workbook_sha256':sha(w),'original_source_files_unchanged':len(original),'parent_snapshot_unchanged':10584,'frozen_model_data_inputs_unchanged':9352,'all_strategies_pass':False,'historical_source_certified':False}
(A/'final_seal_v2.json').write_text(json.dumps(seal,ensure_ascii=False,indent=2));print(seal)
# A bounded Git package: code/docs, v2 audit evidence, current ledger sources, final workbook.
d=json.loads((OUT/'work/data.json').read_text());selected={ROOT/'CLAUDE_AUDITED_VERSION.json',w,OUT/'审计说明_人话版.txt',R/'README.txt',R/'VERSION.json'}
for p in R.rglob('*'):
 if not p.is_file() or p.is_symlink() or '__pycache__' in p.parts:continue
 rel=str(p.relative_to(R))
 if '/data/' in '/'+rel or rel.startswith('data/'):continue
 if rel.startswith('audit_v2/'):
  if any(z in rel for z in ['superseded_execution/','matplotlib/','price_diagnostics/','rotation_macro_runs/','factors_run_archive/']):continue
  if p.suffix in ['.json','.txt','.py','.csv'] and p.stat().st_size<10_000_000:selected.add(p)
 elif not rel.startswith('audit/') and p.suffix in ['.js','.py','.md','.txt']:
  selected.add(p)
for s in d['sources']:
 p=R/s['path']
 if p.is_file() and p.stat().st_size<10_000_000 and '/data/' not in '/'+s['path']:selected.add(p)
for p in [OUT/'work/build.mjs',OUT/'work/collect.py',OUT/'work/data.json',OUT/'work/workbook_verification.json']:
 selected.add(p)
# Complete current grid ledgers are separately admitted, even when ignored by repo defaults.
for p in (R/'research/sector_stock_momentum/results/grid_monthly').glob('*.csv'):selected.add(p)
for p in selected:assert p.is_file() and p.is_relative_to(ROOT) and p.stat().st_size<10_000_000
sel=sorted(str(p.relative_to(ROOT)) for p in selected)
Path('/tmp/codex_backtest_v2_git_paths').write_bytes(b'\0'.join(s.encode() for s in sel)+b'\0')
Path('/tmp/codex_backtest_v2_git_package.json').write_text(json.dumps({'files':len(sel),'bytes':sum((ROOT/p).stat().st_size for p in sel),'paths':sel},indent=2))
print('Git package',len(sel),'files',sum((ROOT/p).stat().st_size for p in sel),'bytes; original/data auto-edits excluded')
