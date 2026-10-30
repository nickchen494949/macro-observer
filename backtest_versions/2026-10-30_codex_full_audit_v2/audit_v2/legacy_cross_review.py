"""Bounded independent legacy review; no retraining, downloads or source/result writes."""
import ast
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
from unittest.mock import patch
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'research/sector_stock_momentum'
sys.path.insert(0,str(SRC))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def readonly_run(name):
    p=ROOT/'audit_v2'/name
    tree=ast.parse(p.read_text())
    tree.body=[n for n in tree.body if not(isinstance(n,ast.Expr) and isinstance(n.value,ast.Call)
        and isinstance(n.value.func,ast.Attribute) and n.value.func.attr=='write_text')]
    scope={'__file__':str(p),'__name__':'__main__'}
    output=io.StringIO()
    with contextlib.redirect_stdout(output):exec(compile(tree,str(p),'exec'),scope)
    return scope,output.getvalue()

gate,gate_log=readonly_run('legacy_ml_gate.py')
verification,verify_log=readonly_run('legacy_ml_verify.py')
import ml_pipeline as ml
import backtest as bt
import risk_report as risk

checks=[]
def check(name,passed,detail):
    checks.append({'name':name,'passed':bool(passed),'detail':detail})
    assert passed,(name,detail)
panel_path=SRC/'results/ml/panel.parquet'
panel=pd.read_parquet(panel_path)
unknown=panel.exit_status.isin(['source_gap','unresolved'])
check('unknown labels excluded from actual panel rank',panel.loc[unknown,'fwd_rank'].isna().all()
      and panel.loc[unknown,'label_resolved'].eq(False).all(),{'unknown_rows':int(unknown.sum()),'all_panel_rows':len(panel)})
known_rank=panel.fwd_ret.where(~unknown).groupby(panel.t).rank(pct=True)
check('known-label rank exactly reconstructed',known_rank.equals(panel.fwd_rank),True)
synthetic=pd.DataFrame({'t':pd.to_datetime(['2011-01-31','2011-01-31','2013-12-31','2013-12-31']),
    'ticker':['known_train','unknown_train','unknown_test','known_test'],'fwd_rank':[.5,np.nan,np.nan,.8]})
synthetic['hold']=synthetic.t+pd.offsets.MonthEnd(1)
capture={}
def fit(model,train,test):
    capture['training']=train.ticker.tolist();capture['testing']=test.ticker.tolist()
    return np.arange(len(test),dtype=float)
with patch.object(ml,'fit_predict',side_effect=fit):pred=ml.walk_forward(synthetic,'ridge',[2014])
check('training excludes unknown but test retains and scores it',capture['training']==['known_train']
      and capture['testing']==['unknown_test','known_test'] and pred.score.notna().all(),capture)
index_path=ROOT/'audit_v2/legacy_ml_strategy_index.json'
index=json.loads(index_path.read_text())
fixed=[x for x in index if 'development factor fit before 2023' in x['evidence_role']]
check('fixed factors compare only from 2023',len(fixed)>0 and all(x['valid_comparison_start']=='2023-01-31' for x in fixed),
      {'fixed_records':len(fixed),'rule':'full historic ledgers retained as selection-sample diagnostics, not clean historical investment performance'})
check('index ledger fingerprints match actual outputs',all(sha(ROOT/x['ledger_path'])==x['sha256'] for x in index),len(index))
rows=verification['rows']
check('every persisted monthly ledger passed recurrence and calendar checks',len(rows)==83,{'ledgers':len(rows),
      'asset_ledger_count':sum(x['asset_ledger_checked'] for x in rows)})
report=verification['report']
check('unavailable daily paths have no claimed daily risk values',report['risk_daily_metrics_with_unavailable_status']==0,
      report['daily_nav_status'])
bt.SEG_D=None
marks=pd.DataFrame({'A':[100.,np.nan,110.]},index=pd.to_datetime(['2020-01-31','2020-02-03','2020-02-28']))
monthly=pd.DataFrame({'pick':['A'],'gross':[.1],'net':[.1],'capital_after_costs':[1.]},index=pd.DatetimeIndex(['2020-02-29']))
try:
    result,gap=risk.nav_daily(monthly,marks)
except ValueError as e:
    missing_rejected=True;detail=str(e)
else:
    missing_rejected=False;detail={'accepted_path':result.tolist(),'reconciliation_gap':gap}
checks.append({'name':'daily unknown internal mark not filled into verified path','passed':missing_rejected,'detail':detail})
source_names=['ml_features.py','ml_pipeline.py','legacy_portfolio.py','explosive_factors.py','explosive_v2.py','improve_v3.py','risk_report.py']
review={'status':'INDEPENDENT_BOUNDED_CHECKS_PASS_WITH_DATA_LIMITS' if missing_rejected else 'REQUIRES_DAILY_MISSING_MARK_FIX',
    'read_only':True,'reviewer':'factors_writer independent cross-review','scope':source_names,
    'source_hashes':{str((SRC/n).relative_to(ROOT)):sha(SRC/n) for n in source_names},
    'provided_gate':{'exit_code':0,'output':gate_log.strip(),'sha256':sha(ROOT/'audit_v2/legacy_ml_gate.py')},
    'provided_verification':{'exit_code':0,'output':verify_log.strip(),'sha256':sha(ROOT/'audit_v2/legacy_ml_verify.py'),
       'execution':'AST exact script executed with only audit report write suppressed','ledgers':rows},
    'actual_input_hashes':{str(p.relative_to(ROOT)):sha(p) for p in [panel_path,index_path,SRC/'results/explosive/v2_selected_factors.json',SRC/'results/explosive/risk_report.csv',SRC/'results/explosive/risk_daily_nav.parquet']},
    'checks':checks,
    'remaining_findings':[] if missing_rejected else [{'id':'LCR01','priority':'P2','file':'research/sector_stock_momentum/risk_report.py',
        'issue':'ffill accepts missing internal daily marks even when the monthly endpoint happens to reconcile; path cannot be called verified observed closes.',
        'counterexample':detail,'required_fix':'Reject any missing/nonpositive held-asset daily mark; leave daily risk unavailable and preserve monthly ledger.'}],
    'resolved_findings':[{'id':'LCR01','priority':'P2','file':'research/sector_stock_momentum/risk_report.py',
        'status':'RESOLVED_AND_INDEPENDENTLY_RETESTED',
        'original_reproduction':'Prices [100, NaN, 110] with gross=net=0.1 originally accepted NAV [1, 1, 1.1] and zero endpoint gap.',
        'correction':'Held-asset marks no longer forward-filled; missing/nonpositive observed marks fail daily certification.',
        'retest_error':detail}] if missing_rejected else [],
    'limitations':['Training admits labels ending on first test formation close under the explicitly idealized same-close assumption; no next-open executable claim.',
       'Pre-2023 fixed-factor selection sample cannot be ranked as out-of-sample. Historical test period repeatedly inspected.',
       'Source identity, filing releases, historical membership and terminal prices remain subject to parent data audit; no raw source certification here.',
       'Real ledger unknown outcomes remain labeled assumptions; unknown labels are excluded from training rather than deleting formation candidates.']}
scan=ROOT/'audit_v2/legacy_cross_daily_missing_scan.json'
if scan.exists():review['actual_verified_path_missing_scan']=json.loads(scan.read_text())
replay=ROOT/'audit_v2/legacy_ml_risk_quote_rerun.json'
if replay.exists():
    record=json.loads(replay.read_text())
    assert record['exit_code']==0 and record['all_monthly_ledgers_unchanged']
    assert record['source_sha256']['risk_report.py']==sha(SRC/'risk_report.py')
    assert all(sha(ROOT/p)==value for p,value in record['output_sha256'].items())
    review['targeted_risk_replay_evidence']={'path':str(replay.relative_to(ROOT)),'sha256':sha(replay),
        'source_and_result_hashes_independently_match':True,'monthly_ledgers_unchanged':True}
(ROOT/'audit_v2/legacy_cross_review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2))
print(json.dumps({'status':review['status'],'checks':len(checks),'fixed_records':len(fixed),'verified_ledgers':len(rows)},indent=2))
