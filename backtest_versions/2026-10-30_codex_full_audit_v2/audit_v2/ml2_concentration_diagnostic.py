"""ML2_SPEC §7 diagnostic of the 17 frozen, final monthly selections.

No model fitting, reselection, new parameter search or source writes. First
reconcile every original monthly return/cost against panel_ml2, then report
concentration and frozen-target sensitivities. Run --self-test before --run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / 'research/sector_stock_momentum'
INPUT = HOME / 'results/ml2'
OUT = ROOT / 'audit_v2'
COST = .001
CALENDAR = pd.date_range('2015-01-31', '2026-09-30', freq='ME')
NAMES = [f'{group}-{kind} Top{k}' for kind in ['ridge', 'lgbm']
         for group in 'ABC' for k in [1, 3]] + [
    'BENCH momentum Top1', 'BENCH momentum Top3',
    'BENCH full-universe C-lgbm Top1', 'BENCH full-universe C-lgbm Top3', 'BENCH SPY']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fee_capital(target, previous, rate=COST):
    """Self-financing fee equation k + c * sum(|k*w_target-w_old|) = 1."""
    if not 0 <= rate < 1 or any(not np.isfinite(v) or v < 0 for v in [*target.values(), *previous.values()]):
        raise ValueError('Invalid long-only cost/weights')
    if sum(target.values()) > 1 + 1e-12:
        raise ValueError('This diagnostic covers the original unlevered ML2 lines only')
    keys = set(target) | set(previous)
    turn = lambda k: sum(abs(k * target.get(s, 0) - previous.get(s, 0)) for s in keys)
    if rate * turn(0) >= 1:
        return 0., turn(0)
    lo, hi = 0., 1.
    for _ in range(64):
        mid = (lo + hi) / 2
        if mid + rate * turn(mid) > 1:
            hi = mid
        else:
            lo = mid
    k = (lo + hi) / 2
    return k, turn(k)


def targets(row):
    picks = [] if pd.isna(row.picks) or not str(row.picks) else str(row.picks).split('|')
    weights = [] if pd.isna(row.weights) or not str(row.weights) else [float(x) for x in str(row.weights).split('|')]
    if len(picks) != len(weights) or len(set(picks)) != len(picks):
        raise ValueError('Picks/weights mismatch or duplicate ticker')
    e = float(row.exposure)
    if picks and not np.isclose(sum(weights), 1., atol=1e-12):
        raise ValueError('Stored relative weights do not sum to one')
    if not picks and e != 0:
        raise ValueError('Nonzero exposure without picks')
    return {s: w * e for s, w in zip(picks, weights)}


def replay(schedule, lookup, cash_rates, removed=None):
    """Frozen target weights; removed ticker's weight stays cash, never redistributed."""
    previous, nav, rows, stock_rows = {}, 1., [], []
    for month, original in schedule.items():
        if nav <= 0:
            rows.append(dict(month=month, net=0., gross=0., turnover=0., capital_after_costs=0.,
                             nav_start=0., nav_end=0., fee_pnl=0., stock_pnl=0., cash_pnl=0.,
                             net_pnl=0., exposure=0.))
            continue
        target = {s: w for s, w in original.items() if s != removed and w != 0}
        if any(not np.isfinite(w) or w < 0 for w in target.values()) or sum(target.values()) > 1 + 1e-12:
            raise ValueError('Invalid target weight')
        cash = max(0., 1 - sum(target.values()))
        rf = float(cash_rates.loc[month])
        if not np.isfinite(rf):
            raise ValueError(f'Missing formation-known cash rate for {month}')
        rets = {s: lookup(month, s) for s in target}
        if any(not np.isfinite(ret) or ret < -1 for ret, _ in rets.values()):
            raise ValueError(f'Missing or impossible holding return at {month}')
        gross = sum(target[s] * rets[s][0] for s in target) + cash * rf
        k, turnover = fee_capital(target, previous)
        net = max(0., k * (1 + gross)) - 1
        fee_pnl, cash_pnl = nav * (k - 1), nav * k * cash * rf
        stock_pnl = 0.
        for ticker, weight in target.items():
            contribution = nav * k * weight * rets[ticker][0]
            stock_pnl += contribution
            stock_rows.append(dict(month=month, ticker=ticker, target_weight=weight,
                                   holding_return=rets[ticker][0], status=rets[ticker][1],
                                   nav_start=nav, capital_after_costs=k, contribution=contribution))
        nav_end = nav * (1 + net)
        if not np.isclose(nav_end - nav, stock_pnl + cash_pnl + fee_pnl, atol=1e-10, rtol=1e-10):
            raise ValueError('Contribution decomposition does not reconcile wealth change')
        rows.append(dict(month=month, net=net, gross=gross, turnover=turnover, capital_after_costs=k,
                         nav_start=nav, nav_end=nav_end, fee_pnl=fee_pnl, stock_pnl=stock_pnl,
                         cash_pnl=cash_pnl, net_pnl=nav_end-nav, exposure=sum(target.values())))
        previous = {s: target[s] * (1 + rets[s][0]) / (1 + gross)
                    for s in target if rets[s][1] == 'ok'} if gross > -1 else {}
        nav = nav_end
    return pd.DataFrame(rows).set_index('month'), pd.DataFrame(stock_rows)


def measures(returns):
    returns = pd.Series(returns, dtype=float)
    if returns.empty or returns.isna().any() or (returns < -1).any():
        raise ValueError('Invalid return sample')
    wealth = (1 + returns).cumprod()
    return dict(annualized_geometric_rate=float(wealth.iloc[-1] ** (12/len(returns)) - 1),
                monthly_mdd=float((wealth / wealth.cummax().clip(lower=1) - 1).min()),
                growth_factor=float(wealth.iloc[-1]), months=int(len(returns)))


def self_test():
    checks = []
    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
    k, turn = fee_capital({'A': 1.}, {})
    check('Initial buy is self financing', abs(k - 1/1.001) < 1e-14 and abs(k + COST*turn - 1) < 1e-14)
    dates = pd.date_range('2020-01-31', periods=3, freq='ME')
    schedule = {m: {'A': .5, 'B': .5} for m in dates}
    rates = pd.Series(.01, index=dates)
    lookup = lambda month, ticker: ((1. if month == dates[0] and ticker == 'A' else 0.), 'ok')
    base, stocks = replay(schedule, lookup, rates)
    check('Contribution uses initial wealth times post-fee capital', abs(stocks.iloc[0].contribution - .5/1.001) < 1e-14)
    expected_drift = {'A': 2/3, 'B': 1/3}
    drift_k, drift_turn = fee_capital(schedule[dates[1]], expected_drift)
    check('Rebalance charges drifted holdings', abs(base.iloc[1].turnover - drift_turn) < 1e-14 and drift_turn > .3)
    removed, removed_stocks = replay(schedule, lookup, rates, removed='A')
    check('Removed ticker is never replaced or renormalized', set(removed_stocks.ticker)=={'B'} and removed_stocks.target_weight.eq(.5).all())
    check('Removed weight earns same cash carry', abs(removed.iloc[0].gross-.005)<1e-14)
    check('Removal recomputes costs rather than retaining old fee', abs(removed.iloc[0].capital_after_costs - 1/1.0005)<1e-14)
    terminal = lambda month, ticker: (.1 if month == dates[0] else 0., 'delisted_in_month' if month == dates[0] else 'ok')
    terminal_run, _ = replay({m:{'A':1.} for m in dates}, terminal, rates)
    check('Terminal holdings become cash before next rebalance', abs(terminal_run.iloc[1].turnover - 1/1.001)<1e-14)
    bankrupt, _ = replay({m:{'A':1.} for m in dates}, lambda m,s:(-1. if m==dates[0] else 5.,'ok'),rates)
    check('Bankruptcy absorbs wealth without resurrection', bankrupt.nav_end.eq(0).all())
    check('Initial capital included in drawdown', abs(measures([-.4,0])['monthly_mdd']+.4)<1e-14)
    # Taking out a good year must not silently create a continuous-portfolio CAGR.
    x=pd.Series([.1,.2,-.1,.05],index=pd.to_datetime(['2020-01-31','2020-12-31','2021-01-31','2022-01-31']))
    year=(1+x).groupby(x.index.year).prod()-1;best=int(year.idxmax());retained=x[x.index.year!=best]
    check('Best year removal retains original surviving returns',best==2020 and retained.tolist()==[-.1,.05])
    return {'status':'PASS','checks':checks}


def run():
    # Parent closes this record only after the final complete ML2 process exits.
    completion_path=OUT/'root_closeout_runs.json'
    completion=json.loads(completion_path.read_text())
    final=[r for r in completion if r['name']=='ml2_complete' and r['exit']==0]
    if not final:
        raise ValueError('Final ML2 run is not yet recorded complete; refusing stale artifacts')
    for name in ['ml2_run.py','backtest.py','winners_tracks.py','portfolio_accounting.py']:
        if final[-1]['source_hashes'][name] != sha(HOME/name):
            raise ValueError(f'Final run source hash no longer matches {name}')
    panel_path=INPUT/'panel_ml2.parquet';rf_path=HOME/'data/fred_DGS3MO.json'
    if not rf_path.exists():
        raise ValueError('Frozen cash rate missing; dashboard fallback is forbidden')
    paths=[panel_path,rf_path,completion_path]
    ledgers={}
    for name in NAMES:
        path=INPUT/('monthly_'+''.join(c if c.isalnum() else '_' for c in name)+'.csv')
        paths.append(path)
        ledgers[name]=pd.read_csv(path,index_col='month',parse_dates=True)
        if not ledgers[name].index.equals(CALENDAR):
            raise ValueError(f'{name}: missing or unexpected holding months')
    before={str(p.relative_to(ROOT)):sha(p) for p in paths}
    panel=pd.read_parquet(panel_path,columns=['t','ticker','ret_oo','status_oo'])
    if panel.duplicated(['t','ticker']).any():
        raise ValueError('Duplicate (formation,ticker) holding labels')
    labels=panel.set_index(['t','ticker'])[['ret_oo','status_oo']].to_dict('index')
    # This import's load_rf only reads the already verified frozen JSON above.
    sys.path.insert(0,str(HOME))
    import backtest as bt
    if bt.COST_PER_SIDE != COST:
        raise ValueError('Frozen fee changed')
    rates=bt.load_rf(CALENDAR)
    spy=ledgers['BENCH SPY']['gross']
    def lookup(month,ticker):
        if ticker=='SPY':
            return float(spy.loc[month]),'ok'
        v=labels.get((month-pd.offsets.MonthEnd(1),ticker))
        if v is None:
            raise ValueError(f'Missing panel label: {month} {ticker}')
        return float(v['ret_oo']),str(v['status_oo'])
    verified={};checks=[]
    for name, original in ledgers.items():
        schedule={month:targets(row) for month,row in original.iterrows()}
        base,stocks=replay(schedule,lookup,rates)
        errors={col:float(np.max(np.abs(base[col]-original[col])))
                for col in ['net','gross','turnover','capital_after_costs','exposure']}
        if any(value>1e-10 for value in errors.values()):
            raise ValueError(f'{name}: original ledger reconciliation failed: {errors}')
        checks.append({'strategy':name,'months':len(base),'max_abs_errors':errors})
        verified[name]=(schedule,base,stocks)
    # Sensitivities are only computed after ALL 17 original ledgers reconcile.
    summary=[];all_stocks=[];all_months=[];all_sensitivity=[]
    for name,(schedule,base,stocks) in verified.items():
        grouped=stocks.groupby('ticker').contribution.sum().sort_values(ascending=False)
        largest=str(grouped.index[0]);contrib=float(grouped.iloc[0])
        original=measures(base.net);profit=float(base.nav_end.iloc[-1]-1)
        removed,_=replay(schedule,lookup,rates,removed=largest);removed_metrics=measures(removed.net)
        annual=(1+base.net).groupby(base.index.year).prod()-1
        best_year=int(annual.idxmax());best_month=base.net_pnl.idxmax();return_month=base.net.idxmax()
        retained=base.loc[base.index.year!=best_year]
        retained_metrics=measures(retained.net)
        summary.append(dict(strategy=name,months=len(base),start=str(base.index[0].date()),end=str(base.index[-1].date()),
            base_cagr=original['annualized_geometric_rate'],base_monthly_mdd=original['monthly_mdd'],base_final_wealth=original['growth_factor'],
            total_net_profit=profit,largest_contributor=largest,largest_stock_contribution=contrib,
            largest_stock_share_of_net_profit=contrib/profit if profit!=0 else None,
            largest_month=str(best_month.date()),largest_month_contribution=float(base.loc[best_month,'net_pnl']),
            largest_month_share_of_net_profit=float(base.loc[best_month,'net_pnl'])/profit if profit!=0 else None,
            highest_return_month=str(return_month.date()),highest_monthly_return=float(base.loc[return_month,'net']),
            without_largest_stock_cagr=removed_metrics['annualized_geometric_rate'],
            without_largest_stock_cagr_difference=removed_metrics['annualized_geometric_rate']-original['annualized_geometric_rate'],
            without_largest_stock_monthly_mdd=removed_metrics['monthly_mdd'],without_largest_stock_final_wealth=removed_metrics['growth_factor'],
            best_year=best_year,best_year_return=float(annual.loc[best_year]),best_year_months=int(sum(base.index.year==best_year)),
            retained_months_without_best_year=len(retained),
            without_best_year_sample_geometric_rate=retained_metrics['annualized_geometric_rate'],
            without_best_year_retained_return_product=retained_metrics['growth_factor'],
            without_best_year_status='NONCONTIGUOUS_SAMPLE_DIAGNOSTIC_NOT_PORTFOLIO_CAGR'))
        all_stocks.append(grouped.rename('contribution').reset_index().assign(strategy=name,share_of_net_profit=lambda d:d.contribution/profit if profit!=0 else np.nan))
        all_months.append(base.reset_index().assign(strategy=name))
        all_sensitivity.append(removed.reset_index().assign(strategy=name,variant='remove_largest_stock_to_same_rate_cash',removed=largest))
        all_sensitivity.append(retained.reset_index().assign(strategy=name,variant='exclude_best_year_original_returns_noncontinuous',removed=str(best_year)))
    after={str(p.relative_to(ROOT)):sha(p) for p in paths}
    if before!=after:
        raise ValueError('Inputs changed during diagnostic; no outputs admitted')
    outputs={
        'ml2_concentration_summary.csv':pd.DataFrame(summary),
        'ml2_concentration_stock_contributions.csv':pd.concat(all_stocks,ignore_index=True),
        'ml2_concentration_month_contributions.csv':pd.concat(all_months,ignore_index=True),
        'ml2_concentration_sensitivity_monthly.csv':pd.concat(all_sensitivity,ignore_index=True)}
    for name,frame in outputs.items():
        frame.to_csv(OUT/name,index=False)
    result=dict(status='RECONCILED_DIAGNOSTICS_AWAITING_PARENT_REVIEW',strategies=len(checks),verified_months=sum(c['months'] for c in checks),
        original_ledger_checks=checks,inputs_sha256=before,script_sha256=sha(Path(__file__)),
        outputs_sha256={name:sha(OUT/name) for name in outputs},self_tests=self_test(),
        definitions={
            'stock_contribution':'Sum over months of wealth before month * capital_after_costs * original target weight * actual holding return; costs shown separately, not allocated to stocks.',
            'month_contribution':'Dollar wealth change relative to initial capital 1: pre-month wealth times net monthly return. Highest percentage-return month also reported.',
            'contribution_identity':'Sum stock contributions + cash carry contributions + negative fee contributions = final wealth - initial wealth.',
            'share':'Contribution divided by total net profit; can be negative or exceed 100% because losses/costs offset gains.',
            'remove_stock':'The retrospectively largest-contribution ticker gets zero weight in every frozen original target. All other original weights are unchanged; residual cash uses original formation-known DGS3MO monthly rates; fees and drift recomputed. No replacements or model fitting.',
            'remove_year':'Choose highest original calendar-year compound return, retaining partial final year as-is. Remove its months from the original return sample; no boundary fee/capital reconstruction. Report retained-month geometric rate, never a continuous portfolio CAGR.',
            'SPY':'SPY holding return is the original benchmark gross ledger return; original costs independently reconstructed. This is accounting reconciliation, not independent raw-price verification.',
            'ret_oo':'All non-SPY holding outcomes and terminal statuses are frozen panel_ml2 labels; inherits their source and execution limitations.',
            'drawdown':'Monthly wealth marks only; no daily path claimed.',
            'interpretation':'Descriptive sensitivity selected after seeing history, not a newly investable or independently tested strategy.'})
    (OUT/'ml2_concentration_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
    print(json.dumps({'status':result['status'],'strategies':len(checks),'verified_months':result['verified_months'],'outputs':list(outputs)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--self-test',action='store_true');parser.add_argument('--run',action='store_true');args=parser.parse_args()
    if args.self_test:
        result=self_test();(OUT/'ml2_concentration_self_tests.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
    elif args.run:
        try:
            run()
        except Exception as exc:
            (OUT/'ml2_concentration_checks.json').write_text(json.dumps({'status':'BLOCKED_RECONCILIATION_OR_INPUT_GATE','error':repr(exc),'sensitivity_outputs_admitted':False},indent=2))
            raise
    else:
        parser.error('Specify --self-test or --run')
