# Clean-Room Challenger Audit of 6 New Academic Papers (`P1` FIP, `P2` 52W-High, `P3` Volume, `P4` PIT SUE/EAR, `P5` Fed EBP, `P6` VRP) (2026-11-16)

> **Reproducible Script & CSV Outputs (Committed on `main`)**:
> - Standalone Script: [`run_six_new_paper_challengers.py`](../../run_six_new_paper_challengers.py)
> - `V4` Challengers Summary (`P1`–`P4`, with Open-Executed Daily MaxDD & Outlier-Removal Tests): [`v4_challengers_p1_p2_p3_p4_summary.csv`](./v4_challengers_p1_p2_p3_p4_summary.csv)
> - `TQQQ SEP` Challengers Summary (`P5` Fed EBP & `P6` VRP): [`tqqq_challengers_p5_ebp_p6_vrp_summary.csv`](./tqqq_challengers_p5_ebp_p6_vrp_summary.csv)
> - Official Federal Reserve EBP Data (`1973-01 .. 2026-10`): [`fed_official_ebp.csv`](../four_paper_experiments_20261116/fed_official_ebp.csv)

---

## 1. Executive Verdict: Do Any of the 6 New Paper Challengers Beat the Frozen Baselines?

**No — both Frozen `V4` (`12-1 Sharpe, Top-2 / Hold <= 5`) and Frozen `V1-Daily TQQQ SEP` (`1.2/0.3 + Open NSL`) remain unbeaten on risk-adjusted return (`Sharpe`) and outlier-removed robustness (`Drop-Best-10M CAGR`).**

| Priority & Paper | Target Strategy | Best Challenger Variant | Full CAGR (vs Baseline) | Ex-2026 CAGR (vs Baseline) | **Sharpe** (vs Baseline) | **Daily MaxDD** (vs Baseline) | **Drop-Best-10M CAGR** (vs Baseline) | Audit Verdict |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **0. Frozen `V4` Baseline** | `V4` | `12-1 Sharpe (Top-2 / Hold <= 5)` 🏆 | **`59.65%`** | **`50.38%`** | **`1.426`** | **`-37.32%`** | **`37.55%`** | **KEEP FROZEN** |
| **P1. Da, Gurun & Warachka (2014, RFS)**<br>*Frog-in-the-Pan (`FIP`)* | `V4` | `P1c. Smooth Sharpe (Ex-Top5 Jumps)`<br>`P1a. FIP Tie-Break in Sharpe Top-5` | `46.41%`<br>`45.41%` | `38.01%`<br>`38.69%` | `1.253`<br>`1.247` | `-38.55%`<br>`-38.85%` | `26.97%`<br>`27.67%` | ❌ **Falsified** (`-13pp` CAGR, `-0.17` Sharpe) |
| **P2. George & Hwang (2004, JF)**<br>*52-Week High Proximity (`P_t / High_252`)* | `V4` | `P2a. 52W-High Tie-Break in Sharpe Top-5`<br>`P2b. 50/50 Rank Blend` | `35.47%`<br>`13.06%` | `27.27%`<br>`8.43%` | `1.020`<br>`0.531` | `-37.03%`<br>`-36.83%` | `17.87%`<br>`1.80%` | ❌ **Falsified** (`-24pp` to `-46pp` CAGR) |
| **P3. Lee & Swaminathan (2000, JF)**<br>*Price Momentum & Trading Volume* | `V4` | `P3b. High Volume Ratio in Sharpe Top-5`<br>`P3a. Low Volume Ratio in Sharpe Top-5` | `58.79%`<br>`32.34%` | `48.73%`<br>`29.09%` | `1.373`<br>`1.090` | `-37.32%`<br>`-31.76%` | `36.33%`<br>`17.30%` | ❌ **Falsified** (High-Vol close `-0.9pp`, Low-Vol `-27pp`) |
| **P4. Chan, Jegadeesh & Lakonishok (1996, JF)**<br>*PIT Quarterly `SUE` & 3-Day Filing `EAR`* | `V4` | `P4a. PIT SUE Tie-Break in Sharpe Top-5`<br>`P4b. 3-Day EAR Tie-Break in Sharpe Top-5`<br>`P4c. 50/50 SUE Rank Blend` | `65.23%`<br>`49.38%`<br>`49.41%` | `57.38%`<br>`39.63%`<br>`41.77%` | `1.263`<br>`1.260`<br>`1.271` | `-37.68%`<br>`-31.39%`<br>`-40.40%` | `37.03%`<br>`29.75%`<br>`30.01%` | ⚠️ **Reject** (`P4a` Sharpe drops `1.426 -> 1.263`, vol jumps `36.7% -> 46.2%`, driven by 1 `MRNA` outlier month) |
| **0. Frozen `V1-Daily TQQQ` Baseline** | `TQQQ` | `SEP + Vol_Z 1.2/0.3 + Open NSL` 🏆 | **`54.89%`** | **`54.43%`** | **`1.259`** | `-44.54%` | — | **KEEP FROZEN** |
| **P5. Gilchrist & Zakrajšek (2012, AER)**<br>*Official Fed Excess Bond Premium (`EBP`)* | `TQQQ` | `P5a. De-lever 3x->1x if Lagged EBP > 0.50%`<br>`P5b. Cash if Lagged EBP > 0.75%` | `51.82%`<br>`49.87%` | `51.21%`<br>`49.16%` | `1.246`<br>`1.186` | **`-37.24%`**<br>`-57.08%` | — | ⚠️ **Reject** (`P5a` cuts Daily MaxDD `-7.3pp` but costs `-3.1pp/yr` CAGR & EBP lacks pre-2016 ALFRED vintage) |
| **P6. Bollerslev, Tauchen & Zhou (2009, RFS)**<br>*Variance Risk Premium (`VRP = IV^2 - RV^2`)* | `TQQQ` | `P6a. De-lever when VRP < -0.015`<br>`P6b. Faster Re-entry when VRP_Z > +1.0` | `44.09%`<br>`54.89%` | `43.90%`<br>`54.43%` | `1.160`<br>`1.259` | `-44.66%`<br>`-44.54%` | — | ❌ **Falsified** (`P6a` whipsaws `61` times; `P6b` identical to baseline) |

---

## 2. Full Results Table: Part 1 — `V4` Challengers (`P1` FIP, `P2` 52W-High, `P3` Volume, `P4` PIT SUE/EAR)

Exported in [`v4_challengers_p1_p2_p3_p4_summary.csv`](./v4_challengers_p1_p2_p3_p4_summary.csv) (all variants use Next-Day `adjOpen` execution + `10bp/side` cost + Open-Executed Daily NAV for `Daily_MaxDD_%`):

| Challenger Variant (`NDX_100` in `SEP=ON`, `#1 Non-IT BestSec` in `SEP=OFF`, `Top-2 / Hold <= 5`) | Full `214M` CAGR | Complete `213M` CAGR | **Ex-2026 (`09–25`) CAGR** | **Pre-2021 (`09–20`) CAGR** | **`214M` Sharpe** | **`Ex-2026` Sharpe** | **Daily MaxDD** | Monthly MaxDD | **Drop-Best-5M CAGR** | **Drop-Best-10M CAGR** | Two-Way Turnover | Trade Win Rate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0. Frozen `V4` Baseline (`12-1 Sharpe`, `Top-2 / Hold<=5`)** 🏆 | **`59.65%`** | **`59.87%`** | **`50.38%`** | **`50.55%`** | **`1.426`** | **`1.354`** | **`-37.32%`** | **`-27.99%`** | **`46.43%`** | **`37.55%`** | `7.00x` | **`70.16%`** |
| **`P1a-FIP-Top5Tie`**. Pick Top-2 Most Continuous (`%pos-%neg`) in `Sharpe Top-5` | `45.41%` | `45.40%` | `38.69%` | `42.31%` | `1.247` | `1.158` | `-38.85%` | `-34.99%` | `34.70%` | `27.67%` | `7.85x` | `67.14%` |
| **`P1b-FIP-Blend`**. `50/50` Rank Blend (`12-1 Sharpe + Daily FIP Continuity`) | `28.76%` | `28.68%` | `21.58%` | `20.87%` | `0.956` | `0.806` | `-46.31%` | `-38.08%` | `19.92%` | `14.27%` | `7.08x` | `61.90%` |
| **`P1c-SmoothSharpe`**. `12-1 Sharpe` Excluding Top-5 Largest Daily Jump Spikes | `46.41%` | `46.40%` | `38.01%` | `38.53%` | `1.253` | `1.183` | `-38.55%` | `-29.32%` | `34.21%` | `26.97%` | `7.25x` | `66.67%` |
| **`P2a-52WHigh-Top5Tie`**. Pick Top-2 Closest to 52W High (`P_t/High_252`) in `Sharpe Top-5` | `35.47%` | `35.54%` | `27.27%` | `25.51%` | `1.020` | `0.942` | `-37.03%` | `-28.48%` | `24.35%` | `17.87%` | `7.39x` | `65.91%` |
| **`P2b-52WHigh-Blend`**. `50/50` Rank Blend (`12-1 Sharpe + 52-Week High Proximity`) | `13.06%` | `13.03%` | `8.43%` | `8.74%` | `0.531` | `0.399` | `-36.83%` | `-33.05%` | `5.93%` | `1.80%` | `14.19x` | `53.44%` |
| **`P2c-52WHigh-Pure`**. Pure 52-Week High Proximity Ranking (George & Hwang 2004) | `7.47%` | `7.42%` | `5.82%` | `6.91%` | `0.388` | `0.321` | `-57.45%` | `-55.06%` | `3.45%` | `0.19%` | `18.54x` | `55.65%` |
| **`P3a-VolLow-Top5Tie`**. Pick Top-2 Lowest `3M/12M` Volume Ratio in `Sharpe Top-5` | `32.34%` | `32.03%` | `29.09%` | `31.75%` | `1.090` | `1.033` | `-31.76%` | `-23.83%` | `23.59%` | `17.30%` | `9.86x` | `62.09%` |
| **`P3b-VolHigh-Top5Tie`**. Pick Top-2 Highest `3M/12M` Volume Ratio in `Sharpe Top-5` | `58.79%` | `59.00%` | `48.73%` | `48.78%` | `1.373` | `1.327` | `-37.32%` | `-27.99%` | `44.69%` | `36.33%` | `7.44x` | `61.36%` |
| **`P3c-VolLow-Blend`**. `50/50` Rank Blend (`12-1 Sharpe + Low 3M/12M Volume Ratio`) | `25.09%` | `24.80%` | `22.63%` | `24.05%` | `0.780` | `0.731` | `-37.99%` | `-31.10%` | `14.26%` | `8.15%` | `10.62x` | `58.76%` |
| **`P3d-VolHigh-Blend`**. `50/50` Rank Blend (`12-1 Sharpe + High 3M/12M Volume Ratio`) | `42.60%` | `42.72%` | `35.87%` | `33.75%` | `1.079` | `1.015` | `-59.60%` | `-58.56%` | `30.70%` | `22.56%` | `7.59x` | `62.41%` |
| **`P4a-SUE-Top5Tie`**. Pick Top-2 Highest PIT Quarterly `SUE` in `Sharpe Top-5` | `65.23%` | `65.47%` | `57.38%` | `56.63%` | `1.263` | `1.221` | `-37.68%` | `-27.99%` | `46.46%` | `37.03%` | `7.48x` | `69.92%` |
| **`P4b-EAR3d-Top5Tie`**. Pick Top-2 Highest 3-Day Filing `EAR` in `Sharpe Top-5` | `49.38%` | `49.39%` | `39.63%` | `43.57%` | `1.260` | `1.210` | `-31.39%` | `-24.46%` | `36.91%` | `29.75%` | `7.59x` | `64.93%` |
| **`P4c-SUE-Blend`**. `50/50` Rank Blend (`12-1 Sharpe + PIT Quarterly SUE`) | `49.41%` | `49.56%` | `41.77%` | `39.69%` | `1.271` | `1.175` | `-40.40%` | `-36.83%` | `38.06%` | `30.01%` | `6.42x` | `65.49%` |
| **`P4d-EAR3d-Blend`**. `50/50` Rank Blend (`12-1 Sharpe + PIT 3-Day Filing EAR`) | `25.68%` | `25.61%` | `21.50%` | `14.67%` | `0.890` | `0.804` | `-45.65%` | `-40.64%` | `17.95%` | `12.29%` | `8.98x` | `60.12%` |

---

## 3. Structural Mechanism Diagnosis: Why Did `P1`–`P4` Fail to Beat `V4`'s `12-1 Sharpe`?

1. **Why Frog-in-the-Pan (`P1`) Hurts `V4` (`45.41%` / `46.41%` vs `59.65%`)**:
   - `V4` **already divides `12-1` return by annualized daily volatility (`12-1 Sharpe = mom / vol`)**, which naturally penalizes erratic biotechs and meme stocks.
   - Going further by maximizing `%pos - %neg` (`P1a`/`P1b`) or removing the top 5 single-day jump spikes (`P1c`) **strips out legitimate earnings-beat gap-ups** (`NVDA`, `TSLA`, `NFLX`, `AVGO`), rotating out of secular growth leaders into slow-grinding defensive stocks (`ORLY`, `PAYX`, `COST`).
2. **Why 52-Week High Proximity (`P2`) Collapses in `V4` (`35.47%` / `13.06%` / `7.47%` vs `59.65%`)**:
   - Two structural defects in a concentrated Top-2 portfolio:
     1. **Low-Volatility Compression**: A defensive stock up `+8%` in a year with `9%` volatility sits at `99.5%` of its 52-week high (`P_t / High_252 = 0.995`), whereas a secular leader up `+150%` over `12-1M` that consolidates `-5%` stays at `0.95`.
     2. **Re-introducing 1-Month Reversal (Jegadeesh 1990)**: `12-1` momentum explicitly skips month $t$ (`t-1 -> t`) to avoid 1-month short-term overreaction reversal. Ranking by $P_t / \text{High}_{252}(t)$ at month-end $t$ forces the strategy to buy stocks that just spiked in month $t$, suffering immediate next-month mean reversion.
3. **Why Lee & Swaminathan (2000) Low-Volume (`P3a`: `32.34%`) Fails While High-Volume (`P3b`: `58.79%`) Almost Ties `V4`**:
   - Lee & Swaminathan (2000) studied 3–5 year long-horizon reversals across small/mid-cap NYSE stocks. In 1-month holding periods on Nasdaq-100 mega-caps, low-volume winners (`P3a`) are stalled/illiquid names (`32.34%`), while high-volume breakout winners (`P3b`, `58.79%`, Sharpe `1.373`) confirm institutional accumulation—yet still trail pure `12-1 Sharpe` (`59.65%`, Sharpe `1.426`).
4. **Why `P4a-SUE-Top5Tie` (`65.23%` CAGR, Sharpe `1.263`) Is Rejected as an Outlier Artifact**:
   - Although `P4a` has a higher raw CAGR (`65.23%` vs `59.65%`), **its annualized volatility jumps by `+9.58%` (`46.24%` vs `36.66%`), causing its Sharpe ratio to drop significantly from `1.426` to `1.263`** (`Ex-2026` Sharpe drops from `1.354` to `1.221`).
   - Decomposition shows that `P4a`'s entire excess CAGR comes from **a single outlier month (`2020-11`, where `P4a` held `TSLA | MRNA` `+106.2%` vs `V4`'s `TSLA | DOCU` `+30.2%`)** and incomplete SEC XBRL coverage (`24.4%` of NDX stock-months lack standardized XBRL `sue_pit` in `2009–2011`). Once the best 10 months are dropped (`DropBest10M_CAGR_%`), `P4a` (`37.03%`) trails `V4 Baseline` (`37.55%`), and both the `50/50 SUE Blend` (`P4c`, `49.41%`) and `3-Day Filing EAR` (`P4b`, `49.38%`) underperform `V4` by `-10pp/yr`.
      
---

## 4. Full Results Table: Part 2 — `TQQQ SEP` Challengers (`P5` Fed EBP & `P6` VRP)

Exported in [`tqqq_challengers_p5_ebp_p6_vrp_summary.csv`](./tqqq_challengers_p5_ebp_p6_vrp_summary.csv):

| `TQQQ` Challenger Variant (`2010-02-11 .. 2026-11-03`, Next-Day `adjOpen` + `10bp/side`) | Full `2010–2026` CAGR | Ex-2026 (`2010–2025`) CAGR | Daily Sharpe (`rf=0`) | **Daily MaxDD** | Monthly MaxDD | Switches |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **0. Frozen `V1-Daily` Baseline (`SEP + Vol_Z 1.2/0.3 + Open NSL`)** 🏆 | **`54.89%`** | **`54.43%`** | **`1.259`** | `-44.54%` | `-30.17%` | `33` |
| **`P5a-EBP`**. De-lever `3x->1x` (`NSL`) when Lagged Fed `EBP > +0.50%` or `Vol_Z > 1.2` | `51.82%` | `51.21%` | `1.246` | **`-37.24%`** | **`-28.36%`** | `35` |
| **`P5b-EBP`**. Exit to `0x Cash` when Lagged Fed `EBP > +0.75%` (Severe Credit Freeze) | `49.87%` | `49.16%` | `1.186` | `-57.08%` | `-49.75%` | `36` |
| **`P6a-VRP`**. De-lever `3x->1x` (`NSL`) when Bollerslev `VRP = IV^2 - RV^2 < -0.015` | `44.09%` | `43.90%` | `1.160` | `-44.66%` | `-37.42%` | `61` |
| **`P6b-VRP`**. Faster Re-entry `1x->3x` when `VRP_Z > +1.0` (High Implied Fear Premium) | `54.89%` | `54.43%` | `1.259` | `-44.54%` | `-30.17%` | `33` |
