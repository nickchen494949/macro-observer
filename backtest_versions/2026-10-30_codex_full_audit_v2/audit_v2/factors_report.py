"""Build auditable strategy index and independently recompute owned summary values."""
import datetime
import hashlib
import json
from pathlib import Path
import re
import sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'research/sector_stock_momentum'
AUDIT=ROOT/'audit_v2'
sys.path.insert(0,str(SRC))

def safe(s,n=None):
    s=''.join(c if c.isalnum() else '_' for c in s)
    return s if n is None else s[:n]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p): return str(p.relative_to(ROOT))
def read_ledger(p):
    d=pd.read_csv(p)
    c='month' if 'month' in d else d.columns[0]
    return d.set_index(pd.to_datetime(d[c])).drop(columns=[c])
def independent_stats(r):
    r=np.asarray(r,float)
    wealth=np.cumprod(1+r)
    cagr=wealth[-1]**(12/len(r))-1
    peak=np.maximum.accumulate(np.r_[1.,wealth])[1:]
    return cagr,float(np.min(wealth/peak-1))
def period_bounds(label):
    if label=='FULL to 2025-12': return '2010-01-01','2025-12-31'
    matches=re.findall(r'(\d{4})-(\d{2})',label)
    if len(matches)>=2:
        (y,m),(z,n)=matches[:2]
        return f'{y}-{m}-01', str(pd.Timestamp(f'{z}-{n}-01')+pd.offsets.MonthEnd(0))
    raise ValueError(label)

archives=sorted((AUDIT/'factors_run_archive').glob('*.json'))
runs={}
for p in archives:
    r=json.loads(p.read_text()); runs[(r['task'],r['started_utc'])]=r
for r in json.loads((AUDIT/'factors_runs.json').read_text()):
    runs[(r['task'],r['started_utc'])]=r
runs=sorted(runs.values(),key=lambda r:r['started_utc'])
(AUDIT/'factors_runs.json').write_text(json.dumps(runs,ensure_ascii=False,indent=2))
latest={r['task']:r for r in runs}
common_limits=['Retrospective history repeatedly examined; not a new blind holdout.',
               'Frozen vendor/index/sector/terminal data still have documented gaps; raw historical accuracy not certified.',
               'Month-end drawdown only; same-close execution is an idealized assumption, not next-open execution.']
items=[]
checks=[]

def add(family,name,summary,ledger,task,role='retrospective rule replay',cost='10 bp/side, actual drifted turnover, fees before investment',limitations=None):
    p=SRC/ledger if ledger else None
    run=latest.get(task,{})
    item={'family':family,'name':name,'summary_path':rel(SRC/summary) if summary else None,
          'ledger_path':rel(p) if p and p.exists() else None,
          'frequency':'monthly target review / rebalance' if cost!='gross benchmark (no transaction cost)' else 'buy and hold, monthly observation',
          'execution':'formation month-end close to next month-end close',
          'cost':cost,'evidence_role':role,'limitations':common_limits+(limitations or []),
          'run_task':task,'run_exit_code':run.get('exit_code'),'run_log':run.get('log'),
          'audit_status':'WRITER_COMPLETE_PENDING_INDEPENDENT_REVIEW' if run.get('exit_code')==0 and p and p.exists() else 'BLOCKED_OR_MISSING_RESULT'}
    if p and p.exists():
        d=read_ledger(p)
        item.update({'ledger_sha256':sha(p),'months':len(d),'first_month':str(d.index.min().date()),'last_month':str(d.index.max().date())})
        r=d.net.astype(float)
        monthly=pd.date_range(d.index.min(),d.index.max(),freq='ME')
        contiguous=d.index.equals(monthly)
        finite=bool(np.isfinite(r).all() and (r>=-1).all())
        checks.append({'family':family,'name':name,'check':'finite continuous unique monthly ledger',
                       'passed':bool(contiguous and finite and not d.index.has_duplicates),'months':len(d)})
        if 'capital_after_costs' in d and 'gross' in d:
            active=~((d.capital_after_costs==0)&(d.net==0))
            error=float((d.net[active]-(d.capital_after_costs[active]*(1+d.gross[active])-1)).abs().max())
            checks.append({'family':family,'name':name,'check':'net reconciles to fee-adjusted gross capital',
                           'passed':bool(error<1e-12),'max_abs_error':error})
    else: item['reason']='No completed current real run / ledger available; do not reuse inherited output as corrected.'
    items.append(item)
    return item

groups=[('eps','eps_momentum','results/eps_momentum/summary.csv'),
        ('sma','sma200_overlay','results/ml/sma200_overlay_summary.csv'),
        ('composite','composite3','results/ml/composite3_summary.csv'),
        ('roe','mom30_roe','results/ml/mom30roe_summary.csv'),
        ('tech','tech_only','results/ml/tech_only_summary.csv')]
for task,family,summary in groups:
    table=pd.read_csv(SRC/summary)
    for name in table.strategy.unique():
        gross=name in ('SPY','XLK')
        if family=='eps_momentum': ledger='results/eps_momentum/monthly_'+('SPY' if gross else safe(name,50))+'.csv'
        elif family=='sma200_overlay': ledger='results/ml/sma200_'+safe(name)+'.csv'
        elif family=='composite3' and 'composite' in name: ledger='results/ml/composite3_'+safe(name)+'.csv'
        elif family=='mom30_roe' and 'top-30' in name: ledger='results/ml/mom30roe_'+safe(name,50)+'.csv'
        elif family=='tech_only' and name.startswith('tech'): ledger='results/ml/tech_'+safe(name,45)+'.csv'
        elif family=='tech_only' and gross: ledger='results/ml/tech_BENCH_'+name+'.csv'
        elif gross: ledger='results/ml/sma200_SPY.csv'
        else: ledger='results/ml/sma200_'+safe('pure momentum top-1' if name=='all S&P: momentum top-1' else name)+'.csv'
        item=add(family,name,summary,ledger,task,cost='gross benchmark (no transaction cost)' if gross else '10 bp/side, actual drifted turnover, fees before investment')
        if item['ledger_path']:
            d=read_ledger(ROOT/item['ledger_path'])
            for row in table[table.strategy==name].itertuples():
                a,b=period_bounds(row.period)
                returns=d.loc[a:b].net.dropna()
                ca,dd=independent_stats(returns)
                err=max(abs(ca-row.CAGR),abs(dd-row.maxDD))
                checks.append({'family':family,'name':name,'check':'summary independently recomputed','period':row.period,
                               'passed':bool(err<1e-10),'max_abs_error':float(err)})

table=pd.read_csv(SRC/'results/factor_combo/combo_table.csv')
for row in table.itertuples():
    role='fixed literature combination' if row.combo.startswith('A') else ('annual walk-forward fitted model, labels purged' if row.combo.startswith('B') else 'interaction selected on 2010-2015 then retrospectively evaluated from 2016')
    item=add('factor_combo',row.combo,'results/factor_combo/combo_table.csv','results/factor_combo/monthly_'+safe(row.combo)+'.csv','combo',role)
    if item['ledger_path']:
        d=read_ledger(ROOT/item['ledger_path'])
        ca,_=independent_stats(d.loc[d.period=='eval'].net)
        checks.append({'family':'factor_combo','name':row.combo,'check':'eval annual return independently recomputed',
                       'passed':bool(abs(ca-row.top10_net_ann)<1e-10),'max_abs_error':float(abs(ca-row.top10_net_ann))})
for name in ['SPY','EW_universe']:
    add('factor_combo','BENCH '+name,None,f'results/factor_combo/monthly_BENCH_{name}.csv','combo','same-cost benchmark')
old_combo=ROOT.parent/'2026-10-30_codex_audited_modified/research/sector_stock_momentum/results/factor_combo/combo_table.csv'
if old_combo.exists():
    retired=sorted(set(pd.read_csv(old_combo).combo)-set(table.combo))
    for name in retired:
        items.append({'family':'factor_combo','name':name,'summary_path':rel(SRC/'results/factor_combo/combo_table.csv'),
                      'ledger_path':None,'frequency':'monthly','execution':'month-end close','cost':'10bp/side',
                      'evidence_role':'retired inherited interaction-search result','limitations':common_limits,
                      'run_task':'combo','run_exit_code':latest.get('combo',{}).get('exit_code'),
                      'run_log':latest.get('combo',{}).get('log'),
                      'audit_status':'AUDITED_NOT_SELECTED_BY_CORRECTED_FROZEN_SEARCH',
                      'reason':'The unchanged search rule selected different interactions after PIT/label corrections; inherited performance is not a corrected result.'})

table=pd.read_csv(SRC/'results/ndx/summary.csv')
for name in table.strategy.unique():
    ledger='results/ndx/monthly_'+('SPY_full' if name=='SPY' else safe(name))+'.csv'
    item=add('ndx_expand',name,'results/ndx/summary.csv',ledger,'ndx',
        role='fixed-factor selection sample included before 2023' if name.startswith('C ') else 'retrospective rule replay',
        cost='gross benchmark (no transaction cost)' if name in ('SPY','XLK') else '10 bp/side, actual drifted turnover, fees before investment',
        limitations=['Nasdaq cached membership assembly matches frozen third-party YAML; not official index constituent certification.'])
    if item['ledger_path'] and 'CAGR' in table:
        d=read_ledger(ROOT/item['ledger_path'])
        for row in table[table.strategy==name].itertuples():
            a,b={'IS':('2009-01-01','2021-05-31'),'OOS':('2021-06-01','2026-09-30'),'FULL':('2009-01-01','2026-09-30')}.get(row.period,(None,None))
            if a is None: a,b=period_bounds(row.period)
            ca,dd=independent_stats(d.loc[a:b].net.dropna())
            error=max(abs(ca-row.CAGR),abs(dd-row.maxDD_month_end))
            checks.append({'family':'ndx_expand','name':name,'period':row.period,'check':'summary independently recomputed',
                           'passed':bool(error<1e-10),'max_abs_error':float(error)})

screen=pd.read_csv(SRC/'results/factor_screen/screen_table.csv')
for row in screen.itertuples():
    items.append({'family':'factor_screen','name':row.factor,'summary_path':rel(SRC/'results/factor_screen/screen_table.csv'),
                  'ledger_path':None,'frequency':'monthly cross-sectional signal study','execution':'none; no executable portfolio return claimed',
                  'cost':'not applicable','evidence_role':'factor inference using fixed development window and corrected multiple tests',
                  'limitations':common_limits,'run_task':'screen','run_exit_code':latest.get('screen',{}).get('exit_code'),
                  'run_log':latest.get('screen',{}).get('log'),'audit_status':'WRITER_COMPLETE_PENDING_INDEPENDENT_REVIEW',
                  'reason':'Signal research, not an investment strategy; CAGR does not apply.'})

(AUDIT/'factors_strategy_index.json').write_text(json.dumps(items,ensure_ascii=False,indent=2))
(AUDIT/'factors_result_verification.json').write_text(json.dumps({'checks':checks,'passed':all(x['passed'] for x in checks),
     'strategy_records':len(items),'portfolio_records':sum(x['ledger_path'] is not None for x in items)},ensure_ascii=False,indent=2))
owned=['eps_momentum.py','composite3.py','mom30_roe.py','sma200_overlay.py','tech_only.py','factor_screen.py','factor_combo.py','ndx_expand.py']
findings=[
 {'id':'FCT01','files':['sma200_overlay.py','composite3.py','tech_only.py','eps_momentum.py','factor_combo.py'],
  'defect':'End-of-period subtraction can make an unlevered total loss worse than -100%; constant 20bp basket fee ignores actual turnover.',
  'correction':'Shared self-financing, drift-aware ledger; exact total-loss cap and no trading after insolvency.',
  'evidence':'factors_gate.json: inherited loss -1.001, corrected -1, then zero returns'},
 {'id':'FCT02','files':['sma200_overlay.py','composite3.py','tech_only.py','factor_combo.py'],
  'defect':'Filtering away every candidate omitted months and compressed CAGR time.',
  'correction':'Keep the complete formation calendar and cash months; validate consecutive monthly dates.',
  'evidence':'factors_gate.json: filtered_empty_month_is_cash'},
 {'id':'FCT03','files':['eps_momentum.py'],
  'defect':'Protected EPS growth remained missing when prior margin became public after EPS.',
  'correction':'Protected factor has its own combined publication date; ordinary EPS is not delayed.',
  'evidence':'factors_gate.json: eps_protected_uses_its_own_public_date'},
 {'id':'FCT04','files':['eps_momentum.py','mom30_roe.py','factor_screen.py'],
  'defect':'Late reports for old quarters could overwrite newer known periods; undefined latest ratios could revive older valid ones.',
  'correction':'Latest fiscal updates only; retain explicitly undefined new ratios as missing.',
  'evidence':'factors_gate.json: late_old_fiscal_report_cannot_overwrite_newer and latest_undefined_ratio_invalidates_old_ratio'},
 {'id':'FCT05','files':['factor_screen.py','factor_combo.py'],
  'defect':'Rolling training admitted labels completing at first test formation; combo also admitted pre-2010 training.',
  'correction':'Require label end strictly before first test formation and start 2010-01; purge interaction search December 2015 label.',
  'evidence':'factors_gate.json: strict_label_cutoff_and_training_start'},
 {'id':'FCT06','files':['factor_screen.py'],
  'defect':'Retrospective December 2019 entered the development-year direction consistency test.',
  'correction':'Calculate verdict only from development IC and label dev/retro yearly columns separately.',
  'evidence':'factors_gate.json: retro_december_cannot_flip_dev_year'},
 {'id':'FCT07','files':['factor_screen.py','factor_combo.py'],
  'defect':'Unknown source/terminal outcomes were usable zero-return learning labels.',
  'correction':'Exclude unknown labels from inference/training; preserve tradable formation rows and explicitly assumed portfolio outcomes.',
  'evidence':'label_resolved in corrected base panel and source masks in monthly_ic/walk_forward/pair_search'},
 {'id':'FCT08','files':['factor_combo.py'],
  'defect':'EW comparison was gross; specified SPY benchmark absent; concatenating eval/retro ledgers reset holdings at boundary.',
  'correction':'Actual-turnover cost for EW and SPY; continuous ledger through evaluation/retrospective boundary then slice statistics.',
  'evidence':'factors_gate.json: eval_retro_boundary_must_preserve_positions'},
 {'id':'FCT09','files':['ndx_expand.py'],
  'defect':'S&P reproduction check merely printed mismatch, imported cached factor selection, saved rounded metrics and overwrote long SPY ledger.',
  'correction':'Mandatory mismatch failure; dynamic final frozen selection; exact numeric metrics; retain full-window SPY; reject conflicting CIK windows.',
  'evidence':'factors_ndx_13.log: all 213 picks identical, max net difference 9.71e-17'},
 {'id':'FCT10','files':['factor_screen.py'],
  'defect':'Degenerate constant-factor standard errors could yield invalid bootstrap handling.',
  'correction':'Mark zero/invalid SE untestable with adjusted p=1; use finite Monte Carlo plus-one correction.',
  'evidence':'factors_gate.json: constant_factor_not_false_significant'},
 {'id':'FCT11','files':['factor_combo.py'],
  'defect':'Main candidate source still excluded NaN future returns before formation ranking (found by root independent review).',
  'correction':'Remove future-return eligibility condition; retain statistical label filtering. Selected unpriceable winners now fail in the ledger instead of substituting another candidate.',
  'evidence':'factors_candidate_equivalence.json: real panel has zero NaN returns; exact old/new candidate frames match all 99455 rows. Two new gate counterexamples pass; saved result hashes retained without unnecessary retraining.'},
]
report={'status':'WRITER_COMPLETE_PENDING_INDEPENDENT_REVIEW' if all(x['passed'] for x in checks) else 'WRITER_VERIFICATION_FAILED',
 'written_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'source_data_certification':'PARTIAL / not certified',
 'scope':owned,'modified_files':[{'path':rel(SRC/f),'sha256':sha(SRC/f)} for f in owned],
 'tests':['audit_v2/factors_gate.json','audit_v2/factors_ndx_source_check.json','audit_v2/factors_result_verification.json','audit_v2/factors_candidate_equivalence.json'],
 'findings':findings,'runs_latest':{t:r for t,r in latest.items()},
 'entry_dispositions':[
   {'entry':f,'status':'REAL_RUN_COMPLETED_PENDING_REVIEW' if latest.get(t,{}).get('exit_code')==0 else 'BLOCKED',
    'task':t,'exit_code':latest.get(t,{}).get('exit_code'),'log':latest.get(t,{}).get('log')}
    for f,t in [('eps_momentum.py','eps'),('sma200_overlay.py','sma'),('composite3.py','composite'),('mom30_roe.py','roe'),
                ('tech_only.py','tech'),('factor_screen.py build','screen_build'),('factor_screen.py screen','screen'),
                ('factor_combo.py','combo'),('ndx_expand.py','ndx')]],
 'strategy_index':'audit_v2/factors_strategy_index.json','run_history':'audit_v2/factors_runs.json',
 'preserved_failed_or_superseded_runs':'Earlier runs are retained in run history/archive. Only latest successful per task is final evidence.',
 'blockers':common_limits+['No official historical Nasdaq constituent/industry file certification.',
                         'Fixed explosive-factor variants include their selection sample before 2023 and cannot be ranked as clean out-of-sample across that interval.'],
 'source_to_result':'frozen cached prices / SEC / membership -> corrected timing and ledger -> real replay -> recomputed tables -> independent root review',
 'approval_owner':'root auditor; writer report is not approval'}
(AUDIT/'factors_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({'strategy_records':len(items),'portfolio_records':sum(x['ledger_path'] is not None for x in items),
                  'checks':len(checks),'failed':[x for x in checks if not x['passed']]},ensure_ascii=False,indent=2))
assert all(x['passed'] for x in checks)
