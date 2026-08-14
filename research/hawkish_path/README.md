# Fed Hawkish Path Backtest

Backtest: does market-implied hawkish repricing of the Fed path predict equity drawdowns?

## Signal Definition

```
ExpectedShortRate_1Y = THREEFF0100.B - THREEFFTP0100.B  (Kim-Wright model)
HawkishPath = ExpectedShortRate_1Y - DFF (FRED effective fed funds rate)

Danger Zone ("Strongly Hawkish"):
  HP > 0.50%  AND  ΔExpectedRate_1Y_4w > 0.25%
```

**Key correction (v2):** Uses ΔExpectedRate_1Y (change in the *expected* future rate itself), NOT ΔHP (change in the gap). This prevents false positives from crisis normalization — when the Fed emergency-cuts but the expected future rate stays flat, HP rises mechanically without any hawkish repricing.

## Data Sources

| Source | Series | Range | Notes |
|:---|:---|:---|:---|
| [Kim-Wright Model](https://www.federalreserve.gov/data/yield-curve-tables/feds200533.csv) | THREEFF0100.B, THREEFFTP0100.B | 1990-01-02 → present | Fed staff research, not official release |
| [FRED DFF](https://fred.stlouisfed.org/series/DFF) | DFF | 1954 → present | Effective Federal Funds Rate |
| Yahoo Finance | SPY, QQQ | SPY: 1993-01-29+, QQQ: 1999-03-10+ | ETF inception dates enforced |

## Key Results (v2 corrected)

### QQQ — Strongly Hawkish regime
- **3M mean return: -7.0%** (vs +3.2% baseline)
- **77.6% probability of negative 3M return** (vs 31.4% baseline)
- **3M MDD 10th percentile: -26.7%**
- Signal fires ~3.6% of the time

### SPY — Strongly Hawkish regime
- **3M mean return: -1.3%** (vs +2.4% baseline)
- **53.9% probability of negative 3M return** (vs 30.3% baseline)

## Files

- `hawkish_path_backtest_v2.py` — Main backtest script
- `hawkish_path_v2_results.csv` — Regime-conditional return statistics
- `hawkish_path_v2_signal.csv` — Daily signal timeseries (1990-2026)

## Running

```bash
python3 hawkish_path_backtest_v2.py
```

Requires: `pandas`, `numpy`, `yfinance`, network access for Kim-Wright download.
