# Independent audit: `COMBO A = SEP × min(RV21, VIX) × CTA Baz trim` (2026-11-15)

Script: [`audit_from_scratch.py`](./audit_from_scratch.py) (zero shared code with `combined_macro_vrp_cta_test.py`, `cta_institutional_deep_test.py`, `proxy_sep_incorporation_test.py`). Full log: [`audit_log.txt`](./audit_log.txt).
Rebuilt from raw files; daily simulation with drifting weights inside the month; 10bp/side.

## Verdict
The code is mechanically correct and the headline numbers reproduce to within 0.3pp. There is no look-ahead in the signals (expanding medians, causal EWMAs).
**The conclusions drawn from those numbers are overstated.** COMBO A amounts to "B5 with less TQQQ and a small Sharpe edge". It does not beat B5 at a statistically significant level.

## Reproduction (ETF 2010-04..2026-10, signal close execution)
| Rule | Claimed | Reproduced |
|---|---|---|
| B5 = SEP × w_RV | 37.2% / 1.02 / -34.0% / -45.2% | 37.4% / 1.03 / -34.0% / -45.1% |
| SEP × min(RV,VIX) | 35.0% / 1.05 / -34.0% / -39.7% | 35.3% / 1.05 / -34.0% / -39.4% |
| B0 (no SEP) | 30.0% / 0.94 / -31.5% / -40.0% | 30.3% / 0.95 / -31.5% / -39.9% |
| COMBO A | 32.4% / 1.08 / -28.1% / -35.5% | 32.5% / 1.08 / -28.1% / -35.4% |

## Findings (by severity)
1. **Major: most of the "~10pp smaller drawdown" comes from simply holding less TQQQ.** COMBO A holds 55% TQQQ on average and B5 holds 70%. Scaled down to the same volatility (k = 0.79), B5 returns 30.5% CAGR with a -37.7% daily max drawdown. COMBO A returns 32.5% with -35.4%. The real edge is about +2pp CAGR and 2pp less drawdown.
2. **Major: not statistically significant.** Stationary block bootstrap (12-month blocks, 5000 draws):
   - ETF period: ΔSharpe vs B5 = +0.056, 90% CI -0.04..+0.17, P(≤0) = 0.18. CAGR is 4.9 pp/yr lower than B5 (P = 0.93).
   - 1990–2026 synthetic: ΔSharpe +0.05, P = 0.04, with no CAGR difference. That period overlaps the ETF period, and the rule was picked from about 26 variants after seeing results.
3. **Major: the gain comes from one episode.** COMBO A minus B5 by year: 2020 = +22.7pp (COVID). The cost falls in strong bull years: 2010 -22pp, 2012 -13pp, 2013 -50pp, 2017 -37pp.
4. **Major: the -35.5% daily max drawdown depends on execution timing.**
   - Trading at the next close instead of the signal close: -42.8% (B5: -47.7%).
   - Trading at the next open: -38.2% (B5: -43.3%).
   - COMBO A's worst window is 2015-07..2016-06. Its big down days sit on month boundaries (2015-09-01, 2016-01-04), so a one-day shift changes the result.
5. **Major: the SEP contribution rests on one tightening cycle.** All 35 real SEP=OFF months fall in 2021-09..2026-10.
   - SEP log-wealth contribution: +0.29 in total. 2022 alone is +0.38, so everything outside 2022 nets to -0.09.
   - 2023 cost -71pp (120% → 49%).
   - ΔSharpe +0.13 (P = 0.05), ΔCAGR +2.3% (P = 0.23).
   - Before 2015 the "SEP" is the 2Y/core-PCE proxy, which was ON throughout 2000–02 and 2008.
6. **Major: the "41 years: z ≥ 2 → 3x loses -9.9%/yr" claim doesn't hold.** Next-day return difference between z ≥ 2 and 0.5 ≤ z < 1.5 (HAC t-stats):
   - 1985–1999: t = +0.12
   - 2000–2009: t = +0.02
   - 2010–2026: t = -1.61
   - Full period: t = -1.07

   The effect exists only after 2010 and is not significant even there.
7. **Critical for that claim: the "CTA washout = buying opportunity, +2.77% next 21d" claim is refuted.** The 241 days counted are overlapping days from only **10 independent episodes**. Those 10 episodes average -1.23% over the next 21 days, with a median of -4.17% and a 40% win rate (t = -0.37). The unconditional 21-day average is +1.11%. The "crowded cliff" result (-0.15%, 63% win rate) has the same overlap problem and is effectively zero.
8. **Minor: "exact Baz/AHL, zero tuning" is not accurate.**
   - The code used EWMA `halflife=n`; the paper uses λ = (n-1)/n.
   - It used EWM standard deviations; the paper uses rolling 63/252-day windows.
   - Applying the trim only above √2 is an ad-hoc hybrid.
   - The paper-exact version gives 32.1% / 1.13 / -36.6%, the same direction. Across thresholds 1.0–2.0, the trim raises Sharpe every time (1.08–1.14 vs 1.05 untrimmed) and lowers CAGR. The direction is robust; the size is small.
9. **Minor: the C4 (real SEP OR proxy ON) "improvement" is a wash.** It returns 33.0% / 1.04 / -37.4% vs COMBO A's 32.5% / 1.08 / -35.4%.
10. **Minor: small data issues.**
    - A hard-coded VIX median of 19.0 is used for 11 months in 1990.
    - The live readout mixes timestamps: the month-end QQQ z is +1.16, but the reported z = +0.52 is the 2026-11-13 IXIC reading. The conclusion (SEP OFF → 0% TQQQ) is unchanged.
    - The audited code computed daily max drawdown with daily-rebalanced weights. Redone with drifting weights it moves by only 0.1pp, so this is immaterial.
11. **Not reported in the original:** COMBO A's 1990–2026 synthetic daily max drawdown is **-50.3%**. The VIX brake and the CTA trim do not improve the worst 1990–2026 drawdown at any threshold.

## What survives
- Vol scaling is the robust part: SEP alone at 100% has a -69.9% daily max drawdown; SEP × vol scaling has -45%.
- The CTA trim and the VIX brake give a small, consistent Sharpe gain at a CAGR cost. That is a risk-preference choice, not alpha.
- Realistic next-open figures for 2010–2026: B5 36.8% / 1.01 / -43.3%; COMBO A 32.2% / 1.06 / -38.2%. Expect lower live results: the SEP has been through one cycle, and the sample is a strong Nasdaq period.
