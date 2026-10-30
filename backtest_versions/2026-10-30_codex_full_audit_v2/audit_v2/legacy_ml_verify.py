"""Writer-side output checks; does not substitute independent review."""
import hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'research/sector_stock_momentum'
files = []
for pat in ['dev_*.csv', 'holdout_*.csv']:
    files += list((SRC / 'results/ml').glob(pat))
for pat in ['v1_*.csv', 'v2_*.csv', 'v3_*.csv', 'ear_monthly_*.csv']:
    files += list((SRC / 'results/explosive').glob(pat))
rows = []
for path in sorted(set(files)):
    d = pd.read_csv(path)
    if 'net' not in d:
        continue
    if 'month' not in d:
        d = d.rename(columns={d.columns[0]: 'month'})
    d['month'] = pd.to_datetime(d.month)
    assert not d.month.duplicated().any(), path
    expected = pd.date_range(d.month.min(), d.month.max(), freq='ME')
    assert list(d.month) == list(expected), path
    assert np.isfinite(d.net).all() and (d.net >= -1).all(), path
    previous, failed = {}, False
    if 'asset_returns' in d:
        for row in d.itertuples():
            names = row.picks.split('|') if isinstance(row.picks, str) and row.picks else []
            target = dict(zip(names, map(float, str(row.weights).split('|')))) if names else {}
            returns, states = json.loads(row.asset_returns), json.loads(row.asset_status)
            if failed:
                assert row.net == row.turnover == row.capital_after_costs == 0 and not target, path
                continue
            gross = sum(target[s] * returns[s] for s in target) + (1 - sum(target.values())) * row.cash_return
            turn = sum(abs(row.capital_after_costs * target.get(s, 0) - previous.get(s, 0))
                       for s in set(target) | set(previous))
            assert np.isclose(row.capital_after_costs + row.cost_per_side * turn, 1, atol=1e-11), path
            assert np.isclose(turn, row.turnover, atol=1e-11), path
            assert np.isclose(gross, row.gross, atol=1e-11), path
            assert np.isclose((1 + gross) * row.capital_after_costs - 1, row.net, atol=1e-11), path
            failed = row.net <= -1
            previous = {s: target[s] * (1 + returns[s]) / (1 + gross)
                        for s in target if states[s] == 'ok'} if gross > -1 else {}
    eq = np.r_[1.0, np.cumprod(1 + d.net)]
    rows.append({'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                 'months': len(d), 'first': str(d.month.min().date()), 'last': str(d.month.max().date()),
                 'CAGR': float(eq[-1] ** (12 / len(d)) - 1),
                 'month_end_maxDD': float(np.min(eq / np.maximum.accumulate(eq) - 1)),
                 'unresolved_outcomes': int(d.unresolved_outcomes.sum()) if 'unresolved_outcomes' in d else 0,
                 'asset_ledger_checked': 'asset_returns' in d})
risk = pd.read_csv(SRC / 'results/explosive/risk_report.csv')
statuses = risk.groupby('strategy').daily_nav_status.first().to_dict()
report = {'status': 'WRITER_CHECKS_PASS_PENDING_INDEPENDENT_REVIEW', 'ledgers': rows,
          'daily_nav_status': statuses,
          'risk_daily_metrics_with_unavailable_status': int((risk.daily_nav_status.str.startswith('UNAVAILABLE', na=False) & risk.maxDD_daily.notna()).sum())}
assert report['risk_daily_metrics_with_unavailable_status'] == 0
(ROOT / 'audit_v2/legacy_ml_verification.json').write_text(json.dumps(report, indent=2))
print(json.dumps({'checked_ledgers': len(rows), 'daily_status_counts': pd.Series(statuses).value_counts().to_dict()}))
