# 🔬 Sector Rotation Research

Monthly sector rotation using **Valuation + EPS Revision + Momentum**, tested via
**Simple Ranking**, **Ridge Regression**, and **Random Forest** — all walk-forward OOS.

## ⚠️ Research Only — Not Production Alpha

This is an audit trail for a research experiment. Results are promising but not
validated for live trading. Key remaining risk: Koyfin PE data may not be strictly
point-in-time.

---

## Data — ALL REAL

| Source | What | Coverage |
|--------|------|----------|
| **Koyfin f_pe** | Daily Forward PE, 11 S&P sectors | 2003→2026 |
| **Yahoo / yfinance** | Daily ETF prices (XLK, XLC, etc.) | 1998→2026 |
| **TLT** | Long bond ETF for rate regime | 2002→2026 |

PE files downloaded from [AlphaLabX1/forward-pe-viewer](https://github.com/AlphaLabX1/forward-pe-viewer/tree/main/data).
No synthetic data. No made-up numbers.

---

## Experiment Timeline

### Phase 1: Simple Ranking Backtest (`run_backtest.py`)

Signals ranked cross-sectionally, buy Top 3 / short Bottom 3.

**2023-01 → 2026-06 (1M holding):**

| Signal | Ann Spread | t-stat | Win Rate |
|--------|-----------|--------|----------|
| Valuation | +2.4% | 0.39 | 44% |
| EPS Revision | +0.2% | 0.03 | 51% |
| Momentum | -7.3% | -1.08 | 46% |

**Key finding:** Weak. Momentum negative. Valuation marginal.

### Phase 2: Robustness Audit on EPS Revision

Tested whether EPS revision alpha was real or an XLE artifact:

| Variant | Top1 CAGR | vs SPY 16.1% |
|---------|-----------|-------------|
| Original | +18.1% | ✅ |
| PE>50 → NaN | +10.1% | ❌ |
| **Exclude XLE** | **+10.7%** | **❌** |

**Verdict:** Simple EPS revision alpha collapsed without XLE. The signal was
dominated by Energy's PE denominator instability in 2020-2022.

### Phase 3: Random Forest (`rf_backtest.py`)

Walk-forward expanding-window RF using 9 features (valuation, EPS revision,
momentum variants, PE level/change, distance from high).

**2019-01 → 2026-06 — Model Comparison:**

| Model | CAGR | Sharpe | Sortino | MaxDD |
|-------|------|--------|---------|-------|
| QQQ | +23.5% | 1.14 | 1.93 | -33.1% |
| **RF Top1 (no XLE)** | **+21.7%** | **1.03** | **2.13** | -22.1% |
| SPY | +16.1% | 0.98 | 1.48 | -24.8% |
| RF Top3 | +15.4% | 0.94 | 1.39 | -20.8% |
| Ridge Top1 | +11.0% | 0.59 | 0.99 | -21.4% |

**Key finding:** RF survives XLE removal. Ridge dies. Non-linear interactions matter.

### Phase 4: 5-Knife Audit (`rf_audit.py`) — **4/4 PASSED**

| Test | Result | Status |
|------|--------|--------|
| **Purged walk-forward** (3M embargo) | CAGR +21.7%, Sharpe 1.03 | ✅ |
| **Leave-one-sector-out** | Mean CAGR +14.1%, range +6.1%→+21.7% | ✅ |
| **Exclude 2022** | CAGR +25.2% (better without it!) | ✅ |
| **Placebo** (shuffled labels) | Real spread +13.0% vs placebo -0.2% | ✅ |

#### Purge Impact
```
Without purge (leaky):  CAGR +35.1%, spread +41.7%
With 3M purge:          CAGR +21.7%, spread +12.3%
```
The unpurged version had significant leakage. Purged results are ~40% lower but still strong.

#### Leave-One-Sector-Out
```
excl XLK:   +9.2%   (most dependent)
excl XLP:   +6.1%   (second most)
excl XLF:  +14.8%
excl XLY:  +12.2%
mean:      +14.1%
```
No single sector removal kills the strategy (unlike simple EPS which died without XLE).

#### OOS Permutation Importance
```
momentum 1M:    🔴 critical (spread drops from +13% to -5%)
momentum 3M:    🔴 critical
EPS revision:   🔴 critical
pe_change:      🔴 critical
valuation:      🟡 important
pe_level:       ⚪ minor
```
Multiple features contribute — not single-variable alpha.

#### Feature Importance Stability
```
eps_rev:     CV=0.25  ✅ stable
mom3:        CV=0.22  ✅ stable
mom1:        CV=0.30  ✅ stable
valuation:   CV=0.54  ⚠️ unstable
mom6:        CV=0.34  ⚠️ unstable
```

---

## Remaining Risks

1. **Point-in-time PE data**: Koyfin f_pe may have been revised retroactively. This audit cannot address data integrity — only FactSet/Bloomberg PIT data can resolve this.

2. **Short sample**: 89 months (2019-2026) is limited. Full sample (2005-2026) shows weaker but positive results.

3. **XLK concentration**: RF Top1 picks XLK 26% of the time. Strategy partially functions as a "Tech timing model."

4. **Sector universe**: Only 11 sectors. Cross-sectional breadth is inherently limited.

---

## Current Assessment

```
Status: 🟢 Candidate signal — worth serious validation
        NOT 🟢🟢 Proven alpha
```

The RF model captures non-linear interactions (EPS revision + momentum confirmation)
that simple ranking and linear models miss. It survives purging, LOSO, year removal,
and placebo tests. But 89-month OOS with questionable PE data quality means this
needs real PIT data before any allocation decision.

---

## Files

### Code
| File | Purpose |
|------|---------|
| `run_backtest.py` | Phase 1: Simple ranking backtest (val, eps_rev, momentum) |
| `rf_backtest.py` | Phase 3: RF vs Ridge vs Simple — walk-forward comparison |
| `rf_audit.py` | Phase 4: 5-knife audit (purge, LOSO, exclude 2022, permutation, placebo) |
| `fetch_sector_data.py` | Data download utility |

### Data
| File | Source |
|------|--------|
| `pe_data/*.csv` | Koyfin Forward PE (daily, 2003→2026) |
| `pe_data/combined_legacy.csv` | Legacy MacroMicro Forward PE (monthly, 1999→2026) |

### Results
| File | Contents |
|------|----------|
| `backtest_results.csv` | Simple ranking backtest results |
| `rf_backtest_results.csv` | RF model comparison results |
| `detail_*.csv` | Month-by-month position details |

---

## Usage

```bash
# Simple ranking backtest
python3 run_backtest.py
python3 run_backtest.py --start 2005-07 --holding 3

# RF model comparison
python3 rf_backtest.py

# 5-knife audit (takes ~10 minutes)
python3 rf_audit.py
```

## Data Sources

- Forward PE: https://github.com/AlphaLabX1/forward-pe-viewer/tree/main/data
- Koyfin migration: https://github.com/AlphaLabX1/forward-pe-viewer/commit/d289ca6
- MacroMicro chart: https://en.macromicro.me/charts/48243/s5cond-forward-pe-ratio
