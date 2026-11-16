# Complete Independent Audit Response: Official Kenneth French FF3 (`True 36M >=720d`), Full-Month M&A Basket Simulation, and Same-Date Daily-Aligned `V4 vs TQQQ SEP` Comparison (2026-11-16)

> **Standalone Reproducible Scripts & Official Datasets (Committed on `main`)**:
> - Four Paper Experiments (`T1`, `T2`, `V1` Official Ken French `True 36M >=720d`, `V2`) & Head-to-Head Daily Comparison: [`run_four_paper_experiments.py`](../../run_four_paper_experiments.py)
> - Same-Date, Same-Cost (`10bp/side`), Same-Daily-Risk-Basis (`Open-Executed Daily NAV`) Head-to-Head Table: [`head_to_head_v4_vs_tqqq_daily_aligned.csv`](./head_to_head_v4_vs_tqqq_daily_aligned.csv)
> - Official Kenneth French Daily FF3 Factors (`2004-01-02 .. 2026-09-30`, `MKT_RF`, `SMB`, `HML`, `RF`): [`ken_french_ff3_daily.csv`](./ken_french_ff3_daily.csv)
> - Official Kenneth French Monthly FF3 Factors (`2004-01 .. 2026-09`, `MKT_RF`, `SMB`, `HML`, `RF`): [`ken_french_ff3_monthly.csv`](./ken_french_ff3_monthly.csv)
> - Regression Sample Length & Fallback Audit Table (`2009 Warmup` vs `2010–2026 True 36M`): [`exp_V1_ff3_sample_length_audit.csv`](./exp_V1_ff3_sample_length_audit.csv)
> - Full-Month M&A Post-Merger Holding Simulation (`VMED 2013-06`, `FOX/FOXA 2019-03` Held to `d1` Open): [`D_mna_full_month_simulation.csv`](../v4_from_scratch_audit_20261114/D_mna_full_month_simulation.csv)
> - Open-Executed Daily NAV Series (`Default V4` & `Cold-Start Walk-Forward V4`): [`E_daily_nav_v0_default.csv`](../v4_from_scratch_audit_20261114/E_daily_nav_v0_default.csv), [`E_daily_nav_wf_cold_2012.csv`](../v4_from_scratch_audit_20261114/E_daily_nav_wf_cold_2012.csv)

---

## 1. Apples-to-Apples Head-to-Head Comparison: `V4` vs `TQQQ SEP` (Exact Same Dates, Exact Same `10bp/side` Open Cost, Exact Same Daily NAV / Daily MaxDD / Daily Sharpe Basis)

Exported in [`head_to_head_v4_vs_tqqq_daily_aligned.csv`](./head_to_head_v4_vs_tqqq_daily_aligned.csv):

| Common Evaluation Window | Strategy (`Next-Day Open Execution + 10bp/side Cost`) | Start Date | End Date | Trading Days | **CAGR** | **Daily MaxDD** | **Monthly MaxDD** | **Daily Sharpe (ex-RF)** | **Monthly Sharpe (ex-RF)** | **Calmar (`CAGR / \|Daily MDD\|`)** |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1. Common Complete Months**<br>*(Excl. Partial Oct 2026)* | **Fixed `V4 Default` (`1.0x` Stocks/SGOV, No ER)** | `2010-03-01` | `2026-09-30` | `4,173` | **`61.89%`** | **`-37.32%`** | **`-23.69%`** | **`1.471`** | **`1.425`** | **`1.66`** |
| **1. Common Complete Months** | **Fixed `TQQQ SEP V1-Daily` (`1.2/0.3 + Open NSL`)** | `2010-03-01` | `2026-09-30` | `4,173` | `54.36%` | `-44.54%` | `-30.17%` | `1.213` | `1.221` | `1.22` |
| **1. Common Complete Months** | **`50% V4 Default + 50% TQQQ SEP` (Annual Rebal)** 🏆 | `2010-03-01` | `2026-09-30` | `4,173` | **`61.87%`** | **`-37.26%`** | `-23.90%` | **`1.509`** | **`1.507`** | **`1.66`** |
| **2. Common Full Window**<br>*(Incl. Oct 2026 Cutoff)* | **Fixed `V4 Default` (`1.0x` Stocks/SGOV, No ER)** | `2010-03-01` | `2026-10-29` | `4,194` | **`61.65%`** | **`-37.32%`** | **`-23.69%`** | **`1.467`** | **`1.423`** | **`1.65`** |
| **2. Common Full Window** | **Fixed `TQQQ SEP V1-Daily` (`1.2/0.3 + Open NSL`)** | `2010-03-01` | `2026-10-29` | `4,194` | `54.08%` | `-44.54%` | `-30.17%` | `1.210` | `1.217` | `1.21` |
| **2. Common Full Window** | **`50% V4 Default + 50% TQQQ SEP` (Annual Rebal)** 🏆 | `2010-03-01` | `2026-10-29` | `4,194` | **`61.61%`** | **`-37.26%`** | `-23.90%` | **`1.506`** | **`1.504`** | **`1.65`** |
| **3. Common Ex-2026 Window**<br>*(15.8 Years Pre-2026)* | **Fixed `V4 Default` (`1.0x` Stocks/SGOV, No ER)** | `2010-03-01` | `2025-12-31` | `3,986` | `51.39%` | **`-37.32%`** | **`-23.69%`** | **`1.342`** | **`1.385`** | **`1.38`** |
| **3. Common Ex-2026 Window** | **Fixed `TQQQ SEP V1-Daily` (`1.2/0.3 + Open NSL`)** | `2010-03-01` | `2025-12-31` | `3,986` | **`53.52%`** | `-44.54%` | `-30.17%` | `1.204` | `1.259` | `1.20` |
| **3. Common Ex-2026 Window** | **`50% V4 Default + 50% TQQQ SEP` (Annual Rebal)** 🏆 | `2010-03-01` | `2025-12-31` | `3,986` | **`55.07%`** | **`-37.26%`** | `-23.90%` | **`1.419`** | **`1.505`** | **`1.48`** |
| **4. Walk-Forward Complete Months**<br>*(2012 Cold-Cash Start, Daily NAV)* | **Walk-Forward `V4` (Cold-Cash Start, Daily NAV)** | `2012-01-03` | `2026-09-30` | `3,707` | `49.49%` | **`-35.58%`** | **`-28.55%`** | **`1.320`** | `1.253` | **`1.39`** |
| **4. Walk-Forward Complete Months** | **Walk-Forward `TQQQ SEP` (Cold-Cash Start, Daily NAV)** | `2012-01-03` | `2026-09-30` | `3,707` | **`56.78%`** | `-46.29%` | `-30.34%` | `1.256` | **`1.274`** | `1.23` |
| **5. Walk-Forward Full Window**<br>*(2012 Cold-Cash Start, Daily NAV)* | **Walk-Forward `V4` (Cold-Cash Start, Daily NAV)** | `2012-01-03` | `2026-10-29` | `3,728` | `49.50%` | **`-35.58%`** | **`-28.55%`** | **`1.322`** | `1.256` | **`1.39`** |
| **5. Walk-Forward Full Window** | **Walk-Forward `TQQQ SEP` (Cold-Cash Start, Daily NAV)** | `2012-01-03` | `2026-10-29` | `3,728` | **`56.44%`** | `-46.29%` | `-30.34%` | `1.253` | **`1.270`** | `1.22` |
| **6. Walk-Forward Ex-2026 Window**<br>*(2012 Cold-Cash Start, Daily NAV)* | **Walk-Forward `V4` (Cold-Cash Start, Daily NAV)** | `2012-01-03` | `2025-12-31` | `3,520` | `39.47%` | **`-35.58%`** | **`-28.55%`** | `1.166` | `1.214` | `1.11` |
| **6. Walk-Forward Ex-2026 Window** | **Walk-Forward `TQQQ SEP` (Cold-Cash Start, Daily NAV)** | `2012-01-03` | `2025-12-31` | `3,520` | **`55.94%`** | `-46.29%` | `-30.34%` | **`1.248`** | **`1.328`** | **`1.21`** |

---

## 2. Remediation of the Two Remaining Technical Items

### Item 1: Separating "True Full 36-Month Sample (`>= 720d / >= 34m` in `2010–2026`)" from "`>= 450d` No-Fallback"
- **Why `2009` Had `< 720` Days**: Raw stock price files in `research/sector_stock_momentum/data/` begin in `2006-12-01` (`wiki`) and `2007-01-03` (`yahoo` / `tiingo`). Therefore, in `2009` (`t = 2008-12-31 .. 2009-11-30`), the maximum available pre-formation history is `481` to `712` trading days (`22` to `33` months), whereas from **`2010-01 .. 2026-10` (`202` months)** the full 36-month window (`731` to `736` trading days) is available.
- **Explicit Separation in [`exp_V1_ff3_sample_length_audit.csv`](./exp_V1_ff3_sample_length_audit.csv) and [`exp_V1_residual_momentum.csv`](./exp_V1_residual_momentum.csv)**:
  - **`V1c-KF-True36M` (Strict `>= 720` Trading Days in `2010–2026`, Zero Fallback)**: Strictly excludes any stock with `< 720` trading days (`466` stock-months in `NDX_100` [`2.2%`] and `103` in `SPX_BestSec_NonIT` [`1.2%`] excluded as `NaN`), and evaluates directly on the **`2010–2026` (`202M`)** and **`2010–2025` (`192M` Ex-2026)** True 36-Month windows:

| `V1` Variant (`V4` Architecture Fixed: `Top-2 / Hold <= 5`, `SEP`, Open + `10bp/side`) | **`True36M` `2010–2026` CAGR (202M)** | **`True36M` `2010–2025` Ex-2026 CAGR (192M)** | Full `2009–2026` CAGR (214M) | Ex-2026 `2009–2025` CAGR (204M) | Full Sharpe (`09–25` Sharpe) | Monthly MaxDD |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **0. Frozen `V4` Baseline (`12-1 Total Return Sharpe`)** 🏆 | **`62.27%`** | **`52.40%`** | **`59.65%`** | **`50.38%`** | **`1.426` (`1.354`)** | **`-27.99%`** |
| **`V1c-KF-True36M`. Official Ken French FF3 True 36M Daily Beta (`Strict >= 720d` in `2010–2026`, Zero Fallback)** | **`52.14%`** | **`45.12%`** | `51.01%` | `44.39%` | `1.336` (`1.237`) | `-37.43%` |
| **`V1c-KF-22to36M`. Official Ken French FF3 Daily Beta (`>= 450d`, Zero Fallback)** | `57.54%` | `50.54%` | `56.06%` | `49.46%` | `1.383` (`1.289`) | `-37.43%` |
| **`V1c-KF-Monthly-Blitz`. Official Ken French FF3 True 36M Monthly OLS (`Blitz 2011 Eq.2`, `>= 34m` in `2010+`)** | `29.89%` | `22.24%` | `30.67%` | `23.45%` | `0.976` (`0.868`) | `-35.22%` |
| **`V1c-KF-Monthly-Alpha`. Official Ken French FF3 True 36M Monthly OLS (`Alpha+Residual`, `>= 34m` in `2010+`)** | `46.51%` | `41.71%` | `47.53%` | `43.02%` | `1.289` (`1.287`) | `-27.28%` |
| **`V1e-KF-True36M`. `50/50` Blend (`Total Sharpe` + Official Ken French `True 36M >=720d` Residual Sharpe)** | **`57.78%`** | **`50.79%`** | `55.68%` | `49.08%` | `1.438` (`1.346`) | `-27.99%` |
| **`V1e-KF-22to36M`. `50/50` Blend (`Total Sharpe` + Official Ken French `>=450d` Residual Sharpe)** | `58.96%` | `51.97%` | `56.78%` | `50.18%` | `1.466` (`1.376`) | `-27.99%` |

---

### Item 2: Full-Month M&A Post-Merger Holding Simulation to `d1` Open (`D_mna_full_month_simulation.csv`) & Exact Single-Vendor Count (`105 / 125`)
- **Full-Month M&A Post-Merger Simulation ([`audit_v4_from_scratch.py`](../../audit_v4_from_scratch.py) & [`D_mna_full_month_simulation.csv`](../v4_from_scratch_audit_20261114/D_mna_full_month_simulation.csv))**:
  - Instead of stopping at the last pre-merger close (`mna_close`), we simulated holding the exact SEC Form 8-K merger consideration (`cash` in `BIL` + successor shares `LBTYA`, `new FOX`, `new FOXA`, `DIS`) all the way from `mna_close` to the next monthly rebalance open `d1_open`:

| Holding Month | Ticker | Entry `d0_open` | Merger `mna_close` | Exit `d1_open` | Panel Pre-Merger Close Return | **Sim 1: Cash Proceeds in `BIL` to `d1_open`** | **Sim 2: Cash + Spin-Off (`new FOX/FOXA`, `LBTYA`) Held to `d1_open`** | **Sim 3: Full Prorated Merger Basket (`Cash + DIS + new FOX/FOXA / LBTYA`) Held to `d1_open`** |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `2013-06` | `VMED` | `2013-06-03` | `2013-06-07` | `2013-07-01` | `+2.7190%` | `+2.6966%` | **`+0.9767%`** | **`+0.9767%`** |
| `2019-03` | `FOX` | `2019-03-01` | `2019-03-19` | `2019-04-01` | `-1.4893%` | `-1.4079%` | **`-3.3972%`** | **`-2.8961%`** |
| `2019-03` | `FOXA` | `2019-03-01` | `2019-03-19` | `2019-04-01` | `-1.8566%` | `-1.7756%` | **`-3.7578%`** | **`-3.2595%`** |

  - **Portfolio-Level Impact on Default `V4 (No ER)`**: Replacing all 3 `delist_last_close` positions with **Sim 3 (Full Prorated Merger Basket Held to `d1_open`)** yields a `214M` CAGR of **`59.45%`** (`59.4475%` vs `59.6538%` baseline, diff = **`-0.21pp/yr`**, Sharpe **`1.421`**, Monthly MaxDD **`-27.99%`**) and a Complete `213M` CAGR of **`59.66%`** (`59.6614%` vs `59.8689%`).
- **Correction of Single-Vendor Count in `D_cross_vendor_check.csv`**:
  - Confirmed and synchronized with [`audit_log.txt`](../v4_from_scratch_audit_20261114/audit_log.txt) line 54: out of `422` invested stock-months, `288` have $\ge 2$ Open-to-Open vendors (`max_absdiff_oo > 1%: 0`), `9` additional positions (`297` total) have a 2nd Close-to-Close vendor (`max_absdiff_cc = 0.0000%`), and of the remaining **`125`** single-vendor (`yahoo`) positions, **`105`** (`84.0%`, or `111 / 134` of single-open-vendor positions) occur in **`2018-04 .. 2026-10`** after the Quandl WIKI dataset ended in `2018-03` (the remaining `20` pre-2018 positions are `PCLN`, `VMED`, `ESRX`, `GILD`, `ILMN`, `SBAC`, `EXPE`, `SNDK` in months where only 1 local vendor file is stored).
