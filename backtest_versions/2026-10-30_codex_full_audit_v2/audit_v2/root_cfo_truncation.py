from pathlib import Path
import sys,json,shutil,hashlib
import pandas as pd
R=Path(__file__).resolve().parents[1];H=R/'research/sector_stock_momentum';sys.path.insert(0,str(H))
from pit_fundamentals_truncation_test import truncated_root,compare
from ml2_features import history_features
out=[]
for c in ['2013-06-30','2017-06-30','2021-12-31']:
 form=pd.date_range('2010-01-31',c,freq='ME');full=history_features(form);temp=truncated_root(c)
 try:tr=history_features(form,root=temp)
 finally:shutil.rmtree(temp)
 ok=compare(tr,full,['t','cik'],'CFO final '+c);out.append({'cutoff':c,'pass':ok,'rows':len(full)})
 print(out[-1],flush=True)
(R/'audit_v2/root_cfo_truncation.json').write_text(json.dumps({'checks':out,'source_sha256':hashlib.sha256((H/'ml2_features.py').read_bytes()).hexdigest()},indent=2))
assert all(x['pass'] for x in out)
