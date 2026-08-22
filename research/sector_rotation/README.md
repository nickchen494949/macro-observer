# 🔬 Sector Rotation Research

Monthly sector rotation using **Valuation + EPS Revision + Momentum**, tested via
**Simple Ranking**, **Ridge Regression**, and **Random Forest** — all walk-forward OOS.

## ⚠️ Research Only — Not Production Alpha

This is an audit trail for a research experiment. **Status: 🟡 Promising, not proven.**

Key remaining risks:
- Koyfin PE data may not be strictly point-in-time
- Sample is short (~89 months OOS)

---

## Data — ALL REAL

| Source | What | Coverage |
|--------|------|----------|
| **Koyfin f_pe** | Daily Forward PE, 11 S&P sectors | See per-sector below |
| **yfinance** | Daily **split-adjusted** ETF prices | 1998→2026 |
| **TLT** | Long bond ETF for rate regime | 2002→2026 |

### Per-Sector PE Coverage (actual start dates)
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
| **Comm Services** | **XLC** | **2018-06** | Reconstituted from Telecom; first-day anomaly (10.13x) dropped |

**Full 11-sector universe common start: 2018-06.**

PE files from [AlphaLabX1/forward-pe-viewer](https://github.com/AlphaLabX1/forward-pe-viewer/tree/main/data).
No synthetic data.

---

## Architecture (v7 Final Clean)

```
engine.py (CACHE_VERSION=7)
  ├── load_prices()             ← fail-fast if any ticker missing
  │     ├── split_adj_close      — Yahoo Close (split-adjusted, no dividends)
  │     └── adj_close            — Yahoo Adj Close (split + dividend adjusted)
  ├── load_pe()                 ← fail-fast if any sector PE missing
  ├── build_features(execution_lag=2)
  │     ├── Forward Earnings Momentum = symmetric change 2*(E_t - E_t-n)/(|E_t| + |E_t-n|)
  │     ├── execution_lag=2     (T+2 entry allows Koyfin PE finalization)
  │     ├── target_ret_raw      (aligned: T+2 entry → next T+2 exit)
  │     └── strict_universe_n   (flags incomplete months)
  ├── compute_benchmark_aligned() ← strict date match, raises on mismatch
  ├── make_placebo_df()         ← fixed fake history per seed, skips NaNs
  └── walk_forward_purged()
        ├── exact purge         (train = train[target_exit_date <= information_asof])
        ├── start/end by month Period
        ├── train_start         (strictly bounds historical training universe for all configs)
        ├── calendar preserved  (missing/invalid universe months yield 0.0 CASH return)
        └── deterministic permutation_seed parameter

rf_backtest.py  ─── model comparison (strict universe)
rf_audit.py     ─── 5-knife audit (tests T+1, T+2, T+3 lags)
```

### Fixes (v8 cumulative)
| Issue | Fix |
|-------|-----|
| 🔴 Missing Univ = 0% | Incomplete months yield 0.0 CASH, preserving calendar N vs SPY |
| 🔴 Shared History | `train_start` strictly bounds historical training pool across all config variants |
| 🔴 T+2 Execution | `execution_lag=2` allows Koyfin PIT stabilization |
| 🔴 Exact Target/Purge | Target perfectly aligned to execution; exact date-based purge |
| 🔴 Double split adjust | Yahoo Close IS split-adjusted; no manual splits |
| 🔴 Same-close | Execution via daily prices, strict execution lag |
| 🔴 Dividend in EPS | `split_adj_close` for EPS proxy |
| 🔴 `pct_change` NaN | `_safe_ratio()` explicit |
| 🔴 Placebo reshuffled | `make_placebo_df()` fixed history, 500 seeds |
| 🔴 Benchmark aligned | `compute_benchmark_aligned()` strict date match |
| 🔴 Permutation logic | 30 true repeats, grouped features use same row perm |
| 🟠 Fwd Earn Momentum | Symmetric change bounds values [-2, 2], prevents explosion |
| 🟠 Sortino Formula | Standard downside deviation: `min(r, 0)^2` |
| 🟠 Placebo NaNs | Shuffles only `.notna()` targets |
| 🟠 Pass criteria | Excess-based: Top1 vs SPY, vs EW, IC, LOSO, placebo |
| 🟠 Strict 2022 | Execution date overlap + training label overlap |

---

## Experiment Timeline

### Phase 1: Simple Ranking (`run_backtest.py`)

Signals ranked cross-sectionally, buy Top 3 / short Bottom 3.

| Signal | Ann Spread | t-stat | Win Rate |
|--------|-----------|--------|----------|
| Valuation | +2.4% | 0.39 | 44% |
| EPS Revision | +0.2% | 0.03 | 51% |
| Momentum | -7.3% | -1.08 | 46% |

**Key finding:** Weak. Momentum negative. Valuation marginal.

### Phase 2: EPS Revision Robustness

Tested whether EPS revision alpha was an XLE artifact:

| Variant | Top1 CAGR | vs SPY |
|---------|-----------|--------|
| Original | +18.1% | ✅ |
| PE>50 → NaN | +10.1% | ❌ |
| **Exclude XLE** | **+10.7%** | **❌** |

**Verdict:** Simple EPS revision collapsed without XLE.

### Phase 3: RF Model Comparison (`rf_backtest.py`)

**v8.1 results: PENDING — run `rf_backtest.py`**

### Phase 4: 5-Knife Audit (`rf_audit.py`)

**v8.1 results: PENDING — run `rf_audit.py`**

v7 pass criteria (7 checks, all excess-based):
1. Top1 > aligned SPY
2. Top1 > EW sectors
3. Mean Rank IC > 0
4. LOSO mean excess > 0
5. Strict excl-2022 excess > 0
6. Placebo spread p < 0.05
7. Placebo Top1-EW p < 0.05

---

## Remaining Risks

1. **Point-in-time PE**: Koyfin f_pe may have been revised retroactively
2. **Short sample**: ~89 months OOS (2019-2026)
3. **Sector concentration**: RF Top1 may favor XLK (~26%)
4. **PE denominator instability**: EPS ≈ 0 → PE explodes → false EPS revision signal

---

## Files

### Code
| File | Purpose |
|------|---------|
| `engine.py` | **Shared engine** — data, features, walk-forward, metrics |
| `rf_audit.py` | 5-knife audit (purge, LOSO, excl-2022, permutation, placebo) |
| `rf_backtest.py` | RF vs Ridge model comparison |
| `run_backtest.py` | Phase 1: Simple ranking (legacy, standalone) |
| `fetch_sector_data.py` | Data download utility |

### Data
| Dir | Contents |
|-----|----------|
| `pe_data/*.csv` | Koyfin Forward PE (daily) |
| `pe_data/combined_legacy.csv` | Legacy MacroMicro PE |
| `adj_prices/*.csv` | yfinance split-adjusted daily close (auto-generated) |

### Results
| File | Status |
|------|--------|
| `backtest_results.csv` | Phase 1 results |
| `rf_backtest_results.csv` | v2 results (superseded) |

---

## Usage

```bash
# Download adjusted prices (first run only, ~30s)
python3 -c "from engine import load_prices; load_prices()"

# Model comparison
python3 rf_backtest.py

# 5-knife audit (~15-20 min due to 500 placebo iterations)
python3 rf_audit.py
```
