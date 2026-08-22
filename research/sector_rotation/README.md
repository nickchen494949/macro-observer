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

## Architecture (v5)

```
engine.py
  ├── load_prices()             ← TWO series per ticker (CACHE_VERSION=5):
  │     ├── split_adj_close      — Yahoo Close (already split-adjusted, no dividends)
  │     └── adj_close            — Yahoo Adj Close (split + dividend adjusted)
  ├── load_pe()                 ← Koyfin CSVs, coverage dict
  ├── build_features()
  │     ├── EPS = split_adj_close / PE  (no dividend contamination)
  │     ├── Momentum = adj_close        (total return)
  │     ├── _safe_ratio()               (explicit, no pct_change NaN)
  │     └── exec_ret + entry_date/exit_date via daily adj_close
  ├── common_feature_start()    ← auto-detect fixed universe start
  ├── compute_benchmark_aligned() ← reuses exact strategy entry/exit dates
  ├── make_placebo_df()         ← fixed fake history per seed
  └── walk_forward_purged()     ← returns entry/exit dates per row

rf_backtest.py  ─── model comparison (imports engine)
rf_audit.py     ─── 5-knife audit (imports engine)
run_backtest.py ─── Phase 1 legacy (standalone)
```

### Fixes (v5 cumulative)
| Issue | Fix |
|-------|-----|
| 🔴 Same-close | Next-trading-day entry/exit via daily prices |
| 🔴 Double split adjust | Yahoo Close IS split-adjusted; removed manual `tk.splits` math |
| 🔴 Dividend in EPS | `split_adj_close` (no dividends) for EPS proxy |
| 🔴 `pct_change` NaN | `_safe_ratio()` explicit |
| 🔴 Placebo 1 iter / reshuffled | `make_placebo_df()` fixed history per seed, 500 seeds |
| 🔴 Benchmark not aligned | `compute_benchmark_aligned()` reuses exact strategy dates |
| 🟠 Pass criteria absolute | Now excess-based: Top1 vs SPY, vs EW, Rank IC |
| 🟠 Group permutation | Same row perm for grouped features |
| 🟠 Strict 2022 test | Checks entry/exit date overlap with excluded year |
| 🟠 Strict 2022 train | Removes labels whose 3M horizon touches excluded year |
| 🟠 Fixed universe | `common_feature_start()` auto-detects |
| 🟠 XLC anomaly | First-day 10.13x dropped |
| 🟠 p-value formula | `(1+n_ge)/(N+1)` conservative |
| 🟠 Cache versioning | `CACHE_VERSION=5` auto-invalidates old data |

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

Walk-forward RF with purge, next-trading-day execution, split-only EPS.

**v5 results: PENDING — run `rf_backtest.py`**

### Phase 4: 5-Knife Audit (`rf_audit.py`)

**v5 results: PENDING — run `rf_audit.py`**

v5 pass criteria (excess-based):
- Top1 > aligned SPY
- Top1 > EW sectors
- Mean Rank IC > 0
- LOSO mean excess > 0
- Strict excl-2022 excess > 0
- Placebo spread p < 0.05
- Placebo Top1-EW p < 0.05

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
python3 -c "from engine import load_adjusted_prices; load_adjusted_prices()"

# Model comparison
python3 rf_backtest.py

# 5-knife audit (~15-20 min due to 500 placebo iterations)
python3 rf_audit.py
```
