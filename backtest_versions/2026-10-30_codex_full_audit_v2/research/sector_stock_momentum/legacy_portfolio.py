"""Shared close-to-close ledger for the audited legacy monthly strategies.

The frozen strategy's targets are unchanged. Fees are paid before investing,
weights drift, months without eligible picks earn cash, and zero wealth stays
zero. Unknown terminal/source outcomes remain explicitly flagged assumptions.
"""
import json
import numpy as np
import pandas as pd
import backtest as bt
from portfolio_accounting import capital_after_costs


def _calendar(X, forms):
    if forms is None:
        forms = X.attrs.get('formation_calendar', sorted(X.t.unique()))
    dates = pd.DatetimeIndex(sorted(pd.to_datetime(forms)))
    if dates.has_duplicates:
        raise ValueError('formation calendar has duplicate months')
    if len(dates) and (not dates.is_month_end.all() or
                       not dates.equals(pd.date_range(dates.min(), dates.max(), freq='ME'))):
        raise ValueError('formation calendar must include every month-end; do not compress missing months')
    return dates


def run_portfolio(X, target_fn, rf, forms=None, cost=bt.COST_PER_SIDE):
    rows, previous, bankrupt = [], {}, False
    groups = {pd.Timestamp(t): g for t, g in X.groupby('t', sort=True)}
    for t in _calendar(X, forms):
        m = t + pd.offsets.MonthEnd(1)
        cash = float(rf.get(m, 0.0))
        if not np.isfinite(cash) or cash < -1:
            raise ValueError(f'{m}: invalid cash return')
        g = groups.get(t, X.iloc[:0])
        target = {} if bankrupt or g.empty else {s: float(w) for s, w in target_fn(g).items()}
        if any(not np.isfinite(w) or w < 0 for w in target.values()):
            raise ValueError('target weights must be finite and nonnegative')
        target = {s: w for s, w in target.items() if w > 0}
        if sum(target.values()) > 1 + 1e-10:
            raise ValueError('legacy ledger supports unlevered long-only targets')
        data = g.set_index('ticker')
        if data.index.has_duplicates:
            raise ValueError(f'{t}: duplicate security in panel')
        returns, status = {}, {}
        for s in target:
            r = float(data.at[s, 'fwd_ret'])
            if not np.isfinite(r) or r < -1:
                raise ValueError(f'{t} {s}: missing/invalid holding return; do not delete the selected stock')
            returns[s] = r
            status[s] = str(data.at[s, 'exit_status'])
        if bankrupt:
            capital, turnover, gross, net = 0.0, 0.0, 0.0, 0.0
        else:
            capital, turnover = capital_after_costs(target, previous, cost)
            gross = sum(target[s] * returns[s] for s in target) + (1 - sum(target.values())) * cash
            net = max(0.0, capital * (1 + gross)) - 1
            bankrupt = net <= -1
            previous = {s: target[s] * (1 + returns[s]) / (1 + gross)
                        for s in target if status[s] == 'ok'} if gross > -1 and not bankrupt else {}
        names = list(target)
        rows.append({'formation': t, 'month': m, 'pick': names[0] if len(names) == 1 else ('basket' if names else 'CASH'),
                     'picks': '|'.join(names), 'weights': '|'.join(format(target[s], '.17g') for s in names),
                     'asset_returns': json.dumps(returns, sort_keys=True), 'asset_status': json.dumps(status, sort_keys=True),
                     'exit_status': '|'.join(status[s] for s in names) if names else ('bankrupt' if bankrupt else 'cash'),
                     'gross': gross, 'net': net, 'turnover': turnover, 'capital_after_costs': capital,
                     'cash_return': cash, 'cost_per_side': cost, 'bankrupt': bankrupt,
                     'unresolved_outcomes': sum(v in ('unresolved', 'source_gap') for v in status.values())})
    return pd.DataFrame(rows).set_index('month')


def score_basket(D, col, n, rf, weight='ew', forms=None):
    def target(g):
        g = g.dropna(subset=[col])
        if weight == 'ivol':
            g = g[g.vol_3m.notna() & (g.vol_3m > 0)]
        g = g.sort_values([col, 'ticker'], ascending=[False, True]).head(n)
        if g.empty:
            return {}
        w = 1 / g.vol_3m.clip(lower=0.05) if weight == 'ivol' else pd.Series(1.0, index=g.index)
        w /= w.sum()
        return dict(zip(g.ticker, w))
    return run_portfolio(D, target, rf, forms=forms)


def apply_regime(df, bench_below, rf):
    """Recompute targets/costs after applying the formation-date cash filter."""
    rows, targets = [], {}
    for m, row in df.iterrows():
        t = m - pd.offsets.MonthEnd(1)
        if 'asset_returns' not in row:
            # Only single-asset, uncosted benchmark inputs can be reconstructed.
            if row.get('pick') in (None, 'basket') or str(row.get('pick')).startswith('CASH'):
                raise ValueError('regime requires asset-level ledger, not rounded aggregate net returns')
            returns = {row['pick']: float(row.get('gross', row.net))}
            status = {row['pick']: 'ok'}
            target = {row['pick']: 1.0}
        else:
            returns = json.loads(row.asset_returns)
            status = json.loads(row.asset_status)
            names = row.picks.split('|') if isinstance(row.picks, str) and row.picks else []
            target = dict(zip(names, map(float, str(row.weights).split('|')))) if names else {}
        targets[t] = {} if bench_below.get(t, False) else target
        for s, r in returns.items():
            rows.append({'t': t, 'ticker': s, 'fwd_ret': r, 'exit_status': status[s]})
    X = pd.DataFrame(rows, columns=['t', 'ticker', 'fwd_ret', 'exit_status'])
    out = run_portfolio(X, lambda g: targets[g.t.iloc[0]], rf,
                        forms=df.index - pd.offsets.MonthEnd(1))
    out.loc[[bool(bench_below.get(t, False)) for t in out.formation], 'pick'] = 'CASH(regime)'
    return out
