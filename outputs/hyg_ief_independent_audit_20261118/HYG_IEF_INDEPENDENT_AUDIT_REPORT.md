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
