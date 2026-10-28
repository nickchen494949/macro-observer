# Independent audit: sector × stock 12-1 momentum backtest

Auditor: independent subagent (I did not build this backtest). I changed no project files. All my checks are read-only scripts in
`/Users/happygolucky/.gemini/antigravity/brain/ef62da80-f524-4a3b-a2be-5ac9449de549/scratch/` (`replicate.py`, `stats_check.py`, `pit_prod.py`, `app_test.py`, `jumps.py`).
They call `bt.load_prices(cutoff='2099-12-31')`, which skips every CSV write.

**Replication:** my rerun of SPEC matches `results/monthly_SPEC.csv` exactly: 213/213 picks identical, max |net diff| = 1e-16.

## Bottom line

- **No look-ahead found in prices, signals or returns.** I added my own truncation test on the production configuration (see C1). It also found 0 differing picks.
- **The data errors I found are real but small for the headline.** Two are identity errors where the acquiring company took over the target's ticker (AGN, JCI). The rest are wrong sector labels. Correcting the provable ones changes 10 of 149 IS picks and 2 of 64 OOS picks:
  - IS CAGR moves by about ±0.5pp (4.8% → 4.4–5.2%).
  - OOS CAGR moves by 2pp (87.4% → 85.2%).
- **The main risk is how the OOS number is read, not a bug.** The OOS result rests on about 5 months. REPORT.md's provisional conclusion ("no evidence of a stable edge, lottery-like") is supported. The OOS numbers should not be cited as evidence that the strategy works.

---

## MAJOR

### M1. The OOS result is fragile, depends on one regime, and SPEC is the OOS maximum of 96 configs
Evidence from `stats_check.py` (net, alpha against SPY, Newey-West t):

| OOS variant | CAGR | Sharpe | alpha | NW t |
|---|---|---|---|---|
| As reported | 87.4% | 1.18 | 62% | 2.33 |
| SNDK months (2026-03..09) replaced by SPY | 58.5% | 1.04 | 42% | 1.93 |
| SNDK + WBD months replaced by SPY | 44.8% | 0.95 | 31% | 1.42 |
| Drop top 3 months | 43.9% | 0.88 | 39% | 1.64 |
| Drop top 5 of 64 months | 27.3% | **0.67 (= SPY OOS 0.67)** | 24% | 1.10 |
| 2021-06..2025-12 only (before SNDK) | 50.1% | 0.93 | 36% | 1.56 |
| Monthly returns capped at +30% | 59.7% | 1.08 | 44% | 1.99 |

- **Sharpe uncertainty is wide.** OOS monthly returns have skew 0.81 and kurtosis 4.97. The skew/kurtosis-adjusted standard error (Mertens) gives a 95% CI for annual Sharpe of **[0.39, 1.96]**, which includes SPY's 0.67.
- **SPEC is an outlier in the grid.** It ranks **#1 of 96 configs OOS** (`grid_is_oos.csv`) but #94 of 96 in the IS selection window. All of the best OOS cells use look=12 with n_sec 1–2. The IS→OOS rank correlation is −0.23.
  - SPEC was user-specified, not selected, so this is not formal selection bias.
  - But any statement that "SPEC works OOS" picks the best of 96 OOS paths. Deflated Sharpe of SPEC's OOS series, using the 96 OOS Sharpes as the trial set (`deflated_sharpe` with OOS inputs), is **0.81**, below 0.95.
- **IS failure:** IS Sharpe 0.29, alpha −2.6% (t −0.25). SPEC trails SPY in 8 of 12 calendar years from 2009 to 2020.
- **The sector step adds nothing.** SPEC picks the same stock as the no-filter top-1 in 59% of OOS months but only 21% of IS months, so the OOS "agreement" is a regime effect. The paired bootstrap matches the report: P(SPEC ≤ no-filter) is 0.92 IS and 0.53 OOS.
- **The bootstrap is easy to misread.** "P(Sharpe≤0) = 0.001" and "SPEC−SPY P(diff≤0) = 0.002" are percentile-bootstrap tail shares, not null-hypothesis p-values.
  - The difference uses *arithmetic* mean returns. At 70% volatility the arithmetic-minus-geometric gap is about 25%/yr, which inflates "SPEC minus SPY ann. mean diff" (median +71%/yr).

### M2. Identity errors when the acquirer adopted the target's ticker (alias and integrity logic cannot detect these)
`ticker_aliases.py` and `check_integrity` only catch renames, re-used symbols and price gaps. A ticker taken over in a merger, inside one continuous membership spell, passes silently.

- **AGN (proven, affects one SPEC pick).** The `AGN` membership spell runs 1996-01-02..2020-05-12, but Allergan Inc. (CIK 850693) was acquired in 2015. Both `data/raw_tiingo/AGN.json` and `data/raw_wiki/AGN.json` contain the *acquirer* Actavis/Watson price history before 2015:
  - Close 2013-02-28 = 85.16 and 2014-01-31 = 188.98, which matches Actavis.
  - Allergan Inc traded about \$108–115 over that period.
  - So the SPEC pick **2014-03 AGN** (momentum 1.22, return −6.8%) is Actavis's signal and return. Dropping pre-2015 AGN makes the pick GILD (`replicate.py`, `fixsec_noAGN`).
  - It also contaminates the Health Care sector average for 2009–2015.
- **JCI (proven, universe only).** Yahoo `JCI` before 2016-09 is **Tyco International**: close 2013-12 = 42.97 = TYC 41.04 / 0.955 reverse-split factor, and the same holds for 2014 and 2015. Old Johnson Controls Inc. (then Consumer Discretionary) is effectively missing, and Tyco sits in the universe under the JCI label.
- **DD (suspicious, not resolved).** Yahoo `DD` close at 2013-12 is 79.32, while E.I. du Pont traded at about \$65. It may be a scaled DowDuPont/Dow series.
- **Recommendation:** for every single-spell ticker with a known merger in which the acquirer took the name, compare the price series against a known historical close for the target at one or two dates. Candidates: AGN, JCI, DD, CCE (2010), LIN, KHC, MDT, ABBV, DWDP, BHGE (already handled).

## MINOR (they do not change the conclusion)

### m1. Sector classification uses today's labels or SIC approximations
`backtest.py:579-588` gives 214 former members a sector derived from SEC SIC codes (`cik_map.csv`, `sector_source == sic_approx`). Several are wrong:
- HAR → Industrials (should be Cons. Disc.)
- ARG, SIAL → Cons. Disc. (should be Materials)
- SRCL → Utilities (should be Industrials)
- APOL, ATGE → Industrials (should be Cons. Disc.)
- TSS → Industrials (should be IT before 2019)
- TWTR → IT even after 2018-09-24 (should be Communication Services)

Effect on SPEC picks:
- HAR (2014-05, 2014-06) and TWTR (2018-10, +22%) were picked through these labels.
- Fixing the 8 labels changes **9 IS picks**. IS CAGR goes 4.8% → 5.2%, Sharpe 0.29 → 0.31. OOS is unchanged.

Today's GICS also leaks into OOS: **APP was Information Technology when added on 2025-09-22** (S&P announcement) but is labelled Communication Services/Advertising in `sectors.csv`. Fixing it changes the 2025-10 and 2025-11 picks: OOS CAGR 87.4% → 85.2%, Sharpe 1.18 → 1.16.

### m2. The truncation test ran on a different universe than production, and it only covers prices
- **Universe mismatch.** `pit_truncation_test.py:27-33` builds sectors **without** the `sic_approx` fallback that `backtest.py` uses.
  - I re-ran the test on the production configuration (`pit_prod.py`): SPEC, NO-SECTOR and ETF, with cuts at 2011-06, 2014-12, 2018-03, 2021-04, 2024-06 and 2026-01. Result: **0 differing picks**.
- **Static inputs are not truncated.** Membership, sectors, MANUAL/TIME_SPLIT aliases and `sec_successor_aliases.csv` (today's SEC tickers) are fixed files built today.
  - Aliases only decide identity, not returns, so that is acceptable.
  - Sectors are the only remaining hindsight channel (m1).

### m3. Fixable coverage gaps (Missing Data Rule)
`missing_members.csv`, `coverage_funnel_by_month.csv`:

| Ticker | Problem | Months lost | Likely fix |
|---|---|---|---|
| FRC | `sector_unknown` | 52 | It is Financials |
| HFC | no price data | 36 | Successor DINO, same CIK |
| CDAY | no price data | 29 | Now DAY |
| WRK | `insufficient_history` for its whole spell | 86 | — |
| INFO | `insufficient_history` | 57 | — |
| PARA | 2022-02..2025-07 spell excluded | 42 | — |
| APC, STI, CBS, FOX/FOXA | data hole 2018-04..2019/20 caused by the WIKI freeze | — | — |

`untrusted_spells` (`backtest.py:117`) is stricter than it needs to be. It requires the series to start by 2007-01-20, which excludes GENZ (data from 2008-01-24) and KG (data from 2008-05) for 2009–2011 even though they have valid prices. 12-1 momentum from the 2008-12 formation only needs data from 2007-12.

Membership coverage is 89.8% at the start, 98.8% median and about 100% in OOS. The gaps mostly affect IS sector averages, not picks.

### m4. No outlier or split check on Tiingo/WIKI prices
Examples:
- RRD +214% on 2016-10-03 (reverse split not adjusted; outside its spell).
- MIL ×7 one-day spike on 2009-11-16 (stock ineligible).
- **CCE −30.8% on 2010-10-04** inside its S&P spell: WIKI `adj_close` does not adjust the \$10 cash distribution from the KO deal, and the old and new CCE are spliced with no gap. This biases Consumer Staples momentum for 2010–11.

None of these occur in a SPEC holding month. I scanned every daily move >25% inside SPEC holding months; all are real events:
- TMUS/MetroPCS −36.6% on 2011-08-02 (earnings)
- FSLR +26.5% on 2023-05-12
- VST −28% on 2025-01-27 (DeepSeek)
- WBD +29% on 2025-09-11 (Paramount bid)
- SNDK +26% on 2026-07-30

### m5. Mid-month delistings are labelled as normal exits
`daily.resample('ME').last()` (`backtest.py:264`) carries a stale last price to month-end. HSP 2015-09 was acquired, with its last trade on 2015-09-02, yet it is logged as status `ok` instead of `last_trade_in_month`. The return effect is about zero (\$90 cash deal). Still, the REPORT claim that all 213 positions had a normal next-month price is slightly inaccurate.

### m6. REPORT wording
"SNDK went from \$32 to over \$2,000" describes the stock, not the strategy. The strategy held SNDK from \$635 (formation 2026-02-28) to \$1,740 (2026-09-30), a log contribution of 1.005 (about +173%).

Also, the 2026 SNDK and WDC prices come from a single source (Yahoo) and are past my knowledge cutoff. Internally they are consistent (close = adjclose, no split artifacts), but I could not verify them independently. Since OOS depends on them, cross-check against a second source.

### m7. Small technical points
- Next-day-close fallback window (`Prices.ret`) still ends at month-end t+1 rather than the first trading day after it.
- In the ETF score variant, Telecom and IT share the XLK score (ties).
- NW lag 3 is ad hoc.

None of these is material.

## Verified correct (no issue)
- **Momentum:** `P.shift(1)/P.shift(look)-1` gives P[t-1]/P[t-12]. The segment guard stops momentum and returns from bridging a gap of more than 30 days (`backtest.py:356-361`, `:325-328`).
- **Returns:** month-end adjclose from t to t+1. Spot-checked against both close and adjclose:
  - WBD 2025-09: 11.64 → 19.53 = +67.8%, real (Paramount bid). Uses Tiingo because Yahoo's WBD file has one row.
  - TMUS 2011-08 −31.4%: MetroPCS history (fja lists PCS as TMUS for the 2009–2013 spell; Yahoo TMUS history is MetroPCS).
  - AMD 2020-03 0.0%: closed at 45.48 on both month-ends, real.
  - COG 2012-01 split handled.
  - DISCA 2018-12 −19.5%.
  - LB 2021-07 +11%.
  - CHK 2017 and GNW/WYND/TGNA 2009–10 momentum consistent with actual prices.
- **Membership at formation:** checked for every suspicious pick, including SNDK. The new SNDK spell starts 2025-11-28, and SNDK was first picked at the 2026-02-28 formation. Its 2016 and 2025 price segments are kept apart; momentum 11.30 = 576.25 / 46.85 − 1.
- **Costs:** turnover math is correct (first buy 10bp, switch A→B 20bp, hold 0).
- **Next-day execution:** entry is the first trading day after month-end (checked 2020-05-31 → 06-01 and 2026-01-31 → 02-02).
- **SPY benchmark:** same timing as the strategy.
- **IS split:** 149 IS months ending 2021-05. The selection window is 148 months ending **2021-04-30**.
- **Risk-free rate and statistics:** rf = DGS3MO observed at t, converted to monthly. Sharpe uses excess returns. NW-OLS sandwich is correct. Deflated Sharpe formula (Bailey & López de Prado, raw kurtosis, N = 96 distinct series) is correct; it was computed on the IS window only.


---

## Follow-up (2026-10-28 11:4x): sector list and identity details. **Two corrections to the findings above.**

### Correction 1: the sector problem (m1) is MAJOR, not minor
I re-ran the backtest with every mis-sectored ticker corrected, not only the 8 from the first pass. Scripts: `scratch/fixall.py` and the attribution run.

| Run | Picks changed | IS CAGR / Sharpe | OOS CAGR / Sharpe | OOS alpha t (NW) |
|---|---|---|---|---|
| As reported | 0 | 4.8% / 0.29 | 87.4% / 1.18 | 2.33 |
| Only EA, ATVI, IPG → Comm. Services from 2018-09-24 | 8 | 7.3% / 0.36 | **70.3% / 1.09** | 1.88 |
| All high-confidence fixes | 38 | 12.6% / 0.53 | **71.3% / 1.10** | 1.92 |
| All fixes, including medium-confidence | 35 | 15.2% / 0.59 | 71.3% / 1.10 | 1.92 |

- **The WBD 2025-09 pick (+67.8%) disappears.** Once EA (Interactive Home Entertainment) and IPG (Advertising) count as Communication Services, that sector's average drops and the pick becomes VST (+3.5%).
- **The IS changes come mostly from Telecom.** The SIC fallback had sent FTR, WIN and LVLT to Consumer Discretionary as a default guess. Adding them back to the small Telecom sector changes its average, so Telecom is picked less often.
- **What does not change:** IS is still below SPY (15.4%), and OOS is still concentrated. The point is that the reported numbers are sensitive to sector labels by ±10–17pp.

### Correction 2: AGN and JCI are mostly label collisions, not wrong returns (downgrade to minor). DD is a real wrong-company price
The fja05680 membership file relabels tickers retroactively. In 2009–2015 it has one `AGN` entry and no ACT/WPI entry. Wikipedia changes says Actavis was added 1999-04-12 and Allergan was removed 2015-03-23. So two real members (Allergan Inc. and Watson/Actavis) collapse into one `AGN` label, and that label is priced as Actavis.
- **AGN:** Actavis *was* an S&P member, so the 2014-03 `AGN` pick is a valid, investable pick of Actavis. What is wrong is that Allergan Inc. is missing from the universe and the label is ambiguous.
- **JCI:** Wikipedia records Tyco being added 2010-08-26 and "TYC acquired JCI and retained JCI ticker" on 2016-09-06. One `JCI` entry is priced as Tyco.
  - 2010-08-26..2016-09: Tyco is a real member; Johnson Controls Inc. is missing.
  - **2009-01..2010-08:** the `JCI` entry is priced as Tyco while Tyco was **not** a member, so a non-member sits in the universe for about 20 months.
- **DD (wrong company, proven).** The membership file has **separate** spells: `DD` 1996-01-02..2017-09-01 (E.I. du Pont) and `DOW` 1996-01-02..2017-09-01 (Dow Chemical). But Yahoo `DD` before 2017-09-01 is **Dow Chemical**:
  - 2014-01..06 monthly returns are identical to `raw_wiki/DOW.json`.
  - Dividing the 2013-12 close of 79.32 by Yahoo's cumulative split factor of 1.786 gives 44.41, Dow's actual close (44.40).
  - Result: E.I. du Pont is missing, Dow Chemical is counted twice (`DOW` from WIKI plus `DD` from Yahoo), and the duplicate is labelled **Industrials** (today's "Industrial Conglomerates").
  - Wrong DD periods by source:

    | Period | Yahoo DD contains | Problem |
    |---|---|---|
    | 2007-01..2017-08-31 | Dow Chemical | wrong for the DD spell, which is E.I. du Pont |
    | 2017-09-01..2019-06-02 | DowDuPont | DD is not a member then; the actual member is DWDP, which only has WIKI data to 2018-03 and is ineligible |
    | 2019-06-03 onward | DuPont de Nemours | correct company |

  - On 2019-06-03 Yahoo shows an artificial **+17.8% one-day adjclose move**: the Corteva spin-off and the 1:3 reverse split were booked together as one split factor of 0.4725.
  - Because there is no gap, DD's momentum for formations 2019-06..2020-05 bridges into DowDuPont/Dow prices and includes that +17.8%.
  - Neither Tiingo nor WIKI has a DD file.
- **CCE.** One spell (1998..2016-05-31) covers two companies. The WIKI series splices old CCE (to 2010-10-01) and new CCE (from 2010-10-04) with no gap, and shows a −30.8% day that is really the \$10 cash payment in the KO deal. This contaminates CCE momentum for formations 2010-10..2011-09.
- **Other cases I checked and found consistent:** MYL/VTRS, TFC/BBT, WTW/WLTW, ESRX, MDT, CI, UAL, KHC/KRFT, DOW 2019, LIN/PX, ARNC/HWM (Alcoa legal entity), CTRA/COG, WBD/DISCA, and TMUS 2009–13 (MetroPCS history, membership labelled TMUS).
- **Not checked (lower risk):** EVHC (AmSurg history), FTI (FMC Technologies → TechnipFMC), AAL (Yahoo history before 2013-12 = US Airways, but the AAL spell starts 2015-03, so it does not matter).

### Full list of mis-sectored tickers
"Effective" = the sector actually used in `secP`, after the SIC fallback and alias inheritance. Confidence:
- **web** = confirmed by a web source today
- **high** = well-known GICS assignment from general knowledge
- **med** = believed correct; verify before using

| Ticker | Effective sector | Correct GICS at the time | Change during membership | Conf. |
|---|---|---|---|---|
| TWTR | IT (whole spell) | IT until 2018-09-21 close, then Comm. Services | 2018-09-24 (S&P 2018 GICS change, effective after close 2018-09-21) | web |
| APP | Comm. Services (whole spell) | **IT (Application Software)** from S&P add 2025-09-22, then Comm. Services (Advertising) | **as of close 2026-07-31** (MSCI GICS change announcement): formations ≤ 2026-06-30 should be IT; the 2026-07-31 formation is already CS | web |
| EA | IT (whole spell) | IT, then Comm. Services (Interactive Home Entertainment) | 2018-09-24 | high |
| ATVI | IT | IT, then Comm. Services | 2018-09-24 | high |
| IPG | Industrials | Cons. Disc. (Media/Advertising), then Comm. Services | 2018-09-24 | high |
| WBA | Cons. Disc. | Consumer Staples (drug retail), whole 2009–2025-08 | — | high |
| HAR | Industrials | Cons. Disc. (consumer electronics) | — | high |
| ESRX | Cons. Disc. | Health Care | — | high |
| MHS (Medco) | Cons. Disc. | Health Care | — | high |
| CERN | IT | Health Care (Health Care Technology) | — | high |
| ARG (Airgas) | Cons. Disc. | Materials (industrial gases) | — | high |
| SIAL | Cons. Disc. | Materials | — | high |
| SRCL | Utilities | Industrials | — | high |
| BTUUQ, ANRZQ, MEE (coal) | Materials | Energy (Coal & Consumable Fuels) | — | high |
| CAM (Cameron) | Industrials | Energy | — | high |
| BHGE (incl. BHI before 2017) | Industrials | Energy | — | high |
| CBE (Cooper Ind.) | IT | Industrials | — | high |
| PCP | Materials | Industrials (Aerospace & Defense) | — | high |
| TSS | Industrials | IT (spell ended 2019, before the 2023 change) | — | high |
| ADS (Alliance Data) | Financials | IT (data processing; spell 2013–2020) | — | high |
| FTR, WIN, LVLT | Cons. Disc. (`guess_2018` default, because the SIC fallback has no sub-industry) | Telecommunication Services (all spells ended before 2018-09) | — | high |
| IGT | Industrials | Cons. Disc. (casinos & gaming) | — | high |
| APOL, ATGE | Industrials | Cons. Disc. (education services) | — | high |
| FBHS | Materials | Industrials (building products) | — | high |
| HRS (Harris) | Industrials (inherited from LHX) | IT (communications equipment) until the 2019-06 L3 merger | — | med |
| LLL | IT | Industrials (Aerospace & Defense) | — | med |
| FLIR | Industrials | IT (electronic equipment) | — | med |
| INFO (IHS Markit) | IT | Industrials (research & consulting); mostly ineligible anyway | — | med |
| ARNC | Industrials (inherited from HWM) | Materials (Alcoa Inc) until the 2016-11-01 split, then Industrials (Arconic) | 2016-11-01 | med |
| DD | Industrials (today's Wikipedia) | Materials for E.I. du Pont and for DuPont de Nemours (2019+); date of any later move to Industrials unknown | ? | med |
| CDAY / DAY | IT | IT until 2023-03-17, Industrials after (the builder's own `MOVED_2023_IT_TO_IND` list says so, but the fallback ignores it) | 2023-03-20 | med |

Structural root causes:
1. **The SIC fallback has no sub-industry.** So `historical_sectors.py` cannot apply the 2018 and 2023 rebuilds to these tickers: Comm. Services always becomes Cons. Disc. before 2018 (wrong for telecoms), and IT never moves to Comm. Services after 2018.
2. **Today's GICS is applied to current members (APP).**
3. **Aliased tickers inherit the successor's sector (HRS ← LHX, ARNC ← HWM).**
