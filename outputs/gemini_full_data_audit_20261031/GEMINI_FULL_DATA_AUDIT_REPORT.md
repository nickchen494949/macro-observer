# 全库回测数据独立审计与 100 张分层随机抽查报告（2026-10-31）

## 一句话总结论（人话版）

**不能给整座仓库的所有回测数据盖“100% 全部无瑕疵通过”的章；但核心大盘价格算术、SEC 财报披露时点、13F 机构持仓库和 347 份策略月度账本的复算全部 100% 对得上（误差 $\le 1.11 \times 10^{-16}$）。**

具体来说，全库 7 大回测数据域、**2,096 万条日线行情**、**20.45 万条季度财报 / 685.75 万条财报明细**、**91 条 FRED 宏观序列（30.93 万条观测）**、**1.20 亿行 SEC 13F 原始持仓**、以及 **347 份策略月度账本** 经全量扫描 + 固定随机种子（`seed=20261031`）**100 张分层随机核查卡**逐笔核对外部主数据源后，结论清清楚楚分成三类：

1. **算术与外部主源硬核对过关的部分（可放心引用算术真值）**：
   - **标普 500 核心股价与开盘价**：与贝莱德官方 `IVV` 逐月持仓未复权原价核对 **65,811 个股票月**，**99.6809%（65,601 个）误差 $\le 10\text{bp}$（0.10%）**，**99.7007% 误差 $\le 1\%$**；与 Nasdaq Data Link `WIKI` 核对 **54,365 个重叠股票月**，**98.3041% 月收益率一致（$\le 1\%$）**。`raw_open` 共 2,981,563 条日线中，`adj_open / open` 与 `adjclose / close` 最大偏差仅 **$1.11 \times 10^{-16}$**。
   - **全部 347 份月度策略账本**：从最底层原始价格/开盘价 JSON 逐月独立重算 10 条代表性主策略（含收盘成交与次日开盘成交），毛收益最大绝对误差 **$\le 1.11 \times 10^{-16}$**（机器浮点极限）。
   - **SEC EDGAR PIT 财报披露时点与拆股换算**：三套财报面板共 **204,523 行季报**、`pit_long` **6,857,549 行**，`available_date != filed + 1天` 为 **0**，`period_end > filed + 16天` 为 **0**，TTM 跨字段提前放行（如旧版 AMD 2017-06-30 利润率偷看未来）回归检查为 **`null`（0 泄漏）**，187,986 行 EPS 披露后拆股换算误差为 **0**。
   - **Smart Money SEC Form 13F 机构持仓全量库（`13f_full_4409f14.db`）**：**397,833 份申报 / 120,182,194 行持仓**，`acceptance_datetime` 覆盖率 **100.0%**，13 项内置 QA（`CH-1`..`CH-13`）全部 `PASS`，随机抽查 10 个年份的 SEC 官方原始 `.zip` 压缩包（`SUBMISSION.tsv` + `INFOTABLE.tsv`）金额（含 2023-01-03 前 $\times 1000$、后 $\times 1$ 规则）与股数 **10/10 分毫不差**。
   - **100 张随机核查卡（`seed=20261031`）**：**0 张算术错误（`FAIL_MATH = 0`）**；**89 张**直接与外部官方/独立主源核对一致（`PASS_PRIMARY_VERIFIED`），**7 张**无免费第二源覆盖但内部算术精确（`PASS_INTERNAL_SINGLE_VENDOR`），其余 **4 张**精准命中下述真实数据缺陷/宏观修订警告。

2. **被抓出并量化的真实数据缺陷（不能装作没看见）**：
   - **原版（`78a2d0d`）估值价格用错复权口径（已在 Codex v2 修复）**：用含未来分红折算的 `adjclose` 乘以历史当期股本/EPS，导致标普 500 特征表 **59,805 个股票月中有 49.43% 市值/估值失真 $>10\%$**（2010–2015 年中位数低估 **25.60%**，特殊分红股 `KDP` 低估达 **89.48%**）。加上训练验证窗口跨月开盘泄漏与费用计提修正后，`ML2 C-lgbm Top1` 年化从原版 **46.12% 降至 33.39%**（落后同窗口纯动量 Top1 的 **41.97%**），`C-lgbm Top3` 从 **36.69% 降至 17.86%**（落后纯动量 Top3 的 **27.33%**）。
   - **中小盘（`winners_holdout`）股票池严重非 PIT，且混入大宗商品/加密货币/外汇信托与代码借壳映射**：
     - 候选池直接取自**今天**的 SEC `company_tickers_exchange.json`（3,830 只），其中 **354 只**是纯非经营性商品/加密信托或空白支票 SPAC（`SIC 6221 / 6770 / 6799`），**1,751 只**在 `2018-03`（WIKI 停更）前根本没有任何 SEC XBRL `10-K/10-Q`。
     - 更直接的证据：中小盘纯动量 Top1 基准账本（`monthly_BENCH_pure_momentum_top_1_base`）在 **2017-10、2017-11、2017-12、2018-02 连续 4 个月把当时还在 OTC 交易的比特币信托 `GBTC`（直到 2020-05-08 才首次交 10-Q）当成“全市场第 1 名中小盘股票”买入**；等权基准与持仓池中出现 **3,528 笔** `AGQ`（2 倍做多白银）、`USO`（原油）、`UNG`（天然气）、`SLV`、`IAU` 等商品信托持仓；且旧公司退市后代码被新公司/SPAC 接管（如 2013 年老 `SPWR` 被映射到 2021 年 SPAC `CIK 1838987`，2012 年老苏富比 `BID` 被映射到 2026 年新注册 `CIK 2094919`，老家具股 `ETH` 被映射到 2024 年灰度以太坊信托 `CIK 2020455`）。
     - 此外，`raw_smallcap` 存在 **6,641 根非正 `adjclose` K 线**（极端合股股 `CBIO` 最低 `-2788.5`、`VATE` `-37.71`、`NFE` `-23.59`）；原版 `STRICT` 过滤因 `< r.end` 边界 bug 漏掉了 **1,160 / 2,835 条**单日暴涨暴跌反转异常；`price_corrections.csv` 的 64 条修补中有 **45 条**直接按跳变比例缩放而非精确拆股比。
   - **跨策略研究中的两处硬口径错配**：
     - **`lseg_backtest_results_v3.csv`（`source=82221/82222`）被数学证明 100% 是标普 500（`^GSPC`），绝非纳指 100 / QQQ**：389 个重叠周收盘价与 `^GSPC` **100.0% 吻合在 1bp 以内**（最大相对误差 $2.23 \times 10^{-8}$，如 `2016-10-14` `price=2132.98` = `^GSPC 2132.98`，而当天 `QQQ=117.14`）。用标普 500 预期 EPS 去交易 QQQ 属于跨指数混搭。
     - **行业 EPS 与 FOMC SEP 的历史时点缺陷**：`data/sector_eps/sector_eps_quarterly.csv` 中 **689 / 700 行（98.43%）** 为 Yardeni 图表曲线像素描点（`curve_approx`，非 PIT）；Wayback 找回的 145 份 S&P DJI 官方 `.xlsx`（150,190 个单元格抽查 100% 精确）目前仅能完整覆盖 **94 / 141 个月**（缺 47 个月）。`data/sep_revisions.json` 的 74 期中有 **30 期早于 2015-06**，而美联储官方 PDF 在 2015 年之前根本没有发布 `Median`（中位数）表。
   - **宏观 FRED 历史修订（非 PIT）与 `data/yahoo` 无分红问题**：
     - 91 个 FRED JSON 中，市场利率/利差（`DGS10`、`DFF`、`BAMLH0A0HYM2`）无修订问题；但 **62 个非日频宏观序列**在实时历史上经历过大幅修订（通过官方 ALFRED 实时库核实：`2020-Q2 GDP` 初值 `19,408.76` vs 现值 `19,958.29`，上修 `+549.5 亿美元`；`2021-06 PAYEMS` 非农上修 `+6.1 万人`；`PCEPILFE` 基期重算从 `120.72` 变为 `111.82`）。旧版 `backtest/audit_report.md` 把全部 89 条 FRED 序列统标为 `"Daily | 1 day lag | Point-in-time: Yes"` 与事实不符。
     - 根目录 `data/yahoo/*.json`（供宏观状态回测 `backtest/` 使用）存的是不含分红的价格序列，与 `research/sector_rotation/adj_prices/*.csv` 含分红总回报相比，每年少算分红收益：`SPY` **1.80%/年**、`QQQ` **0.68%/年**、`XLK` **1.14%/年**、`XLE` **2.66%/年**。

3. **标普 500 成分股历史残余缺口及对核心策略的实际影响**：
   - 与贝莱德官方 `IVV` 135 期月度持仓逐一比对确认的 **59 处成分股归属/收盘后生效时点偏差**（涉及 `ACE`、`CPRI/KORS`、`CCEP/CCE`、`TE` 等 13 个代码），对不同策略的实际命中次数为：
     - **全市场纯动量 Top1（`PureMom_Top1`）**：**0 次命中（完全不受影响）**
     - **机器学习 `ML2 C-lgbm Top3`**：**0 次命中（完全不受影响）**
     - **行业→个股动量 `SPEC`**：**1 次命中**（`2016-06-30` 选了 `TE`，官方收盘后剔除已生效，当月实际现金收购价退出收益 `-0.33%`）
     - **纯动量 Top10**：**3 次命中**（`2016-06-30` `TE`，以及 `2018-02-28` / `2018-05-31` `CPRI` 与 `KORS` 重复计入）
   - 免费数据源下仍客观存在的边界：2017 上半年缺 6 期独立 `IVV` 快照、`gap_ledger.csv` 记录的 89 段历史缺失（659 个股票月）、55 个股票代码的历史 GICS 行业与 `IVV` 持仓行业存在差异、以及 2 笔换股并购退出（`ANDV`、`SCG`）忽略了收购方当月分红。

---

## 二、7 大数据域全量审计总表

| 数据域 | 审计覆盖规模（100% 全量扫描） | 外部主数据源 / 独立校验基准 | 结论等级 | 核心量化证据 |
|---|---|---|---|---|
| **1. 标普 500 & 纳指 100 股票日线价格/开盘价** | 7 个核心库共 `2,509` 个 JSON、`1,017.9 万`根日线 + `WIKI` `3,199` 股 | 贝莱德官方 `IVV` 持仓 (`65,811` 股票月) + Nasdaq `WIKI` (`54,365` 股票月) | **核心价格通过；成分股池有小幅已知残差** | `IVV` 原价 `99.6809% <= 10bp`；`raw_open` 复权因子最大误差 `1.11e-16`；`PureMom_Top1` 与 `ML2 Top3` 0 次命中 59 处成分股缺陷（`SPEC` 命中 1 次 `TE`） |
| **2. 中小盘 (`winners_holdout`) 价格与候选池** | `raw_smallcap` `3,830` 个 JSON（`1,078.0 万`根日线）+ 48 份账本 | Nasdaq `WIKI` + SEC 官方 71 个季度 FSDS `sub_*.parquet` (`2009Q1–2026Q3`) | **未通过 PIT 审计（结构性污染）** | `6,641` 根非正 `adjclose`；`354` 只商品/加密信托与 SPAC（`GBTC` 4 次入选纯动量 Top1；`AGQ/USO/UNG/SLV` 等 `3,528` 笔持仓）；代码借壳错配（`SPWR/BID/ETH`）；`STRICT` 漏拦 `1,160` 条单日尖峰 |
| **3. SEC EDGAR PIT 财报与估值特征** | 3 套季报面板 `204,523` 行 + `pit_long` `6,857,549` 行 + `8-K` `61,645` 行 | SEC 官方 `data.sec.gov` 申报档案 + 71 期 SEC FSDS | **财报时点 100% 通过；原版估值价有分红泄漏（Codex v2 已修）** | `available_date != filed+1d` = `0`；EPS 拆股误差 = `0`；AMD `2017-06-30` 泄漏回归 = `null`；原版用 `adjclose` 算市值致 `49.43%` 样本失真 `>10%` |
| **4. FRED 宏观序列 & 轮动 ETF 行情** | `91` 个 FRED JSON（`309,288` 条观测）+ `66` 个 `data/yahoo` + `13` 个 `adj_prices` | 圣路易斯联储官方 `api.stlouisfed.org` 实时 & ALFRED 初值 API | **利率精确；宏观经济存在历史修订；`data/yahoo` 不含分红** | 利率 `0` 修订；`2020Q2 GDP` 修订 `+549.5B`、`2021-06 PAYEMS` `+61k`；`data/yahoo` 比总回报每年少算 `0.68%–2.66%` 分红 |
| **5. 行业 EPS、FOMC SEP、Kim-Wright & LSEG** | Yardeni `700` 行 + S&P DJI `145` 份 `.xlsx`（`150,190` 格）+ `76` 份 SEP PDF + LSEG `400` 周 | 美联储官方 PDF 原文 + S&P DJI 官方归档表 + `^GSPC`/`QQQ` | **部分通过，抓出 3 处硬缺陷** | **数学证明 LSEG `82221` 100% 是标普 500 `^GSPC` 而非 QQQ**；Yardeni `98.43%` 为曲线描点；SEP `2015-06` 前 30 期无官方中位数；S&P DJI `.xlsx` 单元格抽查 `0` 误差但缺 47 个月 |
| **6. Smart Money SEC Form 13F 机构库** | `53` 个 SEC 官方季度 `.zip`、`397,833` 份申报、`120,182,194` 行持仓 | 直接解包核对 SEC 官方原始 `SUBMISSION.tsv` & `INFOTABLE.tsv` | **100% 通过（生产级 PIT）** | `100.0%` 精确到秒级 `acceptance_datetime`；`CH-1`..`CH-13` 全 `PASS`；10 次跨年原始 `.zip` 随机直抽金额与股数 `0` 误差（注意勿误用仅含 `10,605` 份申报的开发子集 `13f.db`） |
| **7. 全仓库策略月度账本（Claude 原版 + Codex v2 + Top3 专题）** | 共 **`347` 份**月度策略账本（原版 `166` + Codex v2 `173` + Top3 专题 `8`） | 从底层 `raw` / `raw_open` / `raw_tiingo` / `raw_wiki` 逐月独立复算 | **算术复算 100% 通过（Codex v2 已修复原版破产下界与 ML2 偏差）** | 10 条主账本毛收益复算最大误差 `<= 1.11e-16`；原版唯一单月跌破 `-100%`（`2018-04 BCEI net=-100.2%`）已在 Codex v2 修正为 `-100.0%` 破产吸收 |

---

## 三、核心策略原版（Claude `78a2d0d`）vs 修正版（Codex v2 `4ea9a1d`）独立复算对照表

以下数字全部由本次审计脚本 `04_audit_all_ledgers.py` 直接从底层原始价格/开盘价文件逐月重算验证（毛收益逐月复算误差全部 $\le 1.11 \times 10^{-16}$）：

| 策略名称 | 成交方式 | 审计窗口（月数） | 原版 `78a2d0d` 净年化 (CAGR) | Codex v2 `4ea9a1d` 净年化 (CAGR) | Codex v2 月频最大回撤 | 差异原因与审计判定 |
|---|---|---|---|---|---|---|
| **全市场纯动量 Top1 (`NO_SECTOR_FILTER__top_1`)** | 月末收盘 → 下月末收盘 | `2009-01..2026-09` (213) | **36.59%** | **36.59%** (`36.585%`) | `-69.37%` (日频约 `-73%`) | **算术完全站得住**（微小 0.9bp 差异仅来自自融资乘性扣费替代加性扣费）；但高度依赖 2026 年前 9 个月牛股集中爆发（截至 2025 底为 `26.88%`） |
| **最强行业 → 行业内动量 Top1 (`SPEC`)** | 月末收盘 → 下月末收盘 | `2009-01..2026-09` (213) | **27.37%** | **27.36%** (`27.364%`) | `-50.66%` | **算术完全站得住**；仅 `2016-06-30` `TE` 1 个月受收盘后剔除时点影响（当月毛收益 `-0.33%`） |
| **全市场纯动量 Top10 (`Ref__top_10`)** | 月末收盘 → 下月末收盘 | `2009-01..2026-09` (213) | **15.50%** | **15.49%** | `-34.38%` | 算术精确；含 3 笔成分股边界瑕疵（`TE` 1 次、`CPRI` 双重计入 2 次） |
| **纯动量 Top3（跳过最近 1 个月，次日开盘成交）** | 次月初开盘 → 下月初开盘 | `2015-01..2026-09` (141) | **26.86%** (140 月) | **27.33%** (141 月) | `-25.76%` | **最干净、抗回撤显著优于 Top1 的纯价格基准**；补回被旧代码误丢的 `2015-01` 首月后共 141 个月 |
| **机器学习 `ML2 C-lgbm Top1`（动量 Top50 内基本面变化排序）** | 次月初开盘 → 下月初开盘 | `2015-01..2026-09` (141) | ~~46.12%~~ (140 月) | **33.39%** (141 月) | `-63.52%` | **原版超额收益主要来自泄漏与估值价失真**：修掉选参跨月开盘泄漏 + 改用未含未来分红的 `close` 算市值后，**跑输同窗口纯动量 Top1（`41.97%`）8.58 个百分点** |
| **机器学习 `ML2 C-lgbm Top3`** | 次月初开盘 → 下月初开盘 | `2015-01..2026-09` (141) | ~~36.69%~~ (140 月) | **17.86%** (141 月) | `-39.29%` | 同上修复后，**跑输同窗口纯动量 Top3（`27.33%`）9.47 个百分点**——说明现有基本面特征尚未证明能稳定战胜纯动量 |

---

## 四、固定随机种子（`seed=20261031`）100 张分层随机抽查结果

为彻底杜绝人工挑样本，脚本 [`05_stratified_random_spotcheck.py`](05_stratified_random_spotcheck.py) 使用固定随机数种子 `np.random.default_rng(20261031)`，按 8 个分层一次性随机抽取 **100 张审计卡**，逐笔重算并直接打到外部官方/独立数据源：

| 分层编号与抽样范围 | 抽查卡数 | `PASS_PRIMARY_VERIFIED`（外部主源核实无误） | `PASS_INTERNAL_SINGLE_VENDOR`（单源区间内部精确） | 数据警告 / 历史修订 | 真实口径缺陷命中 | 算术错误 (`FAIL_MATH`) |
|---|---:|---:|---:|---:|---:|---:|
| **S1**：标普 500 收盘成交笔数 (`2009–2018`) vs `WIKI` & `IVV` | 15 | **15** | 0 | 0 | 0 | **0** |
| **S2**：标普 500 次日开盘成交笔数 (`2019–2026`) vs `raw_open` & `IVV` | 15 | **12** | **3** | 0 | 0 | **0** |
| **S3**：拆股因子、代码改名别名、退市并购手工退出、纳指 100 合并池 | 10 | **7** | **2** | **1** (`ANDV` 换股忽略当月分红) | 0 | **0** |
| **S4**：中小盘 Holdout 实际持仓交易 vs `WIKI` & SEC FSDS | 15 | **14** | **1** | 0 | 0 *(全量扫描已单独列出 `GBTC` 等非 PIT 缺陷)* | **0** |
| **S5**：SEC EDGAR PIT 季报披露日、隔日生效与拆股 EPS 换算 vs `data.sec.gov` | 15 | **15** | 0 | 0 | 0 | **0** |
| **S6**：FRED 宏观观测点（实时联网查圣路易斯联储官网 API）& 行业 ETF 总回报 | 10 | **9** | 0 | **1** (`TNWBSHNO` 2013Q2 美联储后续下修) | 0 | **0** |
| **S7**：FOMC SEP 官方 PDF 原文、S&P DJI 归档 `.xlsx` 单元格、Yardeni、LSEG | 10 | **7** | **1** | 0 | **2** (`2014-12` SEP 无官方中位数；`LSEG 82221` 实为标普 500 而非 QQQ) | **0** |
| **S8**：Smart Money 13F 数据库 vs SEC 官方原始 `.zip` 内 `SUBMISSION/INFOTABLE.tsv` | 10 | **10** | 0 | 0 | 0 | **0** |
| **合计** | **100** | **89** | **7** | **2** | **2** | **0** |

> 全部 100 张核查卡的逐笔明细（含抽样实体、账本原值、独立复算值、外部主数据源核对证据、单卡结论）完整保存在：
> - Markdown 表格：[`05_random_spotcheck_100_cards.md`](05_random_spotcheck_100_cards.md)
> - CSV 原始表：[`05_random_spotcheck_100_cards.csv`](05_random_spotcheck_100_cards.csv)

---

## 五、只读边界校验与一键复现方法

### 1. 原始代码与历史归档零改动证明
审计开始前，[`00_baseline_integrity_guard.py`](00_baseline_integrity_guard.py) 对仓库内全部 **10,964 份**受保护回测代码、数据与账本文件记录了大小与 SHA-256 指纹（[`baseline_fingerprints.json`](baseline_fingerprints.json)）。全部审计脚本运行完毕后复验结果（[`baseline_integrity_check.json`](baseline_integrity_check.json)）：
- **`status`: `"PASS"`（`10,964` 份文件：`changed = 0`、`missing = 0`、`added = 0`）**。Claude 原版冻结文件与 Codex 独立副本未动一分一毫。

### 2. 本目录全部审计脚本与产出清单
- [`run_all_audits.sh`](run_all_audits.sh)：一键从头重跑全部全量审计 + 100 张随机抽查 + 只读指纹复验
- [`00_baseline_integrity_guard.py`](00_baseline_integrity_guard.py) → [`baseline_integrity_check.json`](baseline_integrity_check.json)
- [`01_audit_equity_prices_and_universes.py`](01_audit_equity_prices_and_universes.py) → [`01_equity_prices_and_universes_audit.json`](01_equity_prices_and_universes_audit.json)、[`ivv_vs_store_price_outliers_gt1pct.csv`](ivv_vs_store_price_outliers_gt1pct.csv)、[`sp500_yahoo_vs_wiki_monthly_outliers_gt2pct.csv`](sp500_yahoo_vs_wiki_monthly_outliers_gt2pct.csv)
- [`02_audit_sec_fundamentals.py`](02_audit_sec_fundamentals.py) → [`02_sec_fundamentals_audit.json`](02_sec_fundamentals_audit.json)
- [`03_audit_macro_sector_13f_datasets.py`](03_audit_macro_sector_13f_datasets.py) → [`03_macro_sector_13f_audit.json`](03_macro_sector_13f_audit.json)
- [`04_audit_all_ledgers.py`](04_audit_all_ledgers.py) → [`04_all_ledgers_audit.json`](04_all_ledgers_audit.json)、[`04_all_ledgers_inventory.csv`](04_all_ledgers_inventory.csv)
- [`05_stratified_random_spotcheck.py`](05_stratified_random_spotcheck.py) → [`05_random_spotcheck_summary.json`](05_random_spotcheck_summary.json)、[`05_random_spotcheck_100_cards.md`](05_random_spotcheck_100_cards.md)、[`05_random_spotcheck_100_cards.csv`](05_random_spotcheck_100_cards.csv)
