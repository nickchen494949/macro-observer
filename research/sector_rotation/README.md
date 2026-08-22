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

## Architecture (v4)

All scripts share a single `engine.py`:

```
engine.py
  ├── load_prices()             ← TWO series per ticker:
  │     ├── adj_close            — split + dividend adjusted (P&L, momentum)
  │     └── split_adj_close      — split-only adjusted (EPS proxy)
  ├── load_pe()                 ← Koyfin CSVs, XLC anomaly dropped, coverage reported
  ├── build_features()          ← explicit ratio (no pct_change NaN bug)
  │     ├── EPS = split_adj_close / PE  (no dividend contamination)
  │     ├── Momentum = adj_close        (total return)
  │     ├── PE capped at 50x
  │     └── exec_ret via daily adj_close (next-trading-day entry/exit)
  ├── make_placebo_df()         ← fixed fake history per seed (cross-sectional)
  ├── compute_benchmark_returns() ← same execution dates as strategy
  ├── walk_forward_purged()     ← 3M embargo, exec-date year exclusion
  │     └── proper group permutation (shared row indices)
  └── calc_metrics()

rf_backtest.py  ─── imports engine ─── model comparison
rf_audit.py     ─── imports engine ─── 5-knife audit
run_backtest.py ─── standalone Phase 1 (simple ranking, legacy)
```

### Fixes Applied (v4)
| Issue | Fix |
|-------|-----|
| 🔴 Same-close execution | `exec_ret` via daily prices: next-trading-day entry/exit |
| 🔴 Split + dividend conflation | Two price series: `split_adj_close` for EPS, `adj_close` for P&L |
| 🔴 `pct_change()` NaN ffill | Replaced with explicit `_safe_ratio()` |
| 🔴 Placebo: 1 iter, reshuffled per month | 500 seeds, `make_placebo_df()` creates fixed fake history |
| 🟠 Group permutation | Same row permutation for all features in group |
| 🟠 Exclude-2022 training | `exclude_labels_overlapping` removes labels touching 2022 |
| 🟠 Exclude-2022 test | Checks `entry_date`/`exit_date` overlap, not just signal year |
| 🟠 Benchmark alignment | `compute_benchmark_returns()` uses exact same execution dates |
| 🟠 XLC first-day anomaly | Dropped 10.13x entry |
| 🟠 p-value formula | `(1 + n_ge) / (N + 1)` — conservative correction |

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

Walk-forward RF with purge, next-trading-day execution, split-only EPS prices.

**v4 results: PENDING — run `rf_backtest.py`**

(v2 results showed +21.7% CAGR but had same-close bias + dividend contamination in EPS)

### Phase 4: 5-Knife Audit (`rf_audit.py`)

**v4 results: PENDING — run `rf_audit.py`**

v4 audit uses:
- Split-only prices for EPS proxy
- Fixed fake history per placebo seed
- Execution-date overlap for 2022 exclusion
- Aligned benchmark (same entry/exit dates)

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
