from pathlib import Path
import hashlib,json,ast
R=Path(__file__).resolve().parents[1];P=R.parent/'2026-10-30_codex_audited_modified'
m=json.loads((P/'audit/final_manifest.json').read_text())
parent_bad=[];input_bad=[];n=0
for x in m['files']:
 f=P/x['path']
 if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest()!=x['sha256']:parent_bad.append(x['path'])
 rel=x['path']
 if ('/data/' in rel or rel.startswith('data/')) and '/data/smallcap/' not in rel and not rel.endswith('rf_monthly.csv'):
  n+=1;q=R/rel
  if not q.is_file() or hashlib.sha256(q.read_bytes()).hexdigest()!=x['sha256']:input_bad.append(rel)
parsed=[]
for f in sorted(R.rglob('*.py')):
 if any(a in f.parts for a in ['_pit_trunc_2013-06-30','_pit_trunc_2017-06-30','_pit_trunc_2021-12-31']):continue
 ast.parse(f.read_text());parsed.append(str(f.relative_to(R)))
result={'parent_sealed_files_checked':len(m['files']),'parent_changes':parent_bad,'frozen_data_inputs_checked':n,'input_changes':input_bad,'python_files_syntax_checked':len(parsed),'status':'PASS' if not parent_bad and not input_bad else 'FAIL'}
(R/'audit_v2/root_provenance_check.json').write_text(json.dumps(result,indent=2));print(result)
assert not parent_bad and not input_bad
