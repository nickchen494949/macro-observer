# Independent From-Scratch Audit — TQQQ SEP + HYG/IEF Credit Gate (2026-11-18)

> Script: [`audit_hyg_ief_from_scratch.py`](../../audit_hyg_ief_from_scratch.py) (imports no strategy code; rebuilds SEP state, Vol_Z, the HYG/IEF signal and the open-executed engine from raw files). Full console output: [`audit_log.txt`](./audit_log.txt).

## Rule audited
Frozen V1-Daily TQQQ SEP, except the `3x -> 1x` de-lever needs **both** `Vol_Z > 1.2` **and** `HYG/IEF < SMA200(HYG/IEF)` (plus the Open-Limit NSL). Everything else unchanged.

## Verdict
**Reproduces exactly, no look-ahead found, and survives a placebo test. But it is not "credit confirmation", the edge rests on 7 decisions, and it carries a specific tail risk the backtest got lucky on. Keep it as a research candidate, not a rule change.**

| Check | Result |
| :--- | :--- |
| T0 Reproduction | Baseline `54.89% / -44.54% / 33 switches`; gated `57.90% / -44.54% / 24 switches`, both exact. |
| T1 Data | HYG/IEF: 0 missing trading days. IEF Tiingo vs Yahoo daily-return correlation 0.993. Dividend-adjusted prices do not create look-ahead in a ratio-vs-SMA test. Signal at d-1 close, trade at d open. **Pass.** |
| T1 Side finding | Local FRED HY OAS (`BAMLH0A0HYM2`) **starts 2023-08-01**. The earlier "P5c real-time HY OAS 2010–2026" result ran on a back-filled constant before that date. **Invalid; discard it.** |
| T2 Attribution | The whole gain comes from **7 episodes**. The two largest (2014-02 and 2024-05) are 80% of it. One episode (2018-10) was a loss worth −37% of the total. |
| T3 Decisions | Of the 12 baseline de-levers, the gate blocked 7 and allowed 5. |
| T4 Placebo | 400 circularly shifted copies of the same signal: only **3.0%** match the real CAGR, and **81%** blow out to a drawdown worse than −50%. The real dates matter: **pass**, with caveats below. |
| T5 Cousins | Mixed: JNK/IEF works, but **HYG/SHY, JNK/SHY and HYG/LQD at SMA200 make things worse** (`51.97% / -58.08%`). |
| T9 Decomposition | The **credit** leg alone (HYG/SHY) fails: `51.97% / -58.08%`, and it blocks the 2011-08 and 2020-02 crash exits. The **rates** leg alone (SHY/IEF) does most of the work: `56.02% / -44.54%`. |
| T6 Credit-only delay | 0–3 day delay: drawdown unchanged (−44.54%). At 4, 9 and 10 days: −50.71%, −49.14%, −54.49%. |
| T7 "20-day non-ratchet NSL" patch | Fixes the 8- and 10-day Vol_Z cliff (−69.92% → about −44%) for **both** baseline and gated. Built after seeing a single episode (2020-02). Fragile in its own parameter: 5 days does not fix it; 10–20 days does. |
| T8 Calendar years | **12 of 17 years identical**. Better in 2014 (+16.9pp), 2017 (+10.0), 2024 (+21.2), 2026 (+6.4); worse in 2018 (−2.4). |
| T10 12-Opportunity Realized Attribution & 7-Signal Decomposition | Exact post-fee realized `Base 1x` vs `Hold 3x` window returns across all 12 baseline `Vol_Z > 1.2` de-levers (`5` genuinely protective trims vs `7` ex-post false alarms), comparing `HYG/IEF`, `HYG/SHY`, `SHY/IEF`, `IEF` standalone, `HYG` standalone, `BOTH`, and `EITHER` on the exact same 12 opportunities ([`T10_12window_realized_and_7signal_decomposition.csv`](./T10_12window_realized_and_7signal_decomposition.csv), [`T10_signal_summary.csv`](./T10_signal_summary.csv)). |

## T10. Exact 12-Window Realized Post-Fee Attribution & 7-Signal Head-to-Head Decomposition

Instead of looking at arbitrary 21-day `QQQ` returns, Table T10A measures the **exact realized post-fee return** from each baseline de-lever signal (`d_sig_close`, executed at `d_exec_open`) until the exact day baseline `1x` and holding `3x` reconverge (`d_reconverge_close`, after all `10bp/side` round-trip fees):

### Table T10A: 12 Baseline `Vol_Z > 1.2` Opportunities — Realized Post-Fee `1x` vs `3x` & 7-Signal Decisions

| # | Signal Close | Exec Open | Reconverge Date | `Vol_Z` | **Base `1x` Post-Fee Ret** | **Hold `3x` Ret** | `1x` Window MaxDD | `3x` Window MaxDD | **True Realized Outcome** | `1. HYG/IEF` | `2. HYG/SHY` *(Credit)* | `3. SHY/IEF` *(Rates)* | `4. IEF` *(Treasury)* | `5. HYG` *(Corp)* | `6. BOTH` *(AND)* | `7. EITHER` *(OR)* |
| :-: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | `2010-05-07` | `2010-05-10` | `2010-07-30` | `1.34` | **`+11.06%`** | `-2.34%` | `-12.48%` | `-34.76%` | **Protective Trim** (`1x` beat `3x`) | `TRIM_1x` ✅ | `HOLD_3x` ❌ | `TRIM_1x` ✅ | `TRIM_1x` ✅ | `HOLD_3x` ❌ | `HOLD_3x` ❌ | `TRIM_1x` ✅ |
| **2** | `2011-08-02` | `2011-08-03` | `2011-12-28` | `1.29` | **`-3.00%`** | `-14.10%` | `-11.93%` | `-34.79%` | **Protective Trim** (`1x` beat `3x`) | `TRIM_1x` ✅ | `HOLD_3x` ❌ | `TRIM_1x` ✅ | `TRIM_1x` ✅ | `HOLD_3x` ❌ | `HOLD_3x` ❌ | `TRIM_1x` ✅ |
| **3** | `2014-01-30` | `2014-01-31` | `2014-03-05` | `1.54` | `+3.27%` | **`+17.55%`** | `-4.85%` | `-7.28%` | **False Alarm** (`3x` beat `1x`) | `HOLD_3x` ✅ | `HOLD_3x` ✅ | `HOLD_3x` ✅ | `TRIM_1x` ❌ | `HOLD_3x` ✅ | `HOLD_3x` ✅ | `HOLD_3x` ✅ |
| **4** | `2014-10-09` | `2014-10-10` | `2014-11-13` | `1.27` | `+5.08%` | **`+18.76%`** | `-6.53%` | `-14.89%` | **False Alarm** (`3x` beat `1x`) | `TRIM_1x` ❌ | `TRIM_1x` ❌ | `TRIM_1x` ❌ | `TRIM_1x` ❌ | `TRIM_1x` ❌ | `TRIM_1x` ❌ | `TRIM_1x` ❌ |
| **5** | `2015-01-08` | `2015-01-09` | `2015-02-23` | `1.39` | `+5.60%` | **`+14.87%`** | `-3.20%` | `-10.29%` | **False Alarm** (`3x` beat `1x`) | `TRIM_1x` ❌ | `TRIM_1x` ❌ | `TRIM_1x` ❌ | `TRIM_1x` ❌ | `TRIM_1x` ❌ | `TRIM_1x` ❌ | `TRIM_1x` ❌ |
| **6** | `2017-06-28` | `2017-06-29` | `2017-07-31` | `1.23` | `-0.36%` | **`+6.46%`** | `-3.70%` | `-8.00%` | **False Alarm** (`3x` beat `1x`) | `HOLD_3x` ✅ | `HOLD_3x` ✅ | `TRIM_1x` ❌ | `TRIM_1x` ❌ | `HOLD_3x` ✅ | `HOLD_3x` ✅ | `TRIM_1x` ❌ |
| **7** | `2017-08-31` | `2017-09-01` | `2017-09-18` | `1.21` | **`-0.43%`** | `-0.55%` | `-1.23%` | `-3.73%` | **Protective Trim** (`-0.12%` tie) | `HOLD_3x` ❌ | `HOLD_3x` ❌ | `TRIM_1x` ✅ | `TRIM_1x` ✅ | `HOLD_3x` ❌ | `HOLD_3x` ❌ | `TRIM_1x` ✅ |
| **8** | `2018-02-05` | `2018-02-06` | `2018-05-16` | `2.90` | `+4.31%` | **`+14.89%`** | `-10.52%` | `-29.68%` | **False Alarm** (`3x` beat `1x`, `-29.7%` DD) | `HOLD_3x` ✅ | `TRIM_1x` ❌ | `HOLD_3x` ✅ | `HOLD_3x` ✅ | `TRIM_1x` ❌ | `HOLD_3x` ✅ | `TRIM_1x` ❌ |
| **9** | `2018-10-16` | `2018-10-17` | `2019-01-28` | `1.34` | **`-6.79%`** | `-28.84%` | `-18.82%` | `-50.06%` | **Protective Trim** (`1x` beat `3x`) | `HOLD_3x` ❌ *(exited 8d late)* | `HOLD_3x` ❌ | `HOLD_3x` ❌ | `HOLD_3x` ❌ | `HOLD_3x` ❌ | `HOLD_3x` ❌ | `HOLD_3x` ❌ |
| **10** | `2020-02-24` | `2020-02-25` | `2020-05-13` | `1.71` | **`-2.64%`** | `-27.51%` | `-22.54%` | `-62.89%` | **Protective Trim** (`1x` beat `3x`) | `TRIM_1x` ✅ | `HOLD_3x` ❌ | `TRIM_1x` ✅ | `TRIM_1x` ✅ | `HOLD_3x` ❌ | `HOLD_3x` ❌ | `TRIM_1x` ✅ |
| **11** | `2024-04-30` | `2024-05-01` | `2024-05-20` | `1.41` | `+7.24%` | **`+21.82%`** | `-1.69%` | `-2.15%` | **False Alarm** (`3x` beat `1x`) | `HOLD_3x` ✅ | `HOLD_3x` ✅ | `HOLD_3x` ✅ | `HOLD_3x` ✅ | `HOLD_3x` ✅ | `HOLD_3x` ✅ | `HOLD_3x` ✅ |
| **12** | `2026-06-05` | `2026-06-08` | `2026-06-18` | `1.96` | `+7.63%` | **`+13.44%`** | `-3.13%` | `-9.18%` | **False Alarm** (`3x` beat `1x`) | `HOLD_3x` ✅ | `HOLD_3x` ✅ | `HOLD_3x` ✅ | `HOLD_3x` ✅ | `HOLD_3x` ✅ | `HOLD_3x` ✅ | `HOLD_3x` ✅ |

### Table T10B: Full-Sample Performance & Error Breakdown Across the 7 Signals (`2010-02-11 .. 2026-11-03`)

| Signal Variant (`SMA200`, Next-Day Open + `10bp/side`) | Full CAGR | Ex-2026 CAGR | `2010–2019` CAGR | `2020–2026` CAGR | Daily MaxDD | Daily Sharpe | **Rightly Blocked False Alarms** *(out of 7)* | **Wrongly Blocked Protective Trims** *(out of 5)* |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`0. Baseline (No Gate: always trim on Vol_Z > 1.2)`** | `54.89%` | `54.43%` | `48.94%` | `63.90%` | **`-44.54%`** | `1.259` | `0 / 7` | **`0 / 5`** |
| **`1. HYG / IEF < SMA200` (Combined Ratio)** | **`57.90%`** | **`57.19%`** | **`51.28%`** | **`67.99%`** | **`-44.54%`** | **`1.275`** | **`5 / 7`** | `2 / 5` *(2017-08 tie, **2018-10**)* |
| **`2. HYG / SHY < SMA200` (Pure Corporate Credit)** | `51.97%` | `50.97%` | `45.29%` | `62.15%` | `-58.08%` | `1.172` | `4 / 7` | **`5 / 5`** *(blocked 2010, 2011, 2018-10, 2020!)* |
| **`3. SHY / IEF < SMA200` (Pure Treasury Strength)** | `56.02%` | `55.21%` | `48.23%` | `67.99%` | **`-44.54%`** | `1.243` | `4 / 7` | `1 / 5` *(blocked **2018-10**)* |
| **`4. IEF > SMA200` (Standalone 7–10Y Treasury)** | `55.64%` | `54.82%` | `48.59%` | `66.43%` | **`-44.54%`** | `1.245` | `3 / 7` | `1 / 5` *(blocked **2018-10**)* |
| **`5. HYG < SMA200` (Standalone High-Yield Bond)** | `51.25%` | `50.21%` | `45.29%` | `60.28%` | `-58.08%` | `1.153` | `4 / 7` | **`5 / 5`** |
| **`6. BOTH (`HYG/SHY < SMA200 AND SHY/IEF < SMA200`)`** | `53.88%` | `52.97%` | `48.41%` | `62.15%` | `-50.71%` | `1.199` | `5 / 7` | **`5 / 5`** |
| **`7. EITHER (`HYG/SHY < SMA200 OR SHY/IEF < SMA200`)`** | `54.08%` | `53.18%` | `45.12%` | `67.99%` | `-58.08%` | `1.215` | `3 / 7` | `1 / 5` *(blocked **2018-10**)* |

### Corrections & Historical Mechanics Noted in T10
- **`2014-01-30` (20-day Treasury outperformance vs 200-day ratio trend)**: Over the 20 trading days leading into `2014-01-30`, Treasuries (`IEF +2.66%`) outperformed High-Yield (`HYG +0.43%`), so short-term risk aversion *was* present; `HYG/IEF` only stayed above `SMA200` (`+2.58%`) because of the large 2013 buffer. Notably, standalone `IEF > SMA200` (`Signal 4`) triggered a trim on `2014-01-30` (`IEF` had just crossed above its 200-day average by `+0.07%`), whereas `HYG/IEF` and `SHY/IEF` did not.
- **`2014-10-09` & `2015-01-08` (Confirmed flight-to-safety, yet trimming lost money)**: On both dates **every single one of the 7 signals (`1..7`)** confirmed flight-to-safety and trimmed `3x -> 1x`, yet `TQQQ` V-shaped (`+18.76%` vs `1x +5.08%` in Oct 2014; `+14.87%` vs `1x +5.60%` in Jan 2015). A real bond flight-to-safety signal does not guarantee an equity drop.
- **Why `SEP` + `HYG/IEF` failed on `2018-10-16` (the quarterly SEP blind spot)**: On **2018-09-26**, the FOMC hiked the target range to `2.00%–2.25%`, but its 2019 median dot remained at **`3.1%`** (unchanged from June 2018), and SEP updates only quarterly (`Mar/Jun/Sep/Dec`). Thus `SEP` remained `ON` during the October 2018 rate-driven selloff while `HYG/IEF` (`+2.27%` above `SMA200`), `HYG/SHY` (`+1.16%`), `SHY/IEF` (`+1.09%`), and standalone `IEF` (`-1.46%` below `SMA200`) **all** blocked the `2018-10-16` exit (delaying `HYG/IEF`'s de-levering by 8 trading days until `2018-10-29`).
- **Date Corrections**: S&P's US sovereign downgrade occurred after market close on **2011-08-05** (`2011-08-02` `Vol_Z > 1.2` and `HYG/IEF` `-4.23%` below `SMA200` preceded the downgrade by 3 days during the debt-ceiling growth scare); in 2020, `HYG/IEF` crossed below `SMA200` on **2020-02-21** (`-0.59%`, 3 calendar days before the `2020-02-24` `Vol_Z > 1.2` trigger).

## Findings that change the interpretation

1. **It is mainly a rates / flight-to-quality signal, not a credit signal.** `HYG/IEF = (HYG/SHY) × (SHY/IEF)`. On 2011-08-02 and 2020-02-24 credit still looked healthy (HYG/SHY above its average); a pure credit gate would have **blocked** those crash exits and dropped to −58%. The exits happened because Treasuries rallied (IEF up), which pushed HYG/IEF under its average. In practice the rule says: "don't de-lever while bond yields are rising."

2. **The tail risk is a rate-driven selloff while SEP is still ON.** That is exactly when the gate blocks the exit:
   - **2018-02 and 2018-10** (both rate-driven) were blocked.
   - 2018-02 happened to recover (+0.097 log).
   - 2018-10 cost −0.12 log. It only escaped 8 days later because that 3x leg was still in profit. With 50–140 day averages, the same episode hits the NSL lock and gives **−58.08% on 2018-12-24**.
   - The −44.54% drawdown is unchanged only because this one exit came just in time.

3. **The evidence is thin.** The gain comes from 7 decisions over 17 years, and two of them are 80% of it. It also went through heavy selection:
   - ~5 rule variants (Gemini picked A after seeing results),
   - 101+ moving-average lengths and 87 threshold pairs (external report),
   - several proxies.
   
   The 3% placebo p-value is before correcting for that search. My own T5 sweep is part of the same family. Neither the external report nor this audit is out-of-sample.

4. **Spec ambiguity.** The external report's 180–220 day range (57.38–58.29%) matches neither of Gemini's two encodings exactly (57.17–58.08% trim-only; 57.40–58.71% with gated re-entry). Also, entering from cash (`0x ->`) ignores the gate, so the rule is asymmetric. Freeze one written definition before any further test.

5. **Gemini's summary overstated it.** "Helps in every era / every decade" is wrong: 12 of 17 years are identical and 2018 is worse. "Fixed the −69.92% hole" is a separate NSL change that also fixes the baseline. It should be judged on its own, and it was tuned on one episode.

## Recommendation
- **Do not change the frozen TQQQ rule.** It doesn't matter for current positions either way: SEP = OFF means 100% SGOV.
- If kept as a candidate, log it in the forward ledger from now with the exact written rule. **Do not re-tune MA, proxy or thresholds.**
- Evaluate the "20-day non-ratchet NSL" separately on the **baseline**. It addresses a real mechanism (a brief round-trip should not raise the NSL floor to a local top), but rests on one episode.
- Before any adoption, stress-test a synthetic rate-shock selloff with SEP = ON (2018-10 shape, deeper). That is the scenario where this rule is structurally weakest.
