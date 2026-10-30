"""Small counterexamples for the legacy strategy audit; no network/data writes."""
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'research/sector_stock_momentum'))
import backtest as bt
from ml_features import price_features, latest_fiscal_updates
from legacy_portfolio import run_portfolio, score_basket, apply_regime
import ml_pipeline as ml

forms = pd.date_range('2020-01-31', periods=4, freq='ME')
rf = pd.Series(0.01, index=forms + pd.offsets.MonthEnd(1))
X = pd.DataFrame([{'t': t, 'ticker': s, 'fwd_ret': r, 'exit_status': 'ok', 'score': 1}
                  for t in forms for s, r in [('A', 0.1), ('B', 0.0)]])
a = run_portfolio(X, lambda g: {'A': 1.0}, rf)
assert np.isclose(a.net.iloc[0], 1.1 / 1.001 - 1)
assert np.allclose(a.turnover.iloc[1:], 0)
cash = run_portfolio(X[X.t != forms[1]], lambda g: {'A': 1.0}, rf, forms=forms)
assert len(cash) == 4 and cash.pick.iloc[1] == 'CASH'
assert np.isclose(cash.net.iloc[1], 0.999 * 1.01 - 1)
z = X.copy(); z.loc[z.t == forms[0], 'fwd_ret'] = -1
loss = run_portfolio(z, lambda g: {'A': 1}, rf)
assert loss.net.iloc[0] == -1 and (loss.net.iloc[1:] == 0).all()
assert (loss.turnover.iloc[1:] == 0).all()
for forms_bad in ([forms[0], forms[0]], [forms[0], forms[2]]):
    try:
        run_portfolio(X, lambda g: {'A': 1}, rf, forms=forms_bad)
    except ValueError:
        pass
    else:
        raise AssertionError('duplicate or missing formation months accepted')
for weight in (-0.1, np.nan):
    try:
        run_portfolio(X, lambda g: {'A': weight}, rf)
    except ValueError:
        pass
    else:
        raise AssertionError('invalid weight silently discarded')
reg = apply_regime(a, {forms[1]: True, forms[2]: True}, rf)
assert reg.turnover.iloc[1] > 0 and reg.turnover.iloc[2] == 0 and reg.turnover.iloc[3] > 0
b = score_basket(X, 'score', 2, rf)
assert 0 < b.turnover.iloc[1] < 0.1  # drift rebalance, not fixed 200% turnover
dates = pd.bdate_range('2018-01-01', periods=400)
d = pd.DataFrame({'A': np.linspace(100, 200, 400), 'SPY': np.linspace(100, 130, 400)}, index=dates)
sg = pd.DataFrame(1, index=dates, columns=d.columns); sg.loc[dates[250]:, 'A'] = 2
bt.SEG_D = sg; bt.SEG_M = sg.resample('ME').last()
P = d.resample('ME').last(); f = pd.DatetimeIndex([dates[260] + pd.offsets.MonthEnd(0)])
features, _ = price_features(d, P, f)
assert pd.isna(features['dist_sma200'].at[f[0], 'A'])
assert pd.isna(features['dist_sma50'].at[f[0], 'A'])
assert pd.isna(features['vol_3m'].at[f[0], 'A'])
x = pd.DataFrame({'cik': [1, 1], 'period_end': pd.to_datetime(['2020-06-30', '2020-03-31']),
                  'av': pd.to_datetime(['2020-08-01', '2020-09-01'])})
assert len(latest_fiscal_updates(x, 'av')) == 1
x = pd.DataFrame({'cik': [1, 1], 'period_end': pd.to_datetime(['2020-03-31', '2020-06-30']),
                  'av': pd.to_datetime(['2020-05-01', '2020-08-01']), 'factor': [0.5, np.nan]})
known = latest_fiscal_updates(x, 'av')
result = pd.merge_asof(pd.DataFrame({'t': [pd.Timestamp('2020-08-31')], 'cik': [1]}),
                       known, left_on='t', right_on='av', by='cik')
assert pd.isna(result.factor.iloc[0])
from risk_report import nav_daily
monthly = pd.DataFrame({'pick': ['A'], 'gross': [0.1], 'net': [0.099], 'capital_after_costs': [0.999]},
                       index=pd.DatetimeIndex(['2020-02-29']))
marks = pd.DataFrame({'A': [100., 105.]}, index=pd.to_datetime(['2020-01-31', '2020-02-28']))
bt.SEG_D = None
try:
    nav_daily(monthly, marks)
except ValueError as e:
    assert 'endpoint differs' in str(e)
else:
    raise AssertionError('a mismatched daily path was silently rescaled')
complete_month = pd.DataFrame({'pick': ['A'], 'gross': [.1], 'net': [.1], 'capital_after_costs': [1.]},
                             index=pd.DatetimeIndex(['2020-02-29']))
for missing in [np.nan, 0., -1.]:
    missing_marks = pd.DataFrame({'A': [100., missing, 110.]},
                                index=pd.to_datetime(['2020-01-31', '2020-02-03', '2020-02-28']))
    try:
        nav_daily(complete_month, missing_marks)
    except ValueError as e:
        assert 'missing or nonpositive daily held-asset quote' in str(e)
    else:
        raise AssertionError('missing held-asset quote was silently filled')
months = pd.date_range('2010-12-31', '2014-12-31', freq='ME')
rng = np.random.default_rng(7)
panel = pd.DataFrame({'t': np.repeat(months, 4)})
panel['hold'] = panel.t + pd.offsets.MonthEnd(1)
for f in ml.FEATS:
    panel['r_' + f] = rng.normal(size=len(panel))
panel['has_fund'] = 1.0
panel['fwd_rank'] = rng.uniform(size=len(panel))
base = ml.walk_forward(panel, 'ridge', [2014]).score
changed = panel.copy()
changed.loc[changed.hold > pd.Timestamp('2013-12-31'), 'fwd_rank'] *= -1000
assert np.allclose(base, ml.walk_forward(changed, 'ridge', [2014]).score)
print(json.dumps({'status': 'PASS', 'checks': ['fees_before_return', 'unchanged_top1_no_trade', 'missing_month_cash',
    'cash_exit_fee', 'bankruptcy_absorbing', 'regime_cash_no_repeat_fee', 'basket_drift_turnover', 'price_segment_windows',
    'late_old_filing_does_not_replace_new_quarter', 'latest_undefined_factor_invalidates_old_value',
    'daily_mismatch_not_smoothed', 'future_labels_do_not_change_earlier_ridge_fit',
    'duplicate_and_skipped_calendar_rejected', 'negative_and_nan_target_rejected',
    'missing_nonpositive_daily_held_quote_not_filled']}))
