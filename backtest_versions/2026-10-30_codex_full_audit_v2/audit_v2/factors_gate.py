"""Small counterexamples for the bounded factors/legacy strategy correction."""
import importlib.util
import ast
import inspect
import json
from pathlib import Path
import sys
from unittest.mock import patch
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'research/sector_stock_momentum'
sys.path.insert(0, str(SRC))
import sma200_overlay as sma
import eps_momentum as eps
import factor_screen as fs
import factor_combo as fc
from legacy_portfolio import score_basket

results = []
def check(name, condition, detail):
    results.append({'test': name, 'passed': bool(condition), 'detail': detail})
    assert condition, (name, detail)

form = pd.date_range('2020-01-31', periods=3, freq='ME')
rf = pd.Series(0.01, index=form + pd.offsets.MonthEnd(1))
X = pd.DataFrame({'t': [form[0], form[2]], 'ticker': ['A', 'B'], 'fwd_ret': [0., 0.], 'exit_status': ['ok', 'ok']})
r = sma.run(X, lambda g: g.ticker.iloc[0], rf)
check('filtered_empty_month_is_cash', len(r) == 3 and r.pick.iloc[1] == 'CASH', r.pick.tolist())
check('cash_sale_fee_precedes_cash_return', np.isclose(r.net.iloc[1], (1-.001)*1.01-1), float(r.net.iloc[1]))
loss = X.assign(fwd_ret=[-1., 5.])
r = sma.run(loss, lambda g: g.ticker.iloc[0], rf)
check('loss_capped_at_total_capital', r.net.iloc[0] == -1., r.net.tolist())
check('zero_wealth_cannot_restart', (r.net.iloc[1:] == 0).all() and (r.turnover.iloc[1:] == 0).all(), r.net.tolist())
flat = pd.DataFrame({'t': form, 'ticker': 'A', 'fwd_ret': 0., 'exit_status': 'ok', 'score': 1.})
b = score_basket(flat, 'score', 5, rf*0, forms=form)
check('same_basket_no_recurring_flat_charge', b.turnover.iloc[1:].eq(0).all() and b.net.iloc[1:].eq(0).all(), b.turnover.tolist())

dates = pd.Series(pd.to_datetime(['2009-12-31', '2014-11-30', '2014-12-31', '2015-01-31']))
mask = fs.known_training_mask(dates, '2015-01-31')
check('strict_label_cutoff_and_training_start', mask.tolist() == [False, True, False, False], mask.tolist())
ic = pd.Series([-0.01, 10.], index=pd.to_datetime(['2019-11-30', '2019-12-31']))
share = fs.development_sign_share(ic, -.01)
check('retro_december_cannot_flip_dev_year', share == .1, share)
rw, ts = fs.romano_wolf(pd.DataFrame({'constant': np.zeros(20), 'real': np.sin(np.arange(20))}), n_boot=19)
check('constant_factor_not_false_significant', rw.constant == 1 and np.isnan(ts.constant), rw.to_dict())

# Prior-year net margin was filed late: unavailable in May, available in June.
p = pd.DataFrame({'cik': [1, 1], 'period_end': pd.to_datetime(['2020-03-31', '2021-03-31']),
 'eps_diluted_approx_ttm_adj': [1., 2.],
 'eps_diluted_approx_ttm_available_date': pd.to_datetime(['2020-05-01', '2021-05-01']),
 'net_income_ttm': [10., 20.], 'revenue_ttm': [100., 100.],
 'net_income_ttm_available_date': pd.to_datetime(['2021-06-01', '2021-05-01']),
 'revenue_ttm_available_date': pd.to_datetime(['2021-06-01', '2021-05-01'])})
with patch.object(pd, 'read_parquet', return_value=p):
    g = eps.growth_panel(pd.to_datetime(['2021-05-31', '2021-06-30']), None)
check('eps_protected_uses_its_own_public_date', np.isnan(g.growth_margin5.iloc[0]) and g.growth_margin5.iloc[1] == 1.,
      [None if pd.isna(v) else float(v) for v in g.growth_margin5])
check('eps_other_variants_not_delayed_by_margin', g.growth.eq(1).all(), g.growth.tolist())
tab = pd.DataFrame({'cik': [1, 1], 'ddate': pd.to_datetime(['2020-06-30', '2020-03-31']),
                    'avail': pd.to_datetime(['2020-08-01', '2020-09-01']), 'ratio': [2., 9.]})
grid = pd.DataFrame({'cik': [1], 't': pd.to_datetime(['2020-09-30'])})
v = fs.asof(grid, tab, 'ratio', 'avail', 200).iloc[0]
check('late_old_fiscal_report_cannot_overwrite_newer', v == 2., float(v))
tab = tab.assign(ddate=pd.to_datetime(['2020-03-31', '2020-06-30']), ratio=[2., np.nan])
v = fs.asof(grid, tab, 'ratio', 'avail', 200).iloc[0]
check('latest_undefined_ratio_invalidates_old_ratio', np.isnan(v), None)
import ndx_expand as ndx
try:
    ndx.cik_at([(1, None, None), (2, None, None)], pd.Timestamp('2020-01-31'))
    rejected = False
except ValueError:
    rejected = True
check('ambiguous_ndx_cik_identity_is_rejected', rejected, rejected)

cash = flat.assign(score=np.nan)
with patch.object(fc.bt, 'load_rf', return_value=rf):
    r = fc.top_portfolio(cash, cash.score)
check('combo_all_missing_months_are_cash', len(r) == 3 and np.allclose(r.net, .01), r.net.tolist())
with patch.object(fc.bt, 'load_rf', return_value=rf*0):
    continuous = fc.top_portfolio(flat, flat.score)
    reset = fc.top_portfolio(flat.iloc[1:], flat.score.iloc[1:])
check('eval_retro_boundary_must_preserve_positions', continuous.turnover.iloc[1] == 0 and reset.turnover.iloc[0] > 0,
      {'continuous_boundary_turnover': float(continuous.turnover.iloc[1]), 'incorrect_reset_turnover':float(reset.turnover.iloc[0])})

# Execute the actual main's candidate-loading statements with one unknown future
# return. The highest formation score must survive, then fail in the ledger.
unknown = pd.DataFrame({'t': [form[0], form[0]], 'ticker': ['A', 'B'],
                       'fwd_ret': [np.nan, 0.1], 'exit_status': ['source_gap', 'ok'],
                       'score': [2.0, 1.0]})
main_ast = ast.parse(inspect.getsource(fc.main)).body[0]
candidate_scope = dict(fc.__dict__)
with patch.object(fc.pd, 'read_parquet', return_value=unknown):
    exec(compile(ast.Module(body=main_ast.body[:2], type_ignores=[]), '<actual_combo_candidate_loading>', 'exec'), candidate_scope)
candidate = candidate_scope['X']
check('combo_unknown_future_remains_formation_candidate', candidate.ticker.tolist() == ['A', 'B'], candidate.ticker.tolist())
with patch.object(fc.bt, 'load_rf', return_value=rf*0):
    try:
        fc.top_portfolio(candidate, candidate.score)
    except ValueError as exc:
        error = str(exc)
    else:
        error = ''
check('combo_unpriceable_winner_is_rejected_not_substituted', ' A: missing/invalid holding return' in error, error)

# Prove these checks would catch inherited behavior, using its function directly.
old = ROOT.parent / '2026-10-30_codex_audited_modified/research/sector_stock_momentum/sma200_overlay.py'
spec = importlib.util.spec_from_file_location('factors_old_sma', old)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
old_r = mod.run(loss, lambda g: g.ticker.iloc[0], rf)
check('counterexample_inherited_missing_month_and_overloss', len(old_r) == 2 and old_r.net.iloc[0] < -1,
      {'old_months': len(old_r), 'old_returns': old_r.net.tolist()})

out = {'status': 'WRITER_TESTS_PASSED_PENDING_INDEPENDENT_REVIEW', 'tests': results}
(ROOT / 'audit_v2/factors_gate.json').write_text(json.dumps(out, ensure_ascii=False, indent=2))
print(json.dumps(out, ensure_ascii=False, indent=2))
