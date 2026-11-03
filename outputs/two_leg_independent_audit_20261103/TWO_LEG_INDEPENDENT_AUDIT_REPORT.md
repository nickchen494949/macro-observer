# Independent From-Scratch Audit — 2-Leg Strategy `G1_SPY_2e`

- **Audit date**: 2026-11-03 · **Sample**: 213 holding months, 2009-01 … 2026-09, plus a live mark of Oct 2026
- **Strategy under audit (frozen, unchanged)**
  - **Leg A, 50%**: Nasdaq-100 members ranked by `mom_12_1 / vol_12_1`. Buy the Top-2 and keep a holding while it stays within the Top-5.
  - **Leg B, 50%**: S&P 500 members ranked by raw `mom_12_1`. Buy the Top-1 and keep it while it stays within the Top-3.
  - **Signal and execution**: signal at the month-end close, trade at the next session's adjusted open, hold until the first open of the following month. Costs are 10 bp per side, leverage 1.0x, cash earns 0%.

## Method

1. I wrote a new engine (`ind_engine.py`) that shares **no code** with the project pipeline (`a2_engine`, `c2_engine`, `backtest.py`, `run_qqq_spy_g1_audit.py`).
2. It reads raw inputs only:
   - Nasdaq-100 membership: jmccarrell YAML change logs.
   - S&P 500 membership: fja05680 daily snapshots.
   - Prices: raw Yahoo, Tiingo, Quandl-WIKI and archive files.
3. It rebuilds features, picks, returns, costs, the daily NAV and the statistics. It is then reconciled month by month against the claimed ledger (`claimed_G1_SPY_2e_ledger.csv`).

## 1. Verdict

| Check | Result |
|---|---|
| Picks: independent vs claimed, both legs | **213 / 213 months identical** |
| Look-ahead, physical truncation of every raw file at 2012-12, 2018-06 and 2022-12 | **0.0 score difference; picks identical** |
| Every pick is an index member at formation (raw source) | **639 / 639** |
| Second membership source (Wikipedia) | All consistent. Flags examined: CERN 2009-07/08 is a stale Wikipedia revision (Cerner replaced Sun on 2009-07-17). AN 2009-08/09 is a parse ambiguity (AutoNation was a member until 2017). |
| Pick-month returns matching the claimed engine within 1 bp | 611 / 639. The rest are explained in §2. |
| Pick-months confirmed by at least 2 price vendors | 484 / 639, max spread 0.91% (LUV 2015, WIKI) |
| Pick-months with \|ret\| > 30% | 29 in total. 26 are confirmed by 2–3 vendors. 3 are single-vendor but match known events: PCLN 2009-11, NKTR 2018-06 (−39%), DVN 2022-05. |

**Conclusion: the strategy is computed correctly.** The claimed headline is slightly overstated, by about 0.26 pp of CAGR. The causes are minor and listed below.

### How the first-pass disagreements were resolved

The first independent pass gave 47.48% CAGR and differed in 20 months. **Every difference traced back to gaps in the independent engine, not errors in the claimed engine.**

- **Missing renamed tickers**: HANS→MNST, TEVA (raw_ndx), FOX/FOXA→TFCF/TFCFA, HFC→DINO, BLL→BALL, NLOK→GEN, LB→BBWI, FER (raw_ndx).
- **One wrong vendor adjustment**: IACI on 2008-08-21, where Tiingo implies +50.9% against the true package return of +10.31%.

After adding these 8 documented same-entity aliases and the 1 corporate-action fix, all 213 months matched.

## 2. Defects found in the claimed engine (all minor)

| # | Defect | Impact |
|---|---|---|
| D1 | **Close-proxy fallback.** In 8 pick-months (COG 2011-09…2012-02, TGNA 2010-07) the engine used first-session close→close instead of open→open. Its open-price scale check rejected valid WIKI opens. | CAGR overstated by about **0.22 pp** |
| D2 | **Cross-leg rebalancing cost not charged.** The sleeve-additive accounting skips the cost of moving the two legs back to 50/50 each month. | about **0.04 pp** |
| D3 | `rank_sleeve_candidates_at_t` drops candidates whose future `hold_ret` is missing. This is a look-ahead pattern in the code. | 3 rows in total, none in the Top-5, so **0 impact**, but it should be removed |
| D4 | The reported "Daily MaxDD (5651ec2)" restarts each month's path at the first-day close, so it skips the move from entry open to first close. | Reported −40.30% vs true mark-to-market **−40.85%** |
| D5 | FOX/FOXA in Mar 2019 exits at the last TFCF trade ($49.61) on deal close. This is an approximation of the Disney + New Fox package. | Small; one month at 25% weight |

## 3. Audited numbers (independent engine, single account, costs fully charged)

| Metric | Claimed | **Audited** |
|---|---:|---:|
| CAGR 2009-01…2026-09 | 50.23% | **49.97%** |
| Excess Sharpe (3M T-bill) | 1.278 | **1.274** |
| Monthly MaxDD | −27.12% | **−27.15%** |
| True daily MaxDD (open entry, daily closes) | −40.30% | **−40.85%** (2026-06-18 → 2026-09-15) |
| CAGR 2009–2018 / 2019–2026 | 39.31% / — | **38.90% / 65.58%** |
| 2022 | +9.09% | **+9.04%** |
| Cost stress 20 / 30 / 50 bp per side | — | 48.98% / 47.99% / 46.02% |
| Newey-West t of monthly excess vs QQQ / SPY | — | **3.12 / 3.81** |
| Stationary bootstrap CAGR, 5% / 50% / 95% | — | 32.0% / 49.9% / 72.2% |
| Benchmarks: QQQ / SPY, same window | — | 20.87% / 14.82% |

**Calendar years**: 2009 31.9, 2010 −2.8, 2011 46.6, 2012 17.1, 2013 24.7, 2014 126.2, 2015 8.8, 2016 100.7, 2017 81.9, 2018 8.4, 2019 57.2, 2020 79.0, 2021 15.9, 2022 9.0, 2023 7.4, 2024 141.8, 2025 97.7, 2026 YTD (to Sep) 172.8.

**Multiple testing**: the corrected cumulative DSR (N = 878 trials) is **0.928**, below the strict 0.95 bar (see `08_multiple_testing_dsr.csv`).

## 4. Outside the backtest window — read this

| Item | Value |
|---|---|
| October 2026 holdings (formation 2026-09-30) | 25% WDC + 25% STX + 50% SNDK |
| October 2026 return, marked to the 2026-10-29 close | **−20.0%** |
| Live drawdown from the 2026-06-18 peak, at 2026-10-29 | **−47.1%** |
| Worst live daily drawdown | **−52.4%** on 2026-10-23 |

**The live drawdown is already deeper than the worst drawdown in the 17.75-year backtest (−40.85%).** All three October positions are memory and storage stocks.

**November 2026 holdings (formation 2026-10-31).** MRNA was re-added to the Nasdaq-100 on 2026-10-09, replacing WBD. It ranks #5, which pushes WDC to #6, so WDC is sold.

| Account | QQQ leg | SPY leg | Total |
|---|---|---|---|
| Continuing account | STX + SNDK | SNDK | **75% SNDK + 25% STX** |
| New account | SNDK + MU | SNDK | **75% SNDK + 25% MU** |

## Files

| File | Contents |
|---|---|
| `ind_engine.py` | Independent engine |
| `01_build_independent.py` | Builds the independent panels and ledger |
| `00_freeze_claimed_ledger.py` | Claimed ledger, kept for reference only |
| `02_reconcile.py`, `02_pick_disagreements.csv` | Month-by-month reconciliation; the CSV is now empty |
| `03_diagnose.py` | Side-by-side rankings for the first-pass disagreements |
| `04_pick_return_crosscheck.csv` | Return comparison for every pick-month |
| `05_stats_daily_costs.py`, `05_independent_stats.csv`, `05_independent_daily_nav.csv` | Statistics, cost stress and daily NAV |
| `06_integrity_checks.py`, `06a_truncation_test_independent.csv`, `06b_pick_vendor_crosscheck.csv` | Truncation test and vendor cross-check |
| `07_membership_second_source.py`, `07_spy_pick_membership_wiki.csv` | Wikipedia membership check |
| `08_live_extension.py`, `08_live_extension.log`, `08_daily_nav_with_live_oct2026.csv` | Live October 2026 mark and November holdings |
