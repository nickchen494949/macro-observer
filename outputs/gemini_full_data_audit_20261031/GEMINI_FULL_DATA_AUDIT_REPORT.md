# 全库回测数据纯独立 Clean-Room 终版审计报告（`v3` 最终签收版：400 张随机核查卡 + 10 份核心策略全链路重建）

- **旗舰英文/双语技术终审报告**：[`v2_standalone/STANDALONE_AUDIT_V3_FINAL_REPORT.md`](v2_standalone/STANDALONE_AUDIT_V3_FINAL_REPORT.md)（兼容入口：[`v2_standalone/STANDALONE_AUDIT_V2_REPORT.md`](v2_standalone/STANDALONE_AUDIT_V2_REPORT.md)）
- **10 份核心策略全链路端到端 PIT 重建结果**：[`v2_standalone/v2_05_full_chain_pit_reconstruction_summary.json`](v2_standalone/v2_05_full_chain_pit_reconstruction_summary.json) | [`v2_standalone/v2_05_full_chain_picks_comparison.csv`](v2_standalone/v2_05_full_chain_picks_comparison.csv)
- **全部 347 份策略账本（`63,272` 策略月）100% 第一性原理成本与现金收益复算表**：[`v2_standalone/v2_01_all_347_ledgers_cleanroom_audit.csv`](v2_standalone/v2_01_all_347_ledgers_cleanroom_audit.csv) | [`v2_standalone/v2_01_all_347_ledgers_cleanroom_summary.json`](v2_standalone/v2_01_all_347_ledgers_cleanroom_summary.json)
- **300 张严格 9 层互斥随机主核查表**：[`v2_standalone/v2_300_master_random_cards.md`](v2_standalone/v2_300_master_random_cards.md) | [`v2_standalone/v2_300_master_summary.json`](v2_standalone/v2_300_master_summary.json)
- **100 张 SEC XBRL 非空数值事实卡（`100/100` 实时 `data.sec.gov`）**：[`v2_standalone/v2_02_sec_xbrl_100_cards.md`](v2_standalone/v2_02_sec_xbrl_100_cards.md) | [`v2_standalone/v2_02_sec_xbrl_100_summary.json`](v2_standalone/v2_02_sec_xbrl_100_summary.json)
- **100 张 SEC XBRL `NULL` 空值完整性核查卡（`100/100` 实时 `data.sec.gov`）**：[`v2_standalone/v2_04_sec_xbrl_100_null_cards.md`](v2_standalone/v2_04_sec_xbrl_100_null_cards.md) | [`v2_standalone/v2_04_sec_xbrl_100_null_summary.json`](v2_standalone/v2_04_sec_xbrl_100_null_summary.json)
- **`ast.parse` 零项目依赖、零读取账本成本列 & `10,964` 文件只读指纹守卫证明**：[`v2_standalone/v2_00_cleanroom_guard_report.json`](v2_standalone/v2_00_cleanroom_guard_report.json)（`scripts_checked = 7, total_ast_or_pattern_violations = 0`；`10,964` 份受保护文件 `changed = 0`）

---

## 一、人话总结论（`v3` 终审定案）

针对上一轮外部审计提出的 **6 项最终签收升级要求**，我们在 `v2_standalone/` 完成了彻底的机械级加固并从头跑通全部 7 阶段独立审计流水线。现在的结论边界做到了 **100% 硬证据支撑、零夸大审计范围**：

### 1. 已从最底层原始文件 100% 全链路重建并外部核对通过的核心资产（可放心签收）
- **标普 500 全部 8 份核心纯动量与行业动量（`SPEC`）主账本（`v2_05` 全链路端到端重建 `8 / 8 PASS`）**：
  - 不读取任何项目预生成 Parquet/CSV，不读取账本任何成本或现金列，直接从原始成分股区间、原始价格/开盘价 JSON、142 份 SEC FSDS 原始 `sub_*.parquet`（独立重建 `41/41` 别名与 `842/842` CIK 映射，100% 一致）、历史 GICS 行业规则与一阶自融资/加性扣费公式从头跑出每月选股与净收益：
    1. **全市场纯动量 Top1（收盘→收盘，`2009-01..2026-09`，213 个月）**：原版 `36.59%` / Codex v2 自融资 `36.59%`（`213/213` 选股、`213/213` 候选股数完全一致，`max |net_diff| <= 1.67e-16`；有贝莱德官方 `IVV` 持仓快照的 **`135 / 135` 个月 100.0% 确认为真实 `IVV` 持仓成分股**）。
    2. **最强行业 → 行业内 Top1 `SPEC`（收盘→收盘，`2009-01..2026-09`，213 个月）**：原版 `27.37%` / Codex v2 自融资 `27.36%`（`213/213` 最强行业、`213/213` 选股完全一致，`max |net_diff| <= 1.63e-16`；官方 `IVV` **`135 / 135` 个月 100.0% 确认**）。
    3. **纯动量 Top1（次日开盘→次月开盘，`2015-01..2026-09`，141 个月，`ML2` 基准）**：净年化 **`41.97%`**（`141/141` 选股完全一致，`max |net_diff| = 9.71e-17`；官方 `IVV` **`135 / 135 = 100.0%` 确认**）。
    4. **纯动量 Top3（次日开盘→次月开盘，`2015-01..2026-09`，141 个月，3 份专题与基准账本）**：净年化 **`27.33%`**（`141/141` 选股完全一致，`max |net_diff| = 2.22e-16`；官方 `IVV` **`404 / 405 = 99.75%` 确认**，唯一 1 笔未匹配为 `2018-05-31 CPRI`，当时贝莱德仍按改名前旧代码 `KORS` 持仓）。
- **Smart Money SEC Form 13F 机构持仓全量库（`13f_full_4409f14.db`，39.78 万份申报 / 1.20 亿行）**：随机盲抽 **`40` 份跨年申报**，不截断行数、不用 `set()` 去重，直接对原始 SEC `.zip` 内整份 `INFOTABLE.tsv` 做 **100% 排序多重集全等比对（`sorted(raw_rows) == sorted(db_rows)`）**：**`40 / 40` 份申报（共 `18,099` 条持仓元组）100% 分毫不差**。
- **SEC 原始 XBRL 首次披露财报事实与 57 维特征算术**：从 142 份原始 SEC FSDS `sub/num` Parquet 独立重建 `94,010 行 × 57 特征 = 5,358,570` 个特征单元格，与 `Codex v2` 特征面板 **`94,010 / 94,010` 行完全对齐、`0` 个 `NaN` 错位、最大浮点差仅 `2.075e-14`**。`100` 张非空 XBRL 随机卡 **`100/100` 实时 `data.sec.gov` 确认**（`98` 张 `PASS_EXTERNAL_PRIMARY`、`2` 张 Q4 EPS 保守置空警告、`0` 张错误）；新增 **`100` 张 `NULL` 空值完整性随机卡（`v2_04`）** 按总体加权证明：**`65.40%`** 为 SEC 原始申报确实未披露该季度标签，**`32.24%`** 为公司使用了银行/公用事业/REITs 等替代 US-GAAP 标签而解析器未纳入，**`2.36%`** 为缺 9M 累计值或非美元币种导致的保守置空。

### 2. 本轮 `v3` 全链路重建与一阶成本复算新抓出的重大发现（之前任何一轮审计均未发现）
- **重大新发现 E — `Codex v2` 的 `CAM 2016-04-01` `<` 开盘价边界 Bug 不仅导致 5 份 Ridge 账本持仓算错 `200.1 bp`，更通过 Top-50 训练池级联放大了 `ML2 C-lgbm Top1` 的收益（`33.39% -> 16.33%`），且 `Codex v2` 估值比仍残留 `adjclose` 未来分红折算（纯无分红复算为 `23.51% / 14.08%`）**：
  1. **根因精确定位到 2 行训练标签**：`Codex v2`（`backtest.py:222` + `ml2_run.py:89`）在拼接 WIKI 开盘价时写了严格小于 `< 2016-04-01`（应为 `<=`），误把被斯伦贝谢收购的 `CAM` 最后一个真实开盘价 `O['2016-04-01', 'CAM'] = 66.18` 抹成 `NaN`。上一轮只查“给定选股后的组合收益”时，我们以为只有当天买入 `CAM` 的 5 份 Ridge 账本受影响；但本轮 `v2_05` 从头训练 `ML2` 发现：**`CAM` 在 `2016-02-29`（动量第 9 名，出场日 `2016-04-01`）和 `2016-03-31`（动量第 10 名，入场日 `2016-04-01`）均处于 Top-50 训练池内**！这 1 天的 `<` bug 改写了 `CAM` 这 **2 行**训练标签 `ret_oo`（`2016-02-29` 相差 `+200.081 bp`，`2016-03-31` 相差 `-25.688 bp`）。
  2. **双向数学闭环验证**：在 `v2_05` 中若仅模拟这 1 天的 `<` bug，我们的无尘室管线 **100% 逐月复现 `Codex v2` 的 `C-lgbm Top1`（`33.39%`，`141/141` 选股、`12/12` 年度选参一致，误差 `1.67e-16`）和 `C-lgbm Top3`（`17.86%`，`141/141` 选股一致，误差 `2.22e-16`）**；而**只要修掉这 1 天的 `<` bug（改为正确的 `<=`）**，2017 年起的树分裂与 `[Y-2, Y-1]` `num_leaves` 选参随之改变，**`C-lgbm Top1` 净年化直接从 `33.39%` 跌至 `16.33%`（`-17.06` 个百分点，`104/141` 个月选股相同）**，`C-lgbm Top3` 从 `17.86%` 变为 `18.69%`（`68/141` 个月 3 股集合完全相同）！
  3. **100% 去分红纯拆股历史价格估值敏感性测试（`v2_05 Step 5`）**：`Codex v2` 的 `ml_features.py`（第 21–22、220–226 行）在计算 `ep / deps_p / log_mcap / sp / bm / cfo_yield` 6 个估值特征时，仍用经拆股调整的基本面除以含未来现金分红回溯折算的 `adjclose[t]`。将这 6 个特征彻底替换为 **100% PIT 无未来分红的 `raw_close[t] / split_factor_after(t)`**（配合无 bug 的 `<=` 开盘价）重跑 12 年滚动训练后，**`C-lgbm Top1` 净年化为 `23.51%`**（比存储值 `33.39%` 低 `-9.88 pp`，比 `<=` `adjclose` 版高 `+7.18 pp`），**`C-lgbm Top3` 净年化为 `14.08%`**（比存储值 `17.86%` 低 `-3.78 pp`）。**结论非常明确**：无论在哪一种严格无泄漏口径下，现有 `ML2 C-lgbm` 都显著跑输完全验证通过的**纯动量基准（Top1 `41.97%`、Top3 `27.33%`）**，且 Top1 机器学习排序对极小样本扰动高度脆弱。
- **重大新发现 C — FOMC SEP `data/sep_revisions.json` 全量 74 行官方 PDF Table 1 坐标级普查（`v2_03`）**：用 PyMuPDF 单词坐标精确锁定每期官方 PDF `Table 1` 的 `(Median × target_year)` 单元格同时核查 `Core PCE` 与 `Federal funds rate` 后，74 行全部水落石出：**`31` 行**（`2015-09` 之前）美联储官方 Table 1 根本没有发布 `Median` 列；**`11` 行**（集中在 `2015-09..2018-12`）存在早期人工/脚本摘录错格（误摘了 Headline PCE、相邻年份列或把 `1.4` 利率填进 `pce`）；**`32` 行**两格双双 `0.0000` 精确吻合（其中 **`2019-03` 至 `2026-06` 连续 `29 / 29` 期 100.0% 零误差**）。

---

## 二、外部审计 6 项最终签收要求落实总表

| # | 外部审计最终签收要求 | `v2_standalone/` 机械级实现 | 执行验证证据 |
|---|---|---|---|
| **1** | **零读取账本 `turnover`、`capital_after_costs`、`cash_return` 及月度 `rf` CSV**（100% 第一性原理算换手费与现金收益） | [`v2_00_cleanroom_ast_and_readonly_guard.py`](v2_standalone/v2_00_cleanroom_ast_and_readonly_guard.py) 源码级封禁上述所有列名与文件名；[`v2_cleanroom_lib.py`](v2_standalone/v2_cleanroom_lib.py) 仅凭 `(picks, weights)` + 原始日/月收益独立递推漂移权重 `w_prev`、季频漂移、6 子仓重叠 `hold6m` 扣费、自融资二分求解及原始 `data/fred/DGS3MO.json` 现金收益 | `7` 个脚本 `violations = 0`；全库 `347` 份账本中 `298` 份一阶复算 `PASS`，精准揪出 `20` 份扣费/并购退出不一致账本（含 `5` 份 `Codex v2` Ridge `CAM` 账本与 `8` 份原版 `NDX` 硬扣 `20bp` 账本） |
| **2** | **核心策略从原始文件端到端全链路 PIT 信号/特征/模型/选股重建** + 其余账本诚实标注审计范围 | [`v2_05_full_chain_pit_strategy_reconstructor.py`](v2_standalone/v2_05_full_chain_pit_strategy_reconstructor.py) 零项目依赖、零读取预生成 Parquet，端到端重建 **10 份核心主账本**；`v2_01` 对其余次级网格账本如实标注 `RETURN_AND_FIRST_PRINCIPLES_COST_VERIFIED_ONLY`（`211` 份），绝不夸大为全链路重建 | **8 份纯动量与 `SPEC` 主账本 `100% PASS`（`max |net_diff| <= 2.22e-16`）**；**2 份 `Codex v2` `C-lgbm` 账本精准抓出 `CAM` 训练池级联（`33.39% -> 16.33%`）与无分红估值敏感性（`23.51% / 14.08%`）** |
| **3** | **SEC 13F 整份申报 100% 排序多重集全等比对**（禁止 `set()` 吞掉同 CUSIP 多子管理人重复行） | `v2_03` Part C 直接比对 `sorted(raw_rows) == sorted(db_rows)`，覆盖整份申报全部 `(cusip, raw_value, value_usd, shares, put_call)` 元组 | **`40 / 40` 份申报（`18,099` 条持仓）100% 多重集全等 `PASS_EXTERNAL_PRIMARY`** |
| **4** | **FRED 当 `ALFRED_initial = None` 时严禁计入 `PASS_EXTERNAL_PRIMARY`** | `v2_03` Part D 新增独立层级 **`PASS_EXTERNAL_LATEST_ONLY`**（`5` 张卡），仅在 ALFRED 确有历史初值且 `0` 修订时才授予 `PASS_EXTERNAL_PRIMARY` | `PASS_EXTERNAL_LATEST_ONLY = 5` 与 `PASS_EXTERNAL_PRIMARY = 199` 严格分离 |
| **5** | **官方美联储 FOMC SEP PDF Table 1 坐标级单元格解析（`Core PCE` + `Fed funds rate` 双指标）** | `v2_cleanroom_lib.py` 用 PyMuPDF `(x0, y0)` 坐标定位 `Table 1` 的 `Median` 表头区间与 `target_year` 列中心，对全部 `74` 行做完整普查 | 普查全量 74 行：`31` 行无官方中位数、`11` 行 `2015–2018` 摘录错格、**`32` 行双指标 `0.0000` 吻合（`2019-03..2026-06` 连续 `29/29 = 100%`）** |
| **6** | **新增 100 张 SEC 财报 `NULL` 空值完整性随机核查卡（`N001..N100`）** | [`v2_04_sec_xbrl_100_null_completeness_auditor.py`](v2_standalone/v2_04_sec_xbrl_100_null_completeness_auditor.py) 扫描全部 142 份 SEC FSDS 原始 Parquet + `100/100` 实时 `data.sec.gov`，输出 Horvitz-Thompson 总体加权归因与全库零财报代码清单 | 样本计数 `38` 真缺失 / `54` 替代标签未纳入 / `8` 保守置空；总体加权占比 **`65.40%` 真缺失 / `32.24%` 替代标签 / `2.36%` 保守置空** |

---

## 三、核心策略全链路端到端无尘室重建对照总表（`v2_05`）

| # | 核心策略与成交/扣费口径 | 窗口（月数） | 无尘室全链路判定（`<=` 无 Bug 开盘价） | 选股一致率 | 无尘室净年化 | 账本记录净年化 | 最大月净收益差 | 贝莱德官方 `IVV` 持仓外部确认 |
|---:|---|---:|---|---:|---:|---:|---:|---|
| **1** | 全市场纯动量 Top1（收盘，加性，原版） | `2009-01..2026-09` (`213`) | **`PASS`** | **`213 / 213`** | **`36.59%`** | `36.59%` | `9.71e-17` | **`135 / 135` (`100.0%`)** |
| **2** | 全市场纯动量 Top1（收盘，自融资，`Codex v2`） | `2009-01..2026-09` (`213`) | **`PASS`** | **`213 / 213`** | **`36.59%`** | `36.59%` | `1.67e-16` | **`135 / 135` (`100.0%`)** |
| **3** | 最强行业→个股 `SPEC`（收盘，加性，原版） | `2009-01..2026-09` (`213`) | **`PASS`**（`213/213` 行业） | **`213 / 213`** | **`27.37%`** | `27.37%` | `9.97e-17` | **`135 / 135` (`100.0%`)** |
| **4** | 最强行业→个股 `SPEC`（收盘，自融资，`Codex v2`） | `2009-01..2026-09` (`213`) | **`PASS`**（`213/213` 行业） | **`213 / 213`** | **`27.36%`** | `27.36%` | `1.63e-16` | **`135 / 135` (`100.0%`)** |
| **5** | 纯动量 Top1（次日开盘，自融资，`ML2 Bench`） | `2015-01..2026-09` (`141`) | **`PASS`** | **`141 / 141`** | **`41.97%`** | `41.97%` | `9.71e-17` | **`135 / 135` (`100.0%`)** |
| **6** | 纯动量 Top3（次日开盘，自融资，`ML2 Bench`） | `2015-01..2026-09` (`141`) | **`PASS`** | **`141 / 141`** | **`27.33%`** | `27.33%` | `2.22e-16` | **`404 / 405` (`99.75%`)** |
| **7** | 纯动量 Top3（次日开盘，`Top3_skip_monthly`） | `2015-01..2026-09` (`141`) | **`PASS`** | **`141 / 141`** | **`27.33%`** | `27.33%` | `2.22e-16` | **`404 / 405` (`99.75%`)** |
| **8** | 纯动量 Top3（次日开盘，`Top3_qqq_rebalance`） | `2015-01..2026-09` (`141`) | **`PASS`** | **`141 / 141`** | **`27.33%`** | `27.33%` | `2.22e-16` | **`404 / 405` (`99.75%`)** |
| **9** | `Codex v2` `ML2 C-lgbm Top1`（滚动训练，次日开盘） | `2015-01..2026-09` (`141`) | **`FLAGGED_CAM_TRAINING_OPEN_CUTOFF_CASCADE`** *(模拟 `<` bug 时 `141/141` 精确复现 `1.67e-16`)* | `104 / 141` *(模拟 `<`: `141/141`)* | **`16.33%`** *(无分红估值: **`23.51%`**)* | `33.39%` | `2.81e-01` *(模拟 `<`: `1.67e-16`)* | 受 `CAM` 训练标签 `<` bug（`-17.06 pp`）与 `adjclose` 未来分红敏感性影响 |
| **10** | `Codex v2` `ML2 C-lgbm Top3`（滚动训练，次日开盘） | `2015-01..2026-09` (`141`) | **`FLAGGED_CAM_TRAINING_OPEN_CUTOFF_CASCADE`** *(模拟 `<` bug 时 `141/141` 精确复现 `2.22e-16`)* | `68 / 141` *(模拟 `<`: `141/141`)* | **`18.69%`** *(无分红估值: **`14.08%`**)* | `17.86%` | `1.34e-01` *(模拟 `<`: `2.22e-16`)* | 受 `CAM` 训练标签 `<` bug（`+0.83 pp`）与无分红估值（`-3.78 pp`）影响 |

---

## 四、300 张严格 9 层互斥随机主核查表（`v2_03`）+ 100 张 `NULL` 空值完整性核查表（`v2_04`）

### 1. 300 张主随机核查卡（9 个严格互斥结论层级）

| 互斥结论层级 | A: 全 347 账本零过滤双阶段盲抽 | B: SEC 原始 XBRL + 实时 `sec.gov` | C: SEC 13F `.zip` 100% 多重集全等 | D: 宏观 / 坐标级 SEP / S&P DJI / ETF | **300 卡合计** | **占比** |
|---|---:|---:|---:|---:|---:|---:|
| **`PASS_EXTERNAL_PRIMARY`** *(经真正外部独立主源验证：SEC EDGAR/FSDS、100% 多重集 13F `.zip`、贝莱德官方 `IVV` 快照、WIKI/Tiingo 第二源、ALFRED 未修订初值、坐标解析 SEP Table 1、S&P DJI `.xlsx`)* | **48** | **98** | **40** | **13** | **199** | **`66.33%`** |
| **`PASS_INTERNAL_MATH_SINGLE_VENDOR`** *(单价格源覆盖区间内原始成分与一阶换手扣费算术精确)* | 51 | 0 | 0 | 0 | **51** | **`17.00%`** |
| **`UNVERIFIABLE_NET_ONLY_LEDGER`** *(无过滤盲抽自然命中 27 份无 `picks` 旧 `factor_combo` 账本)* | **12** | 0 | 0 | 0 | **12** | **`4.00%`** |
| **`DATA_WARNING_KNOWN_LIMITATION`** *(ALFRED 宏观修订、Yardeni 描点、`-100%` 压力破产行、换股并购分红省略、Q4 EPS 保守置空)* | 3 | 2 | 0 | 6 | **11** | **`3.67%`** |
| **`DATA_DEFECT_CONFIRMED`** *(中小盘混入 `BDRY/GBTC/UNG` 3、2015–2018 SEP Table 1 摘录错格 3、LSEG `82221=^GSPC` 2)* | **3** | 0 | 0 | **5** | **8** | **`2.67%`** |
| **`UNVERIFIABLE_MISSING_RAW_INPUT`** *(2015-09 前 SEP 官方无 `Median` 列或缺失历史归档原文件)* | 0 | 0 | 0 | **6** | **6** | **`2.00%`** |
| **`PASS_EXTERNAL_LATEST_ONLY`** *(实时 `api.stlouisfed.org` 最新值 `0` 误差吻合，但 ALFRED 无历史初值返回，严格降级单列)* | 0 | 0 | 0 | **5** | **5** | **`1.67%`** |
| **`PASS_INTERNAL_CROSS_STORE`** *(同源双本地缓存一致，绝不混充外部主源)* | 0 | 0 | 0 | **5** | **5** | **`1.67%`** |
| **`FAIL_MATH_OR_FACT_MISMATCH`** *(一阶换手扣费抓出原版 NDX 硬扣 `20bp/月` 错误：`L007`、`L030`、`L083`)* | **3** | **0** | **0** | **0** | **3** | **`1.00%`** |
| **合计** | **120** | **100** | **40** | **40** | **300** | **`100.00%`** |

### 2. 100 张 SEC 财报 `NULL` 空值完整性随机核查卡（`v2_04`，`N001..N100`）
- **`TRUE_ABSENT_IN_SEC_XBRL`**：样本 **`38 / 100`**，Horvitz-Thompson 总体加权占比 **`65.40%`**（SEC 原始 FSDS 与实时 `data.sec.gov` 均确认该季度确实未披露任何主标签或替代标签）。
- **`PARSER_OMITTED_ALTERNATIVE_TAG_IN_SEC`**：样本 **`54 / 100`**，总体加权占比 **`32.24%`**（公司披露了 `NetIncomeLossAvailableToCommonStockholdersBasic`、公用事业 `RegulatedAndUnregulatedOperatingRevenue`、银行 `InterestIncomeExpenseNet`、油气 `OilAndGasRevenue`、REITs `RealEstateRevenueNet` 等行业/替代标签，指明了未来扩充基本面解析器的精确标签清单）。
- **`CONSERVATIVE_RULE_BLANK_UNAMBIGUOUS_QTR_UNAVAILABLE`**：样本 **`8 / 100`**，总体加权占比 **`2.36%`**（仅有全年 `qtrs=4` 缺 `qtrs=3` 9M 申报或采用 `GBP`/`CAD` 非美元计价，按保守规则置空未做猜测）。

---

## 五、一键完整复现全部 7 阶段独立无尘室审计

```bash
bash outputs/gemini_full_data_audit_20261031/v2_standalone/run_v2_standalone_audit.sh
```
