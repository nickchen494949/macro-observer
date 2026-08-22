# 🔬 Sector Rotation Research

Monthly sector rotation using **Valuation + Forward Earnings Momentum + Price Momentum**,
tested via **Random Forest** and **Ridge** — all walk-forward OOS.

## ⚠️ Research Only — Not Production Alpha

**Status: 🟡 Promising, not proven (v7 final-clean, not yet run).**

Remaining risks:
- Koyfin PE = vendor-history (not perfect point-in-time)
- Short sample (~80-90 months OOS)
- Multiple-testing: many model variants tried before v7

---

## Data — ALL REAL

| Source | What | Coverage |
|--------|------|----------|
| **Koyfin f_pe** | Daily Forward PE, 11 S&P sectors | See per-sector below |
| **yfinance** | Daily ETF prices (**split-adjusted** + **total-return**) | 1998→2026 |

### Per-Sector PE Coverage
| Sector | ETF | PE Start | Notes |
|--------|-----|----------|-------|
| Technology | XLK | 2003-06 | |
| Financials | XLF | 2003-06 | |
| Consumer Disc | XLY | 2003-06 | |
| Energy | XLE | 2003-06 | |
| Health Care | XLV | 2003-06 | |
| Consumer Staples | XLP | 2003-06 | |
| Materials | XLB | 2003-06 | |
| Industrials | XLI | 2003-06 | |
| Utilities | XLU | 2003-06 | |
| **Real Estate** | **XLRE** | **2016-01** | Spun out of Financials |
| **Comm Services** | **XLC** | **2018-06** | Reconstituted; first-day anomaly (10.13x) dropped |

**Full 11-sector universe common start: 2018-06.**
PE from [AlphaLabX1/forward-pe-viewer](https://github.com/AlphaLabX1/forward-pe-viewer/tree/main/data).

---

## Architecture (v7 final-clean)

```
engine.py (CACHE_VERSION=7)
  ├── load_prices()
  │     ├── split_adj_close — Yahoo Close (split-adjusted, NO dividends) → EPS proxy
  │     └── adj_close       — Yahoo Adj Close (split+dividend) → momentum, P&L
  │     └── fail-fast on missing; cache version written AFTER all succeed
  ├── load_pe()             ← fail-fast on missing
  ├── build_features(execution_lag=2)
  │     ├── Forward Earnings = split_adj_close / PE
  │     ├── _symmetric_change()  — bounded [-2,+2], no denominator explosion
  │     ├── Momentum via _safe_ratio() on adj_close
  │     ├── exec_ret + entry_date/exit_date (T+lag execution)
  │     └── target_3m: execution-aligned 3M return + target_exit_date
  ├── common_feature_start()
  ├── check_universe_completeness()
  ├── compute_benchmark_aligned()  ← strict date match
  ├── make_placebo_df()            ← NaN-safe, fixed history per seed
  └── walk_forward_purged()
        ├── Purge: target_exit_date <= pred_date (exact, no embargo approx)
        ├── train_start for fixed training universe
        ├── min_test_sectors for strict universe
        ├── Month-Period date comparison (no off-by-one)
        └── permutation_seed for repeated importance
```

### Timeline: Signal → Trade → Target

```
Month-end T
  │ features observed (PE, prices)
  ↓
T+1 close: Koyfin PE finalized
  ↓
T+2 close: ENTRY (execution_lag=2)
  ↓
next month T+2: EXIT (1-month P&L)
  ↓
T+3 months T+2: target_exit (3M training target)
```

### Features
| Feature | Source | Formula |
|---------|--------|---------|
| `f_valuation` | PE | -z-score of PE vs 24M rolling |
| `f_fwd_earn_mom_3m` | Price/PE | symmetric change of (split_adj_close/PE) over 3M |
| `f_fwd_earn_mom_1m` | Price/PE | symmetric change over 1M |
| `f_mom6/3/1` | adj_close | 6/3/1 month total return |
| `f_pe_level` | PE | raw forward PE |
| `f_pe_chg3` | PE | 3M PE ratio change |
| `f_dist_high6` | adj_close | distance from 6M high |

### Fixes (v7 cumulative)
| # | Issue | Fix |
|---|-------|-----|
| 1 | 🔴 Same-close | T+2 next-trading-day entry/exit via daily prices |
| 2 | 🔴 Koyfin finalization lag | `execution_lag=2` (T+2), also tests T+1 and T+3 |
| 3 | 🔴 Target/execution mismatch | 3M target computed from T+2 entry to T+3M+2 exit |
| 4 | 🔴 Embargo approximation | Purge by `target_exit_date <= pred_date` (exact) |
| 5 | 🔴 Double split adjust | Yahoo Close IS split-adjusted; no manual tk.splits |
| 6 | 🔴 Dividend in EPS | `split_adj_close` for earnings proxy |
| 7 | 🔴 `pct_change` NaN | `_safe_ratio()` / `_symmetric_change()` |
| 8 | 🔴 Placebo 1 iter / reshuffled | `make_placebo_df()` fixed history, NaN-safe, 500 seeds |
| 9 | 🔴 Benchmark misaligned | `compute_benchmark_aligned()` strict, raises on mismatch |
| 10 | 🔴 Permutation never ran | `permutation_seed` param, 30 real repeats |
| 11 | 🔴 END off-by-one | Month-Period comparison |
| 12 | 🔴 Training universe dynamic | `train_start` fixes to common universe |
| 13 | 🟠 EPS revision naming | Renamed → Forward Earnings Momentum (`_symmetric_change`) |
| 14 | 🟠 Denominator explosion | Symmetric change bounded [-2,+2] |
| 15 | 🟠 Strict universe | `min_test_sectors` skips incomplete months |
| 16 | 🟠 Sortino formula | Proper downside deviation (MAR=0) |
| 17 | 🟠 Deterministic seeds | `gid * 10000 + rep`, no Python `hash()` |
| 18 | 🟠 Pass criteria | Excess-based: vs SPY, vs EW, IC, LOSO, placebo |

---

## Experiment Timeline

### Phase 1: Simple Ranking (`run_backtest.py`)

| Signal | Ann Spread | t-stat | Win Rate |
|--------|-----------|--------|----------|
| Valuation | +2.4% | 0.39 | 44% |
| EPS Revision | +0.2% | 0.03 | 51% |
| Momentum | -7.3% | -1.08 | 46% |

### Phase 2: EPS Revision Robustness

| Variant | Top1 CAGR | vs SPY |
|---------|-----------|--------|
| Original | +18.1% | ✅ |
| Exclude XLE | +10.7% | ❌ |

**Verdict:** Simple EPS revision collapsed without XLE.

### Phase 3: RF Model Comparison (`rf_backtest.py`)

**v7 results: PENDING — run `rf_backtest.py`**

### Phase 4: 5-Knife Audit (`rf_audit.py`)

**v7 results: PENDING — run `rf_audit.py`**

v7 pass criteria (7 checks, excess-based):
1. Top1 > aligned SPY
2. Top1 > EW sectors
3. Mean Rank IC > 0
4. LOSO mean excess > 0
5. Strict excl-2022 excess > 0
6. Placebo spread p < 0.05
7. Placebo Top1-EW p < 0.05

Plus execution lag sensitivity: T+1 / **T+2** / T+3.

---

## Remaining Risks

| Risk | Severity | Mitigatable? |
|------|----------|-------------|
| Koyfin PE not perfect PIT | 🟠 | Partially: T+2 execution helps; start freezing snapshots |
| Multiple-testing / researcher DoF | 🟠 | Future: max-stat placebo or live OOS |
| Short sample (~80-90 months) | 🟡 | More time needed |
| Transaction cost / turnover | 🟡 | Not yet analyzed |
| ETF P/PE ≠ pure analyst revision | 🟡 | Cross-check with direct NTM EPS consensus |

---

## Files

| File | Purpose |
|------|---------|
| `engine.py` | **Shared engine** — data, features, walk-forward, metrics |
| `rf_audit.py` | 5-knife audit + execution lag sensitivity |
| `rf_backtest.py` | RF vs Ridge comparison |
| `run_backtest.py` | Phase 1 legacy |

| Dir | Contents |
|-----|----------|
| `pe_data/*.csv` | Koyfin Forward PE |
| `adj_prices/*.csv` | yfinance prices (auto-generated, CACHE_VERSION=7) |

---

## Usage

```bash
# Download prices (first run only, ~30s)
python3 -c "from engine import load_prices; load_prices()"

# Model comparison
python3 rf_backtest.py

# Full audit (~20-30 min, 500 placebo + 30×11 permutations)
python3 rf_audit.py
```
