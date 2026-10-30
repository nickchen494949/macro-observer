# ML_SPEC — 机器学习选股（冻结后才打开考试期）

Written before any model was trained (2026-10-28 22:06). Stage 1 (development) selects the model using ONLY holding
months 2011-01 … 2022-12; its choice is written to `results/ml/selection.json` and committed to GitHub; only then
is stage 2 (holdout 2023-01 … 2026-09) run, once, with nothing changed.

Honest caveat: the 2023–2026 period was already seen in earlier momentum backtests of this repo (pure momentum,
sector momentum, EPS variants), so it is a **retrospective** holdout for the user and for me, not an untouched one.

## Universe, timing, costs (identical to the audited backtest)
- Month-end t, PIT S&P 500 members with a fresh month-end quote and a full 12-1 momentum window, sector as of t.
- Holding t → t+1 close, terminal events as in backtest.py; costs 10 bp × turnover; long-only; 1 stock (primary),
  top-5 / top-20 equal-weight reported as diagnostics (is the model ranking or just lucky?).

## Features (ml_features.py, all public at t)
mom_12_1, mom_6_1, mom_3_1, rev_1m, mom_12_1_secrel, sector_mom, dist_sma200, above_sma200, dist_sma50, dist_52wh,
vol_3m, vol_12m, beta_12m, maxret_1m, eps_g, eps_g_m5, eps_g_sym, deps_p, ep, sue, margin, margin_chg, rev_g,
log_mcap, days_since_filing. Pre-processing: cross-sectional percentile rank per month (missing → median 0 plus a
`has_fund` indicator for linear models; LightGBM sees NaN).

## Label
Cross-sectional percentile rank of the next-month return (fwd_rank).

## Candidate models (fixed list, no tuning beyond this list)
| id | model |
|---|---|
| mom | 12-1 momentum only (baseline) |
| composite | equal-weight mean of ranks: mom_12_1, eps_g_m5, deps_p, sue, ep, dist_52wh |
| ridge | Ridge regression (alpha = 10) on all ranked features |
| lgbm_s | LightGBM regressor, 15 leaves, min_data 200, lr 0.03, 300 trees, feature_fraction 0.7, bagging 0.8 |
| lgbm_m | LightGBM regressor, 31 leaves, min_data 100, lr 0.03, 500 trees, feature_fraction 0.7, bagging 0.8 |
| lgbm_rank | LightGBM LambdaRank (per-month groups, label = fwd decile 0–9), 15 leaves, min_data 200, 300 trees |
Portfolio rules applied to every model's score: **top1** and **top1_sma200** (only stocks above their 200-day SMA).

## Walk-forward and selection (development only)
- Refit every January on all formations whose label is known (formation ≤ previous month-end); first prediction
  year 2014 (≥ 3 years of training data: formations from 2010-12).
- Selection metric (pre-declared): mean monthly Spearman IC of the score vs next-month return over the development
  walk-forward months 2014-01 … 2022-12; the model with the highest mean IC is chosen. Between top1 and top1_sma200
  the rule with the higher development Sharpe of the 1-stock portfolio is chosen.
- Reported for transparency: every model × rule on development, deflated Sharpe for the 12 tried combinations.

## Holdout (stage 2, run once)
The chosen model + rule, refitted every January exactly as in development (training data always ends before the
prediction month), evaluated on holding months 2023-01 … 2026-09. Benchmarks: SPY, pure momentum top1, pure
momentum top1_sma200, protected-EPS strategy (F), sector-momentum spec with and without SMA200.
