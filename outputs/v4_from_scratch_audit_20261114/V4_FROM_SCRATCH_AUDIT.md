# V4 from-scratch audit (`Symmetric_Sharpe_Top2_V4` + built-in Election Reset), 2026-11-14

**Script:** [audit_v4_from_scratch.py](file:///Users/happygolucky/Desktop/宏观观察器/audit_v4_from_scratch.py). It shares no code with the official engine or the panel builder.
**Outputs:** `outputs/v4_from_scratch_audit_20261114/` (ledgers, daily NAV, cross-vendor check, robustness grid, log)

## Verdict

| Question | Answer |
|---|---|
| Does the code do what the spec says? | **Yes.** Picks and returns reproduce exactly. |
| Is the data behind the picks sound? | **Mostly yes.** Two residual risks are listed below. |
| Look-ahead bias? | **None found** in membership, features, returns or SEP timing. Sector labels were only partly checked. |
| Is 60.78% CAGR a reliable expectation? | **No.** About 11pp of it comes from a regime switch tested in a single tightening cycle. Returns are highly concentrated and recent. The Election Reset does not hold up for V4. |

## 1. Engineering checks (passed)

| Check | Result |
|---|---|
| Membership rebuilt from raw NDX yaml / S&P csv | 0 mismatched months out of 215 (both indexes) |
| 12-1 mom/vol recomputed from raw daily files (21,899 NDX + 19,120 S&P rows) | Matches. 8 rows differ, all from the panel's flat-price filter |
| My selection code run on the panel features vs the official ledger | 0 pick mismatches; max monthly return diff 1.4e-6; CAGR **60.78%**, Sharpe **1.444**, MDD **-27.99%** |
| V4 run on features I recomputed from raw files | CAGR 60.68%: only 3 months differ (2009-05..07, VRTX↔APOL) |
| Invested positions (422 stock-months, 82 tickers) | 0 missing returns. 415 open-to-open; 5 "delist_last_close" (VMED/FOX/FOXA are real corporate events; the 2 from 2026-10 are just data end) |
| Cross-vendor check | 297 of 422 positions have a second vendor; **0 differ by >1%** |
| Unpriced NDX names (CTRP, FB, WLTW, SYMC, …) | Re-priced via successor tickers: at most rank 3–4 in 4 months; **0 pick changes** |
| Daily MaxDD (open-executed daily NAV, rebuilt) | **-37.32%** (2020-02-19 → 2020-03-23). 2026: **-18.88%**. Both claims reproduce. Before this, no script in the repo computed them |
| Cost stress | 25 / 50 / 100 bp per side → 59.0% / 56.1% / 50.5% CAGR |

## 2. Material findings (ranked)

### F1 (critical): the regime overlay was tested in one tightening cycle
- ALFRED SEP medians **start 2015-12**. So 2009-01..2015-11 is `SEP = ON` by construction, not by signal.
- All **34** `SEP = OFF` months fall in **2021-10..2026-10**. They form 5 episodes of a single tightening/inflation cycle, and the exit rule was written after seeing 2022.
- Contribution: 60.8% CAGR with the overlay vs **50.6%** without (49.3% with no overlay and no Election Reset). Monthly MDD -28% vs -35%.
- Inside the 34 OFF months: V4 **+92%** vs staying in QQQ-top2 **-40%**. Almost all of that is episode 1 (2021-10..2023-03: +47.5% vs -16.7%) and episode 5 (2026-07..10: +23.3% vs -27.8%).
- Partial out-of-sample evidence: the rule did *not* fire in the 2016–2018 hiking cycle, and V4 did well then. That is one cycle of non-firing, not validation of firing.

### F2 (major): the Election Reset does not survive in V4
- The spec justifies it with Decembers of **-7.4 / -8.5 / -10.5%**. Those are **V3 A1-RS** numbers. Under V4 the trigger Decembers were **-2.0% (2010), -3.9% (2018), -3.1% (2022)**.
- V4's worst Decembers were 2024 (**-10.3%**) and 2017 (**-8.2%**), neither of them a trigger year.
- Permutation test: going to cash in the 3 trigger Decembers ranks in the **top 10.7%** of all 680 possible 3-December sets. That is not distinctive, even before accounting for the years being picked after the fact.
- It adds +1.1pp CAGR based on 3 events. **I made it the V4 default at your request last turn; this audit does not support that.**

### F3 (major): returns are concentrated and recent

| Period | V4 CAGR / Sharpe | QQQ CAGR / Sharpe |
|---|---|---|
| 2009–2014 | 38.9% / 1.30 | 24.4% / **1.43** |
| 2015–2020 | 64.7% / 1.50 | 21.4% / 1.08 |
| 2021–2026-10 | 82.3% / 1.54 | 15.7% / 0.67 |

- Best 10 of 214 months = **35%** of total log-wealth. Dropping them → 38.6% CAGR; dropping the best 20 → 25.3%.
- Top 5 tickers (NVDA, TSLA, BIDU, WDC, STX) = **51%** of summed position contribution.
- 2026 alone is +308.5% in 10 months: STX/WDC in Jan and Apr (+39.9%, +56.5%).
- Weak years: 2009 +21% vs QQQ +57%; 2023 **+2.5% vs +52%**; 2019 +30% vs +43%.

### F4 (moderate): the parameters sit on the in-sample peak
- Hold-k: 2 → 51.6%, 3 → 54.7%, 4 → 57.6%, **5 → 60.8%**, 6 → 61.1%, 8 → 55.5%, 10 → 50.7%. It is a plateau, but the chosen value is at its top.
- Top-1 → 68.2% CAGR but -36.5% MDD. Top-3 → 52.6%. Raw momentum instead of Sharpe → 56.9% CAGR, Sharpe 1.15, MDD -47.5%.
- Rough out-of-sample haircut for choosing k and N in-sample: 5–10pp.

### F5 (info): the statistics say real alpha, uncertain size
- Alpha vs QQQ **32.5%/yr, Newey-West t = 4.33**, beta 1.08.
- Deflated Sharpe ≈ 1.00 for N = 1,112–5,000 trials (with an assumed Sharpe dispersion of 0.1–0.2).
- Block bootstrap 95% CI: CAGR **39%–89%**; CAGR minus QQQ **+20% to +67%**; Sharpe minus QQQ **-0.01 to +0.82** (the risk-adjusted edge is not certain).
- The momentum edge is unlikely to be pure noise. The 60% point estimate is not a forecast.

### F6 (minor): data and implementation residuals
- **125 of 422 positions are single-vendor.** That includes every 2025–2026 OFF-regime pick (NRG, VST, APA, VLO, MPC). The live picks cannot be cross-checked from local data.
- Sector labels fall back to the current `sectors.csv` when snapshots are missing; I did not audit this row by row for BestSec months.
- The S&P membership csv ends **2026-08-18**, so Sept–Oct 2026 index changes are missing.
- The last month (2026-10) runs only to the Oct 29 close but is counted as a full month in CAGR.
- The QQQ buffer keeps updating during OFF months, so re-entry uses "virtual" holdings. This is consistent with the spec but undocumented.
- Live trading: about 100% short-term gains (tax drag not modeled); each 50% single-stock position carries gap risk.

## 3. Corrections to my earlier statements
- Last turn I first published wrong win-rate numbers for V4+ER (68.50%) and then corrected them (70.97%, 88/124). The corrected figures are in the spec.
- Earlier I said V4 picked "REGN/BIIB in 2012–14, MNST in 2015, CEG in 2024". The ledger shows BIIB 2011-12..2012-03, REGN 2013-01 only, **MNST 2012-04 (not 2015)**, CEG 2023-04 and 2024-05..06.

## 4. Recommendations
1. Plan around **~45–50% CAGR without the overlay** as the structural core, and treat the SEP overlay as a single-cycle hypothesis. Size it so that it failing in the next cycle is survivable.
2. **Revert the Election Reset to optional** (or remove it from V4) and fix the spec's V3-derived December figures.
3. Before the 2026-11-30 close: confirm the Nov 3, 2026 midterm result from an official source if you keep the Reset, and verify VLO/MPC prices against a second vendor.
4. Refresh the S&P membership file past 2026-08-18.
