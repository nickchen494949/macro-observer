"""Index root-owned stock strategies without rerunning strategies or touching inputs.

Legacy rows are exact mappings to the earlier 340-row inventory. Current runs
must have an exit-0 record; ML2/main must also match the relevant current code
hash. Stale files for blocked or pending rows are never usable ledgers.
"""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
AUD = ROOT / 'audit_v2'
SRC = ROOT / 'research/sector_stock_momentum'
RES = SRC / 'results'
parser = argparse.ArgumentParser()
parser.add_argument('--legacy-data', type=Path, default=ROOT.parents[1] / 'outputs/backtest_strategy_table_20261030/work/data.json')
args = parser.parse_args()
legacy = json.loads(args.legacy_data.read_text())
sources = {x['id']: x['path'] for x in legacy['sources']}
FAMILIES = {'行业与个股动量': ('main', 13), '机器学习第二版 ML2': ('ml2', 17),
            '赢家股策略': ('winners', 57), '非标普留出测试': ('holdout', 17),
            '非标普留出测试 STRICT': ('holdout_strict', 17), '非标普股票压力测试': ('old_fixedstress', 1)}

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def relative(p):
    return str(p.relative_to(ROOT))

def read_json(p, default):
    return json.loads(p.read_text()) if p.exists() else default

records = []
for file in ['root_runs.json', 'root_dependent_runs.json', 'root_final_execution_runs.json', 'root_closeout_runs.json']:
    for r in read_json(AUD / file, []):
        records.append({**r, 'registry': 'audit_v2/' + file})

def run_record(family):
    name = {'main':'main_final', 'ml2':'ml2_complete', 'winners':'winners_final', 'holdout':'holdout', 'holdout_strict':'holdout_strict'}[family]
    found = [r for r in records if r.get('name') == name]
    if not found:
        return None, 'PENDING_FINAL_RUN', 'No completed current-run record; existing CSV may be inherited or superseded.'
    r = found[-1]
    if r.get('exit') != 0:
        return r, 'RUN_FAILED', f'Actual run exit {r.get("exit")}; see log.'
    relevant = {'main':['backtest.py'], 'ml2':['backtest.py','ml2_run.py','ml2_features.py'],
                'winners':['winners_tracks.py'], 'holdout':['winners_holdout.py','smallcap_universe.py','smallcap_data_audit.py'],
                'holdout_strict':['winners_holdout.py','smallcap_universe.py','smallcap_data_audit.py']}[family]
    def recorded_hash(record,n):
        hashes=record.get('source_hashes',{})
        return hashes.get(relative(SRC/n),hashes.get(n))
    mismatch = [n for n in relevant if recorded_hash(r,n) != digest(SRC/n)]
    if family in ['main','holdout','holdout_strict']:
        refreshes=[x for x in records if x.get('name')=='daily_refresh' and x.get('exit')==0]
        proof=read_json(AUD/'root_daily_refresh.json',{})
        if not refreshes or proof.get('status')!='PASS' or not all(x.get('monthly_sha256_unchanged') for x in proof.get('checks',[])):
            return r, 'PENDING_DAILY_REFRESH', 'Monthly rerun completed; final missing-quote daily-risk refresh not yet completed.'
        refresh=refreshes[-1]
        if any(recorded_hash(refresh,n)!=digest(SRC/n) for n in ['backtest.py','winners_tracks.py']):
            return r, 'PENDING_DAILY_REFRESH_SOURCE_CHANGED', 'Daily-risk refresh predates current price-path source.'
        r={**r,'daily_refresh_record':{k:v for k,v in refresh.items() if k!='source_hashes'},
           'daily_refresh_proof':'audit_v2/root_daily_refresh.json'}
        # Root's focused refresh asserts fixed monthly hashes and metrics, and
        # runs under the current missing-quote policy without changing trades.
        if family=='main' and mismatch==['backtest.py']:
            mismatch=[]
    if mismatch:
        return r, 'PENDING_FINAL_RUN_SOURCE_CHANGED', 'Completed record predates relevant current source: ' + ', '.join(mismatch)
    return r, 'COMPLETED_CACHE_REPLAY', None

def safe(name):
    return ''.join(c if c.isalnum() else '_' for c in name)

blocked = {x['strategy']: x for x in read_json(RES/'winners/blocked_strategies.json', [])}
COMMON = ['Historical replay of repeatedly examined data; not a new untouched prospective test.',
          'Cached membership, historical sectors, security identity, and terminal data remain incompletely source-certified.',
          'Month-end returns alone do not certify daily drawdown or live execution.']

def benchmark_ledger(symbol):
    """Export exact raw-cache month-end benchmark convention; verify summary CAGR."""
    raw = SRC / 'data/raw' / (symbol+'.json')
    j = read_json(raw, {})
    p = pd.Series(j['adjclose'], index=pd.to_datetime(j['dates']), dtype=float).sort_index()
    assert not p.index.duplicated().any() and (p.dropna() > 0).all()
    m = p.resample('ME').last()
    r = m.pct_change(fill_method=None).loc['2009-01-31':'2026-09-30']
    assert len(r) == 213 and r.notna().all()
    summary = read_json(RES/'summary.json', {})['summary'][f'Bench: {symbol}']['FULL_gross']
    cagr = (1+r).prod()**(12/len(r))-1
    assert np.isclose(cagr, summary['CAGR'], atol=1e-12), (symbol, cagr, summary['CAGR'])
    d = pd.DataFrame({'month':r.index, 'formation':r.index-pd.offsets.MonthEnd(1),
                      'gross':r.values,'net':r.values,'turnover':0.,'cost_per_side':0.,'picks':symbol})
    path = AUD / ('root_benchmark_'+symbol+'.csv')
    d.to_csv(path,index=False)
    return path, {'raw_path':relative(raw),'raw_sha256':digest(raw),
                  'derivation':'cached adjusted-close last observation per calendar month; consecutive month return; no trading cost',
                  'matches_current_summary_CAGR':True,'CAGR':float(cagr)}

def attach_ledger(row, path):
    if not path.exists():
        row.update(ledger_path=None, audit_status='MISSING_CURRENT_LEDGER', reason='Expected current output absent: '+relative(path))
        return
    d = pd.read_csv(path)
    datecol = 'month' if 'month' in d else d.columns[0]
    dates = pd.DatetimeIndex(pd.to_datetime(d[datecol]))
    assert len(dates) and dates.is_unique and dates.is_monotonic_increasing, path
    assert dates.equals(pd.date_range(dates[0], dates[-1],freq='ME')), f'Calendar gap: {path}'
    assert 'net' in d and np.isfinite(d.net).all() and (d.net >= -1-1e-12).all(), path
    row.update(ledger_path=relative(path), ledger_sha256=digest(path), sha256=digest(path),date_column=datecol,
               first_month=dates[0].date().isoformat(),last_month=dates[-1].date().isoformat(),months=len(d))
    if row['valid_comparison_start'] is None:
        row['valid_comparison_start'] = row['first_month']
    elif row['valid_comparison_start'] < row['first_month']:
        row['valid_comparison_start'] = row['first_month']
    row['summary_sha256'] = digest(ROOT/row['summary_path'])

out = []
for legacy_number, old in enumerate(legacy['inventory'], start=1):
    if old[0] not in FAMILIES:
        continue
    family = FAMILIES[old[0]][0]
    name = old[2]
    row = {'family':'root_'+family,'name':name,'legacy_name':name,'legacy_source':sources[old[9]],'legacy_source_id':old[9],
           'legacy_source_path':sources[old[9]],'legacy_family':old[0],'legacy_inventory_row':legacy_number,
           'legacy_display_name':old[1], 'summary_path':sources[old[9]], 'ledger_path':None,
           'frequency':'monthly target review and rebalance',
           'execution':'formation month-end close to next month-end close; idealized same-close signal execution',
           'cost':'0.10% per side on actual drifted turnover; fees paid before investment',
           'evidence_role':'retrospective cached-data replay','valid_comparison_start':None,
           'limitations':COMMON.copy(), 'run_status':None,'audit_status':None}
    if family == 'old_fixedstress':
        row.update(run_status='SUPERSEDED_DIAGNOSTIC',audit_status='SUPERSEDED_NO_CURRENT_LEDGER',
                   evidence_role='old post-hoc fixed-choice stress calculation; not a separately rerun strategy',
                   reason='No current dedicated fixed-choice ledger. Replaced for current diagnosis by the new full holdout -100% stress replay; the two calculations are not asserted identical.',
                   replacement={'family':'root_holdout','legacy_source':sources['S046'],'legacy_source_id':'S046',
                                'name':'BENCH pure momentum top-1 / stress −100 %'},
                   valid_comparison_start=None)
        out.append(row); continue
    record, status, reason = run_record(family)
    row.update(run_status=status,audit_status=status)
    if reason:
        row['reason'] = reason
    if record:
        row.update(run_task=record['name'],run_exit_code=record.get('exit'),run_log=record.get('log'),
                   run_registry=record['registry'])
        if record.get('daily_refresh_record'):
            row['daily_refresh_record']=record['daily_refresh_record']
            row['daily_refresh_proof']=record['daily_refresh_proof']
    if family == 'main':
        path = RES / ('monthly_'+safe(name)+'.csv')
        if 'next-day' in name:
            row['execution']='next trading-session close to next trading-session close; actual session quote required'
            row['limitations'].append('Manual terminal wealth rebased to actual entry; two stock-merger terminal wealth values still use successor month-end-close approximations.')
        if name.startswith('IS-selected'):
            row['valid_comparison_start']='2021-06-30'
            row['evidence_role']='parameter selected through 2021-04; pre-2021-06 results are selection/development evidence'
        if name.startswith('Bench:'):
            row['cost']='No trading cost in the frozen main benchmark convention; gross benchmark'
            row['frequency']='buy and hold benchmark, measured monthly'
            if status == 'COMPLETED_CACHE_REPLAY':
                path, proof = benchmark_ledger(name.split(': ')[1]); row['benchmark_derivation']=proof
            else:
                path = AUD / ('root_benchmark_'+name.split(': ')[1]+'.csv')
        if 'unresolved exits' in name:
            row['evidence_role']='unknown-terminal-outcome stress sensitivity; not another independent strategy'
    elif family == 'ml2':
        path = RES/'ml2'/('monthly_'+safe(name)+'.csv')
        row['valid_comparison_start']='2015-01-31'
        row['execution']='next trading-session adjusted open to next rebalance open; absent opens use next-session close on both legs; terminal exceptions explicitly modeled'
        row['limitations'] += ['No verified open-to-open daily NAV; daily drawdown unavailable.',
                              'Unknown/source-gap labels excluded from fitting and IC; validation/test candidates retained under explicit baseline/stress rules.',
                              'Two manual stock-merger terminal values are successor close approximations; largest-stock/best-year removal diagnostics not yet implemented.']
    elif family == 'winners':
        path = RES/'winners'/('monthly_'+safe(name)+'.csv')
        if name in blocked:
            row.update(ledger_path=None,audit_status='BLOCKED_DAILY_PATH',run_status='BLOCKED_DAILY_PATH',
                       reason=blocked[name]['reason'],blocked_record_path='research/sector_stock_momentum/results/winners/blocked_strategies.json')
            if path.exists():
                row['excluded_inherited_ledger_path']=relative(path)
                row['excluded_inherited_ledger_sha256']=digest(path)
            row['limitations'].append('Inherited ledger exists only as old evidence and is explicitly excluded; required daily volatility input cannot be verified.')
            out.append(row); continue
        if 'hold6m' in name:
            row['frequency']='monthly one-sixth tranche replacement; each tranche held six months, not full monthly rebalance'
        if name.startswith('T2'):
            row['limitations'].append('T2 first actual holding month is 2013-02; do not fabricate January 2013 or splice an earlier cash series.')
        row['limitations'].append('Unavailable daily path is reported separately; available monthly ledger does not imply daily risk proof.')
    else:
        strategy, scenario = name.rsplit(' / ',1)
        tag = '_STRICT' if family == 'holdout_strict' else ''
        path = RES/'winners_holdout'/('monthly_'+safe(strategy+' '+scenario)+tag+'.csv')
        if 'hold6m' in strategy:
            row['frequency']='monthly one-sixth tranche replacement; each tranche held six months, not full monthly rebalance'
        row['scenario']=scenario
        row['universe']='available liquid non-S&P; price >= $5 and 63-day median dollar volume >= $5m; no market-cap definition'
        row['limitations'] += ['Primary WIKI period ends 2018-02; post-2018 missing dead companies cause substantial survivorship bias.',
                              'Terminal loss stress on present names does not quantify companies absent from the universe.',
                              'Holdout suppresses all fundamentals under SPEC 5b; missing-fundamental patterns otherwise reveal future survival.']
        summary_path=ROOT/row['summary_path']
        if summary_path.exists():
            summary=pd.read_csv(summary_path)
            found=summary[(summary.strategy==strategy)&(summary.scenario==scenario)]
            if len(found) and 'list' in found:
                row['candidate_list']=str(found['list'].iloc[0])
        if family == 'holdout_strict':
            row['evidence_role']='ex-post price-quality sensitivity; future reversal/stale-run removal; excluded from live-strategy winner ranking'
            row['limitations'].append('STRICT uses future information in F1/F3 cleaning and is diagnostic only.')
        elif scenario.startswith('stress'):
            row['evidence_role']='unknown-terminal loss stress sensitivity on frozen candidate rule'
        elif row.get('candidate_list')=='supplementary (post-hoc)':
            row['evidence_role']='post-hoc supplementary frozen candidate; retrospective replay'
    row['expected_ledger_path']=relative(path)
    if status == 'COMPLETED_CACHE_REPLAY':
        # A leftover file alone is never evidence that this strategy was emitted
        # by the current run; require its exact key in the current summary too.
        if family=='main':
            assert name in read_json(RES/'summary.json',{})['summary'], name
        elif family in ['ml2','winners']:
            assert name in set(pd.read_csv(ROOT/row['summary_path']).strategy), name
        else:
            current=pd.read_csv(ROOT/row['summary_path'])
            assert ((current.strategy==strategy)&(current.scenario==scenario)).any(), name
        attach_ledger(row,path)
    elif path.exists():
        row['excluded_pending_or_superseded_ledger_path']=relative(path)
    out.append(row)

for family, (_, expected) in FAMILIES.items():
    assert sum(r['legacy_family']==family for r in out)==expected, family
assert len(out)==122
assert len({(r['legacy_source'],r['legacy_name']) for r in out})==len(out)
(AUD/'root_stock_strategy_index.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
verification={'legacy_inventory_path':str(args.legacy_data),'legacy_inventory_sha256':digest(args.legacy_data),
              'counts_by_family':dict(Counter(r['family'] for r in out)),
              'counts_by_status':dict(Counter(r['audit_status'] for r in out)),
              'current_usable_ledgers':sum(r['ledger_path'] is not None for r in out),
              'all_122_legacy_rows_mapped_exactly':True,
              'stale_blocked_files_excluded':True,
              'pending_rows':sum(str(r['audit_status']).startswith('PENDING') for r in out),
              'note':'Repeatable inventory binds actual completed run records and current summary keys. No strategy/source data edited or downloaded.'}
(AUD/'root_stock_index_verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2))
print(json.dumps(verification,ensure_ascii=False,indent=2))
