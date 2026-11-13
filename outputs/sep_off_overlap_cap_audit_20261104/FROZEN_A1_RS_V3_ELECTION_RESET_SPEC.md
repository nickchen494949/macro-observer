# 冻结版规范与完整研发演进总纲：`V4 Symmetric Sharpe Top-2` & `V3 A1-RS + Election Reset` (2026-11-13)

> **本文件用途**：作为项目根目录最高优先级的策略冻结规范与研发溯源档案（与 `.agents/AGENTS.md` 及 `README.md` 联动），确保任何新开启的对话（New Chat）在第一回合即完整掌握**最终冻结规则（V4 极简对称版 & V3 三腿杠杆版）、全部历史回测数据、8 大推导阶段、被证伪/放弃的分支原因，以及全部 27 个审计目录的脚本索引**。

---

## 一、 策略定位与定级

1. **最新冻结极简对称版（V4 Latest Frozen — 零补丁统一双核架构，2026-11-13）**：
   - **`Symmetric_Sharpe_Top2_V4`**（无杠杆 `1.0x`：214M CAGR **`59.65%`–`59.74%`**，Sharpe **`1.426`–`1.429`**，全周期逐笔交易胜率 **`70.16%`–`71.09%`**，2026 实盘日频 MaxDD **`-18.88%`**；叠加可选 **`V3 Election Reset` 保险**后 214M CAGR **`60.78%`**，Sharpe **`1.445`**）
   - **独立复现引擎**：[`independent_v4_symmetric_sharpe_top2_audit.py`](./independent_v4_symmetric_sharpe_top2_audit.py)
   - **核心极简规则（全天候同一套个股动量公式 `12-1 Sharpe + Buy Top-2 / Hold <= 5`）**：
     - **`SEP = ON`（顺风期，180 个月）**：**`50% QQQ #1 + 50% QQQ #2`**（Nasdaq-100 成分股，`12-1 Sharpe` 排名，`Buy Top-2 / Hold <= 5`，单笔胜率 `69.23%`，赔率 `4.49:1`）。
     - **`SEP = OFF`（逆风紧缩期，34 个月）**：**`50% SGOV` + `25% BestSec #1 + 25% BestSec #2`**（先在 S&P 500 的 10 个非科技 GICS 板块中按等权 `12-1 Raw` 动量选出第 1 名板块 `BestSec`，再在该板块内按 **`12-1 Sharpe` 选出前 2 名股票 `Buy Top-2 / Hold <= 5` [或 `Hold <= 3`]**，逆风期单笔胜率高达 **`75.00%`–`79.17%`**，赔率 `2.70:1–2.87:1`）。
     - **2026 年 11 月实盘持仓（`SEP = OFF`，`BestSec = Energy`，无论 Reset 或 Follow 100% 一致）**：**`25% VLO + 25% MPC + 50% SGOV`**。
2. **三腿温和杠杆冻结版（V3 Frozen Challenger — 2026-11-05）**：
   - **`A1-RS_ModBurst_135_75_25_GateV1_ElectionResetV3`**（简称 **`A1-RS 1.35x + V3 Election Reset`**，214M CAGR **`64.95%`**，Sharpe **`1.489`**）
3. **原版三腿正式主线（Production Baseline）**：
   - **`BestSec_ModBurst_135_75_25_GateV1`**（原版 `1.35x`，214M CAGR `60.96%`，Sharpe `1.414`）

---

## 二、 完整冻结规则（四层架构）

### 1. 常态选股与缓冲层（Rank + Sector RS）
- **调仓频率与执行**：每月末最后交易日收盘（formation date $t$）计算信号，次月首个交易日开盘（$d_0$ Open）执行，单账户双边换手成本 `10 bp/side`（含跨腿漂移对冲）。
- **各腿选股与缓冲规则（100% 仅使用 $t$ 时刻已知信号，严禁使用 `hold_ret.notna()`）**：
  - **`QQQ` 腿（Nasdaq-100 成分股）**：`12-1 Sharpe` 动量排名，`Buy Top-2 / Hold <= 5`。
  - **`Tech` 腿（S&P 500 信息技术板块，严格 PIT GICS 分类）**：`12-1 Raw` 动量排名，**`Hard Top-1`（`Hold <= 1`，无缓冲）**。
  - **`SPY` 腿 / `Ex-IT Raw` 腿**：`12-1 Raw` 动量排名，**`Buy Top-1 / Hold <= 3 + 板块相对强弱过滤 (RS_sec >= -5.0%)`**：
    - 老持仓仍为第 1 名（`Rank = 1`）：无条件继续持有；
    - 老持仓退居第 2–3 名（`Rank in {2, 3}`）：
      - 若最近 1 个月相对所属 GICS 板块等权收益 $\text{RS}_{\text{sec}} = r_{1\text{M},\text{stock}}(t) - r_{1\text{M},\text{sector}}(t) \ge -5.0\%$：保留缓冲，继续持有；
      - 若 $\text{RS}_{\text{sec}} < -5.0\%$：取消缓冲，换入当前第 1 名；
    - 老持仓跌出前 3 名（`Rank > 3`）：卖出并换入当前第 1 名。
  - **`Ex-IT BestSec` 腿（非科技最强板块第 1 名）**：先按 S&P 500 非科技 GICS 板块等权 `12-1` 动量选出第 1 名板块，再在该板块内按 `Buy Top-1 / Hold <= 3 + RS_sec >= -5.0%` 选股。

---

### 2. 宏观状态切换与去重层（`SEP = ON` vs `SEP = OFF` Route A1）
- **`SEP = ON`（美联储 FOMC SEP 利率路径非鹰派紧缩）**：
  - 基础权重：`50% QQQ (25% × 2) + 25% Tech + 25% SPY`。
  - **Gate V1 低波温和加杠杆（`1.20x / 1.35x`，75/25 分散）**：
    - 激活条件：`qqq_vol21 <= 30%` 且 `port_vol_est <= 55%` 且 `not dm_panic`；
    - `Confirmed 2-Leg` 共振：总敞口 **`1.20x`**；
    - `3-Leg` 共振（`Tech == SPY` 且在 `QQQ Top-2` 中）：总敞口 **`1.35x`**，保持 `75% 共振主股 + 25% QQQ 另一只持仓`（单股最高 **`101.25%`**，不做 `100%` 单股集中）。
- **`SEP = OFF`（美联储 FOMC SEP 紧缩期，无杠杆 `1.00x`）**：
  - 基础权重：`25% Tech + 25% SPY + 25% Ex-IT BestSec + 25% SGOV`。
  - **路线 A1 单科技股去重规则**：
    - 若 `Tech == SPY`（两腿同时选中同一只 IT 股票）：保留 `Tech` 的 `25%`，将 `SPY` 的 `25%` 改买 **`Ex-IT Raw`**（即变为 `25% Tech + 25% Ex-IT Raw + 25% Ex-IT BestSec + 25% SGOV`）。

---

### 3. 中期选举政体翻转重置层（`V3 Election Reset`）
- **触发条件**：美国中期选举（Midterm Election，11 月初举行）结果确认为 **`Unified Government → Divided Government`**（执政党失去参议院或众议院多数，由统一政府变为分裂政府；2009–2026 历史样本为 **2010、2018、2022**，未发生翻转的 2014 不触发）。
- **执行动作（`V3` 标准版）**：
  1. **大选年 12 月（`YYYY-12`，于 `YYYY-11` 月底收盘调仓）**：
     - 组合转入 **`100% SGOV`** 防守观察 1 个月，规避旧政策预期刹车引发的动量因子年末踩踏。
  2. **次年 1 月（`YYYY+1-01`，于 `YYYY-12` 月底收盘调仓）**：
     - **清空全部选股腿的 `Hold-3 / Hold-5` 历史持仓缓冲记忆（`held = []`）**；
     - 在 `YYYY-12` 月底完全按最新排名从零选出各腿第 1 名（`QQQ` 选第 1、第 2 名），于 `YYYY+1-01` 首个交易日开盘恢复正常策略运行，第一时间跟上新政体周期的领头羊。

---

## 三、 核心回测业绩对比（2009-01 至 2026-10，零共享代码独立引擎）

| 策略版本 | 213M CAGR<br>*(至26/09)* | **214M CAGR**<br>*(含26年10月)* | Sharpe<br>*(213M / **214M**)* | 月频 MaxDD | **历史日频 MaxDD** | **2026 实盘日频 MaxDD** | 最低保证金率<br>(`MinMER`) | 三次翻盘 12月<br>`[10 / 18 / 22]` | 三次翻盘次年 1月<br>`[11 / 19 / 23]` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1. 原版 `1.35x` 正式主线**<br>(`BestSec_ModBurst_135_75_25_GateV1`) | 62.46% | **60.96%** | 1.443 / **1.414** | -22.42% | -34.63% | -26.98% | 70.6% | `[-7.4%, -8.5%, -10.5%]` | `[+7.9%, +20.0%, +4.7%]` |
| **2. `A1-RS (-5.0%) 1.35x`（无选举重置）**<br>(`A1-RS_ModBurst_135_75_25_GateV1`) | 62.84% | **62.28%** | 1.444 / **1.435** | -22.74% | -34.64% | **-25.88%** | 70.6% | `[-7.4%, -8.5%, -10.5%]` | `[+7.9%, +20.0%, +5.9%]` |
| **3. 冻结版：`A1-RS 1.35x + V3 Election Reset`** 🏆<br>(`A1-RS_ModBurst_135_75_25_GateV1_ElectionResetV3`) | **65.54%** | **64.95%** | **1.498 / 1.489** | **-22.74%** | **-34.64%** | **-25.88%** | **70.6%** | **`[-0.2%, -0.0%, +0.2%]`** | **`[+13.7%, +19.9%, +5.9%]`** |
| **4. 进取对照：`A1-RS 1.50x + V3 Election Reset`**<br>(`A1-RS_Prudent_150_75_25_GateV1_ElectionResetV3`) | **68.71%** | **68.10%** | **1.504 / 1.496** | **-22.42%** | **-34.79%** | **-25.88%** | 62.2% | `[-0.2%, -0.0%, +0.2%]` | `[+14.3%, +19.9%, +5.9%]` |

---

## 四、 2026 年 11 月 – 2027 年 1 月实盘执行日历

1. **2026 年 11 月（当前持仓，已建仓）**：
   - `SEP = OFF`，维持 **`25% SNDK + 25% VLO + 25% MRNA + 25% SGOV`**。
2. **2026 年 11 月 30 日收盘（决定 2026 年 12 月持仓）**：
   - **分支 A（若 2026 年 11 月中期选举确认为 `Unified → Divided`）**：触发 `V3 Election Reset`，12 月全月持仓切换为 **`100% SGOV`**。
   - **分支 B（若共和党保住参众两院，维持 `Unified → Unified`）**：不触发 `V3 Election Reset`，按常规 `A1-RS` 规则运行。
3. **2026 年 12 月 31 日收盘（决定 2027 年 1 月持仓）**：
   - 若 12 月触发了 `V3 Election Reset`：在 12 月 31 日收盘计算信号时，**清空全部 `Hold-3 / Hold-5` 历史缓冲记忆**，完全按 2026 年 12 月底最新排名直接选出各腿第 1 名（`QQQ` 第 1–2 名），于 **2027 年 1 月 4 日开盘**建仓。

---

## 五、 完整研发演进脉络：我们是如何一步步推导出这个结论的？（防重复踩坑指南）

> **重要提示**：未来任何新对话在提出策略修改建议前，必须先查阅以下 **7 个阶段的历史回测结论与已证伪方向**，避免重复测试已被证明无效或有害的方案。

### 阶段 1：从板块 ETF 轮动到成分股动量的跃迁（2026-10-28 至 10-31）
- **被证伪方向（已放弃）**：
  1. **板块 ETF 9 特征随机森林（RF）**：小样本严重过拟合噪声，OOS 失效。
  2. **ETF 隐含 EPS 动量 / 加速因子（`outputs/sector_eps_then_momentum_20261030/`）**：在无生存偏差的真实成分股池上 IC $\approx 0$。
  3. **单纯“先选第 1 名板块、再买板块内第 1 名个股”单股策略（`research/sector_stock_momentum/`）**：虽然 OOS（2021–2026）CAGR 高达 `87.4%`，但 IS（2009–2021）CAGR 仅 `4.8%`（Sharpe `0.29`），单股波动率高达 `70%`，且受单月极端个股影响过大。
- **核心发现**：
  - 个股 `12-1` 动量的 Alpha 远强于 ETF，但单一股票池或单只股票的周期脆弱性太高，必须通过**跨指数池（Nasdaq-100 + S&P 500 IT + S&P 500 全市场）多腿共振与不同缓冲机制**来稳定 Sharpe 与回撤。

### 阶段 2：三腿核心架构（`QQQ + Tech + SPY`）与各腿差异化选股/缓冲规律（2026-11-01 至 11-03）
- **审计报告**：
  - `outputs/qqq_mom_top3_claude_audit_20261103/CLAUDE_CLEANROOM_AUDIT_REPORT.md`
  - `outputs/tech_top1_independent_audit_20261103/CLAUDE_INDEPENDENT_AUDIT_REPORT.md`
  - `outputs/core3_stock_selection_audit_20261103/CORE3_STOCK_SELECTION_AUDIT_REPORT.md`
  - `outputs/qqq_lgbm_cleanroom_audit_20261103/QQQ_LGBM_CLEANROOM_AUDIT_REPORT.md`
- **关键实证结论**：
  1. **为什么不用 LightGBM 机器学习选股？**
     - Clean-room 独立审计证明，`QQQ` 上的纯规则 `12-1 Sharpe (Buy Top-2, Hold <= 5)` 在风险调整后收益、透明度和零过拟合稳定性上全面优于 18 特征 walk-forward LightGBM。
  2. **为什么各腿必须使用不同的动量指标与缓冲宽度？**
     - **`QQQ` 腿（`50%` 权重，2 只股票各 `25%`）**：Nasdaq-100 高弹性成长股用 **`12-1 Sharpe`（风险调整动量）+ `Buy 2 / Hold <= 5`** 能显著过滤妖股暴涨暴跌并降低换手损耗。
     - **`Tech` 腿（`25%` 权重，S&P 500 IT）**：科技龙头具有极强的赢家通吃效应，测试证明 **`12-1 Raw` + `Hard Top-1 (Hold <= 1，无缓冲)`** 显著优于带缓冲的 `Hold <= 3`（科技股一旦失去第 1 名，缓冲持有第 2–3 名反而拖累收益）。
     - **`SPY` 腿（`25%` 权重，S&P 500 全市场）**：用 **`12-1 Raw` + `Buy 1 / Hold <= 3`**，在科技主升浪时能与 `Tech`/`QQQ` 形成双倍/三倍天然共振（如 `NVDA`、`PLTR`），在宏观风格切换时又能捕捉非科技领头羊（如 2022 年能源股 `DVN`、`EQT`）。
  3. **无杠杆基础三腿组合（`Ctrl_3S_G1_1k`）独立复现表现**：
     - 213 个月（`2009-01 .. 2026-09`）CAGR **`50.20%`**，Sharpe **`1.300`**，日频 MaxDD **`-40.19%`**，2022 年收益 **`+8.13%`**（Clean-room 213/213 个月 `100%` 对齐）。

### 阶段 3：宏观状态切换层（`FOMC SEP = ON` vs `SEP = OFF`）（2026-11-03 至 11-04）
- **审计报告**：
  - `outputs/core3_qqq_spy_g1_audit_20261103/CORE3_QQQ_SPY_G1_AUDIT_REPORT.md`
  - `outputs/core3_structural_blindspots_audit_20261103/CORE3_STRUCTURAL_BLINDSPOTS_AUDIT_REPORT.md`
- **关键实证结论**：
  - 利用 ALFRED 历史真实发布时点的美联储 FOMC 经济预测摘要（SEP）利率路径信号，将 213 个月划分为 **`SEP = ON`（180 个月）** 与 **`SEP = OFF`（33 个紧缩月，含 2022 全年及 2026 下半年）**。
  - 当 **`SEP = OFF`** 时，高估值 `QQQ` 腿是主要回撤来源；将 `QQQ` 的 `50%` 切换为 **`25% Ex-IT BestSec（非科技最强板块第 1 名）+ 25% SGOV（短债现金）`**（即 `3L_3e_BestSec_1x`）：
    - 213M CAGR 从 `50.20%` 提升至 **`54.28%`**，Sharpe 从 `1.300` 提升至 **`1.395`**；
    - 历史日频 MaxDD 从 `-40.19%` 收窄至 **`-34.63%`**；
    - **2022 年大熊市收益从 `+8.13%` 暴增至 `+39.69%`**；
    - **2026 年实盘最大日频回撤从 `-47.90%` 大幅降至 `-26.98%`**。
- **被证伪方向（已放弃）**：
  - 个股止损线 / 均线技术刹车（`outputs/core3_tech_risk_controls_20261103/`）：对动量龙头加硬止损或 MA50/MA200 过滤会被频繁震出主升浪，净降 CAGR 且不改善日频核心回撤。

### 阶段 4：共振温和加杠杆（`Gate V1`）与外部审计 8 项强制修复（2026-11-04）
- **审计报告**：
  - `outputs/consensus_burst_mode_audit_20261104/CONSENSUS_BURST_MODE_AUDIT_REPORT.md`
  - `outputs/remediation_full_audit_20261104/FULL_8POINT_REMEDIATION_AUDIT_REPORT.md`
  - 独立验证脚本：`outputs/remediation_full_audit_20261104/run_full_8point_remediation_audit.py`
- **关键实证结论**：
  1. **全部 8 项外部审计问题 100% 修复并通过零共享代码验证**：
     - 重建纯 PIT GICS 4/6/8 位子行业映射（100% 剔除混入 IT 分母的非 IT 纳指股票、修复 `LSI` 代码重用、`Q` 2010 Qwest vs 2025 Qnity 拆分、`TGNA->GCI` 2015 前假板块、`FSLR/LDOS/XRX` 转板日期）；
     - 彻底移除选股时的 `hold_ret.notna()` 过滤（证明对 213 个月 Top-1/Top-2 选股影响为 **0**）；
     - 将理想化 `DGS3MO/12` 替换为真实 Tiingo `SGOV / BIL` 开盘到开盘收益 + `10 bp/side` 换手成本，并完成 `+50bp .. +600bp` 融资利差压力测试。
  2. **为什么选择 `75%/25%` 双股分散的 `1.35x`（或 `1.50x`）而非 `1.75x 100%` 单股集中（`ExpABC_3b`）？**
     - 隔夜跳空与券商强平压力测试（`05b_overnight_gap_and_forced_liquidation_stress.csv`）证明：
       - `1.75x 100% 单股`（单股敞口 `175%`）在遇到 `-38.8%` 隔夜暴雷跳空时会跌破券商 `30%` 维持保证金线触发强平；
       - **`1.35x 75/25 双股`（`BestSec_ModBurst_135_75_25_GateV1`，主股最高 `101.25%` + 副股 `33.75%`）**：历史最低日频保证金率 **`MinMER = 70.6%`**，即使主股隔夜暴跌 **`-57%`** 也绝不触发 `30%` 强平线！
       - **`1.50x 75/25 双股`（`BestSec_Prudent_150_75_25_GateV1`，主股最高 `112.5%` + 副股 `37.5%`）**：历史最低日频保证金率 **`MinMER = 62.2%`**，即使主股隔夜暴跌 **`-50%`** 仍保持 `40.7%` 保证金率（零强平）。

### 阶段 5：2026 年 10 月实盘回撤解剖与 `SEP = OFF` 路线 A1 去重（2026-11-04）
- **审计报告**：
  - `outputs/sep_off_overlap_cap_audit_20261104/SEP_OFF_OVERLAP_CAP_AUDIT_REPORT.md`
  - 脚本：`outputs/sep_off_overlap_cap_audit_20261104/run_sep_off_overlap_cap_audit.py`
- **问题起源**：
  - 在 `2026-10`（`SEP = OFF`），原版策略在 `Tech` 腿和 `SPY` 腿同时选中了 `SNDK`（造成 `50% SNDK + 25% VLO + 25% SGOV`），当月 `SNDK` 回调导致组合单月亏损 `-11.72%`。
- **关键结构性发现（`01_sep_on_vs_off_overlap_diagnostic.csv`）**：
  - 将 213 个月按 **`SEP = ON` vs `SEP = OFF`** 与 **跨腿重叠 vs 不重叠** 四象限拆解：
    - **`SEP = ON` 时跨腿重叠（107 个月）**：年化复合收益高达 **`+119.53%`**（胜率 `74.8%`），是整个策略的第一 Alpha 引擎！如果在 `SEP = ON` 时限制单股重叠上限（如全天候 `Cap <= 25%`），CAGR 会暴跌 **`-20.0 pp`**（从 `50.2%` 跌至 `30.3%`）！
    - **`SEP = OFF` 时跨腿重叠（18 个月）**：年化复合收益仅为 **`-2.62%`**（含 2026 年 10 月为 **`-13.85%`**），重叠不仅不产生正 Alpha，反而制造了 `2021-10 MRNA`、`2024-07 NVDA`、`2026-10 SNDK` 的单股集中回撤！
- **路线 A1 规则确立**：
  - **严格仅在 `SEP = OFF` 且 `Tech == SPY`（两腿选中同一只 IT 股）时去重**：保留 `25% Tech`，将 `SPY` 的 `25%` 改买 **`Ex-IT Raw`**（形成 `25% Tech + 25% Ex-IT Raw + 25% Ex-IT BestSec + 25% SGOV`），既 100% 保留了 `SEP = ON` 的共识爆发力，又消除了 `SEP = OFF` 下的 `50%` 科技单股重叠。

### 阶段 6：破解 `Hold-3` 缓冲老化陷阱（`APP` 与 `EQT`）→ `板块相对强弱过滤 RS_sec >= -5.0%`（`A1-RS`）（2026-11-04）
- **独立复现脚本**：`outputs/sep_off_overlap_cap_audit_20261104/step_6902_audit.py`
- **问题起源**：
  - 在路线 A1 下，`2026-10` 的 `Ex-IT Raw` 腿因为 `Hold <= 3` 缓冲规则，继续持有了退居第 2 名的老持仓 `APP`（当月跌 `-8.7%`），而错过了当月刚升至第 1 名的 `WBD`（当月暴涨 **`+24.6%`**）！
  - 为什么 `APP` 在 `2026-09-30` 换月时已经明显走弱却没被换掉？因为 `APP` 在 9 月单月下跌 `-7.8%`，跑输其所属板块等权收益达 **`-11.2%`**，但它的 12-1 累计动量仍排在第 2 名（`Rank = 2 <= 3`）。同样的一幕也发生在 `2022-12` 的老天然气股 `EQT`（退居第 2–3 名且大幅跑输能源板块，随后在 12 月大跌 `-20%`）。
- **解决方案与实证验证（`A1-RS`）**：
  - 对所有使用 `Hold <= 3` 缓冲的选股腿（`SPY`、`Ex-IT Raw`、`Ex-IT BestSec`）增加一条极简的**缓冲位健康度过滤**：
    - 当老持仓仍为 `Rank 1` 时无条件持有；
    - 当老持仓退居缓冲位 `Rank in {2, 3}` 时，检查其最近 1 个月相对所属 GICS 板块等权收益 $\text{RS}_{\text{sec}} = r_{1\text{M},\text{stock}}(t) - r_{1\text{M},\text{sector}}(t)$：若 $\text{RS}_{\text{sec}} < -5.0\%$，说明该老龙头相对本板块已显著失速，立即取消缓冲并换入新 `Rank 1`！
  - **效果**：
    - `2026-10` 自动将失速的 `APP`（$\text{RS}_{\text{sec}} = -11.2\%$）换入新第 1 名 `WBD`（`+24.6%`），使 **2026 年 10 月实盘收益从 `-11.72%` 直接逆转为正收益 `+1.16%`**（单月挽回 **`+12.88 pp`**）！
    - 214M CAGR 从原版 `60.96%` 提升至 **`62.28%`**，Sharpe 从 `1.414` 提升至 **`1.435`**，2026 实盘日频最大回撤从 `-26.98%` 改善至 **`-25.88%`**，且多重检验 DSR（`N = 1,112`）达 **`0.9998`**。

### 阶段 7：中期选举政体翻转（`Unified → Divided`）与 `V3 Election Reset`（2026-11-04 至 11-05）
- **独立复现脚本**：
  - [`independent_a1_rs_election_reset_audit.py`](./independent_a1_rs_election_reset_audit.py)
  - [`outputs/sep_off_overlap_cap_audit_20261104/step_6975_audit.py`](./outputs/sep_off_overlap_cap_audit_20261104/step_6975_audit.py)
  - [`outputs/sep_off_overlap_cap_audit_20261104/step_6983_audit.py`](./outputs/sep_off_overlap_cap_audit_20261104/step_6983_audit.py)
- **问题起源与实证解剖**：
  - 检验 2009–2026 全部 4 次美国中期选举（`2010`、`2014`、`2018`、`2022`）与 4 次总统大选（`2012`、`2016`、`2020`、`2024`）发现：
    - 凡是中期选举发生 **`Unified Government → Divided Government`（统一政府翻盘为分裂政府：2010 奥巴马丢众院、2018 特朗普丢众院、2022 拜登丢众院）**，选后第一个完整月（**大选年 12 月**）动量策略 **100% 出现显著亏损（`-7.4%`、`-8.5%`、`-10.5%`）**；
    - 相反，未发生政体翻转的 **2014 年中期选举（`Divided → Divided` 安慰剂对照）** 12 月大涨 **`+5.83%`**，总统大选年 12 月（2012 `+9.52%`、2016 `+23.28%`、2020 `+7.16%`）也多数大涨。
  - **为什么“躲 2–3 个月（`V7 / V8`）”是错的，而“只躲 12 月 + 12 月底清空缓冲（`V3`）”最优？**
    - 在全部 3 次 `Unified → Divided` 翻盘周期中，旧政策动量的均值回归踩踏**全部集中在 12 月一个月内释放完毕**，而**次年 1 月（`2011-01`、`2019-01`、`2023-01`）无一例外是新政体周期领头羊的暴利主升浪起点（`+13.7%`、`+19.9%`、`+5.9%`）**！
    - 如果躲 2–3 个月（`V7 / V8`），会白白踏空次年 1 月的主升浪，导致 CAGR 反而倒退 `-0.6 pp`；
    - 而在 **12 月底清空 `Hold-3 / Hold-5` 缓冲记忆（`held = []`）**，能让 `QQQ` 腿在 `2011-01` 甩掉退居第 5 名的旧股 `ILMN`、直接满仓切入新第 1 名 `NFLX`（使 `2011-01` 单月收益从 `+7.9%` 跃升至 **`+13.7%`**），并与 `A1-RS` 在 `2023-01`（切入 `OXY / FSLR`，`+5.9%`）形成完美机制共振！

#### `A1-RS 1.35x` 面板下 `V0–V8` 全部 9 种 Election Reset 变体完整回测表

| 变体编号与规则说明（仅在中期选举 `Unified → Divided` 时触发：2010、2018、2022） | 213M CAGR<br>*(至26/09)* | **214M CAGR**<br>*(含26/10)* | Sharpe<br>*(213M / 214M)* | 月频 MaxDD | 三次翻盘 12月<br>`[10 / 18 / 22]` | 三次翻盘次年 1月<br>`[11 / 19 / 23]` | 结论 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`V0`. 不躲、不重置（`A1-RS 1.35x` 基准）** | 62.84% | 62.28% | 1.444 / 1.435 | -22.74% | `[-7.4%, -8.5%, -10.5%]` | `[+7.9%, +20.0%, +5.9%]` | 基准 |
| **`V1`. 仅 12月底 Reset 缓冲（12月不躲）** | 63.11% | 62.55% | 1.447 / 1.439 | -22.74% | `[-7.4%, -8.5%, -10.5%]` | `[+13.7%, +20.0%, +5.9%]` | 验证 1月 Reset 单独有效 (`+0.27pp`) |
| **`V2`. 只躲 12月 `100% SGOV`（12月底不重置缓冲）** | 65.26% | 64.68% | 1.496 / 1.487 | -22.74% | `[-0.2%, -0.0%, +0.2%]` | `[+7.8%, +19.9%, +5.8%]` | 验证 12月避险单独贡献 (`+2.42pp`) |
| **`V3`. 标准版：12月 `100% SGOV` + 12月底 Reset 缓冲** 🏆 | **65.54%** | **64.95%** | **1.498 / 1.489** | **-22.74%** | **`[-0.2%, -0.0%, +0.2%]`** | **`[+13.7%, +19.9%, +5.9%]`** | **当前冻结版 (`+2.70pp` CAGR)** |
| **`V4`. 半仓版：12月 `50% SGOV` + 12月底 Reset 缓冲** | 64.43% | 63.85% | 1.475 / 1.466 | -22.74% | `[-3.8%, -4.3%, -5.1%]` | `[+13.7%, +19.9%, +5.9%]` | 稳健备选 (`+1.59pp` CAGR) |
| **`V5`. 12月强制 `SEP=OFF` 防守 + 12月底 Reset 缓冲** | 63.70% | 63.13% | 1.458 / 1.450 | -22.74% | `[-3.0%, -8.0%, -10.5%]` | `[+13.7%, +19.9%, +5.9%]` | 18/22年12月已处于 `SEP=OFF` |
| **`V6`. 12月仅去杠杆 (`1.0x`) + 12月底 Reset 缓冲** | 63.26% | 62.69% | 1.449 / 1.441 | -22.74% | `[-6.8%, -7.8%, -10.5%]` | `[+13.7%, +20.0%, +5.9%]` | 仅去杠杆不足以规避正股下跌 |
| **`V7`. 躲 12月+1月（2个月 `SGOV` + 1月底 Reset）** | 62.22% | 61.66% | 1.446 / 1.438 | -22.74% | `[-0.2%, -0.0%, +0.2%]` | `[+0.0%, +0.2%, +0.4%]` | ❌ 踏空 1月主升浪 (`-0.62pp`) |
| **`V8`. 躲 12月+1月+2月（3个月 `SGOV`）** | 62.17% | 61.61% | 1.445 / 1.437 | -22.74% | `[-0.2%, -0.0%, +0.2%]` | `[+0.0%, +0.2%, +0.4%]` | ❌ 踏空 1–2月主升浪 (`-0.67pp`) |

### 阶段 8：从三腿打补丁（V3）到第一性原理极简对称双核（`V4 Latest: Symmetric_Sharpe_Top2_V4`）（2026-11-13）
- **独立复现脚本与台账**：
  - [`independent_v4_symmetric_sharpe_top2_audit.py`](./independent_v4_symmetric_sharpe_top2_audit.py)
  - [`outputs/v4_symmetric_sharpe_top2_20261113/`](./outputs/v4_symmetric_sharpe_top2_20261113/)
- **问题起源与第一性原理解剖**：
  1. **顺风期（`SEP = ON`，180 个月）为什么不需要 `Tech + SPY` 两条辅助腿？**
     - 纯 **`QQQ Top-2`（`50% + 50%`，`12-1 Sharpe`，`Buy Top-2 / Hold <= 5`）** 在 180 个 `SEP = ON` 顺风月里的年化收益高达 **`67.77%`**（高于三腿 `1.0x` 的 `60.61%`），104 笔完整交易胜率 **`69.23%`**，平均盈亏比 **`4.49 : 1`**，盈亏总额比（Profit Factor）高达 **`10.10`**。
     - 双槽位（`Top-2`）不仅在 2010 年后的所有滚动窗口（`2011–2026`、`2012–2026`、`2018–2026`、`2020–2026`）全部跑赢单槽位 `Top-1`，而且完美消除了 `Top-1` 的“单槽位阻塞风险”（如 2020 年 `Top-1` 被 `DXCM` 占坑全年仅赚 `+1.63%`，而 `Top-2` 用第 2 槽位捕获 `TSLA` 全年大赚 **`+172.68%`**）。
  2. **逆风期（`SEP = OFF`，34 个紧缩月）`QQQ` 表现如何？该如何对称切换？**
     - 在 34 个 `SEP = OFF` 紧缩月里，纯 `QQQ Top-2` 累计亏损 **`-45.13%`**（年化 **`-19.61%`**，单笔交易胜率跌至 **`24.00%`**），证明紧缩期必须切出 `QQQ`。
     - **Apple-to-Apple 严格固定股数与缓冲对比（`12-1 Raw` vs `12-1 Sharpe`）**：
       - 在全市场非科技池（`Ex-IT` 约 400 只股票，跨 10 个周期属性截然不同的行业）直接按 `12-1 Sharpe` 选股，会被公用事业/必需消费等低波慢牛股骗走排名（年化仅 `51.80%`）；
       - 但如果**第一步先在 10 个非科技板块间按等权 `12-1 Raw` 选出最强顺风行业 `#1 BestSec`（保证行业爆发力），第二步在该行业内部按 `12-1 Sharpe` 选出前 2 名股票 `Buy Top-2 / Hold <= 5`（或 `Hold <= 3`）并配 `50% SGOV`**，则同行业内部比较波动率完全公平，直接剔除了高波动妖股！
       - 结果：逆风期单笔交易胜率从 `Ex-IT Raw` 的 `53.33%` 跃升至 **`75.00%`（`Hold <= 5`）– `79.17%`（`Hold <= 3`）**，无需任何跨腿去重补丁（Route A1）或 `-5.0%` 板块相对强弱补丁（RS_sec），全周期无杠杆 `1.0x` 214M CAGR 达 **`59.65%`–`59.74%`**（Sharpe **`1.426`–`1.429`**），叠加 `V3 Election Reset` 达 **`60.78%`**（Sharpe **`1.445`**）！

#### `V4 Latest (Symmetric_Sharpe_Top2_V4)` 完整业绩与交易胜率汇总表（无杠杆 `1.0x`，2009-01 至 2026-10）

| 策略变体（无杠杆 `1.0x`，含双边 `10bp` 换手成本） | `2009–2025` CAGR<br>*(17年完整年)* | **214M 全周期 CAGR**<br>*(含26年10月)* | **214M Sharpe** | 月频 MaxDD | **历史日频 MaxDD** | **2026 实盘日频 MaxDD** | **全周期逐笔胜率**<br>*(逆风期 BestSec 胜率)* | **平均盈亏比**<br>*(Profit Factor)* |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1. `V4 对称核心版 (Hold <= 5, V0)`** 🏆 | **50.38%** | **59.65%** | **1.426** | **-27.99%** | **-37.32%** | **-18.88%** | **70.16%** (`87/124`)<br>*(逆风期 **75.00%** `15/20`)* | **3.99 : 1**<br>*(PF = **9.39**)* |
| **2. `V4 逆风紧缓冲版 (BestSec Hold <= 3, V0)`** | **50.93%** | **59.74%** | **1.429** | **-27.99%** | **-37.32%** | **-18.88%** | **71.09%** (`91/128`)<br>*(逆风期 **79.17%** `19/24`)* | **3.86 : 1**<br>*(PF = **9.50**)* |
| **3. `V4 + V3 Election Reset (Hold <= 5)`** | **51.49%** | **60.78%** | **1.444** | **-27.99%** | **-37.32%** | **-18.88%** | **68.50%** (`87/127`)<br>*(逆风期 **75.00%** `15/20`)* | **4.02 : 1**<br>*(PF = **8.75**)* |
| **4. `V4 + V3 Election Reset (Hold <= 3)`** | **51.92%** | **60.74%** | **1.445** | **-27.99%** | **-37.32%** | **-18.88%** | **69.47%** (`91/131`)<br>*(逆风期 **79.17%** `19/24`)* | **3.89 : 1**<br>*(PF = **8.85**)* |

---

## 六、 全部关键回测审计报告与可复现脚本索引（供新对话直接调用）

| 阶段 / 主题 | 核心审计报告 (`.md`) | 零共享代码 / 复现脚本 (`.py`) 与关键结果表 (`.csv`) |
| :--- | :--- | :--- |
| **0. 最新冻结 V4 极简对称版 (`Symmetric_Sharpe_Top2_V4`)** | [`FROZEN_STRATEGY_SPEC.md`](./FROZEN_STRATEGY_SPEC.md) | [`independent_v4_symmetric_sharpe_top2_audit.py`](./independent_v4_symmetric_sharpe_top2_audit.py)<br>[`v4_symmetric_sharpe_top2_h5_v0_214m_ledger.csv`](./outputs/v4_symmetric_sharpe_top2_20261113/v4_symmetric_sharpe_top2_h5_v0_214m_ledger.csv)<br>[`v4_symmetric_sharpe_top2_h5_v3_214m_ledger.csv`](./outputs/v4_symmetric_sharpe_top2_20261113/v4_symmetric_sharpe_top2_h5_v3_214m_ledger.csv)<br>[`v4_symmetric_sharpe_top2_h5_v0_trades.csv`](./outputs/v4_symmetric_sharpe_top2_20261113/v4_symmetric_sharpe_top2_h5_v0_trades.csv) |
| **1. 三腿杠杆冻结版 (`A1-RS + V3 Election Reset`)** | [`FROZEN_STRATEGY_SPEC.md`](./FROZEN_STRATEGY_SPEC.md)<br>[`outputs/sep_off_overlap_cap_audit_20261104/FROZEN_A1_RS_V3_ELECTION_RESET_SPEC.md`](./outputs/sep_off_overlap_cap_audit_20261104/FROZEN_A1_RS_V3_ELECTION_RESET_SPEC.md) | [`independent_a1_rs_election_reset_audit.py`](./independent_a1_rs_election_reset_audit.py)<br>[`outputs/sep_off_overlap_cap_audit_20261104/step_6902_audit.py`](./outputs/sep_off_overlap_cap_audit_20261104/step_6902_audit.py)<br>[`outputs/sep_off_overlap_cap_audit_20261104/step_6983_audit.py`](./outputs/sep_off_overlap_cap_audit_20261104/step_6983_audit.py) |
| **2. `SEP = OFF` 重叠去重审计 (Route A1)** | [`outputs/sep_off_overlap_cap_audit_20261104/SEP_OFF_OVERLAP_CAP_AUDIT_REPORT.md`](./outputs/sep_off_overlap_cap_audit_20261104/SEP_OFF_OVERLAP_CAP_AUDIT_REPORT.md) | [`outputs/sep_off_overlap_cap_audit_20261104/run_sep_off_overlap_cap_audit.py`](./outputs/sep_off_overlap_cap_audit_20261104/run_sep_off_overlap_cap_audit.py)<br>[`01_sep_on_vs_off_overlap_diagnostic.csv`](./outputs/sep_off_overlap_cap_audit_20261104/01_sep_on_vs_off_overlap_diagnostic.csv)<br>[`03_sep_off_overlap_cap_backtest.csv`](./outputs/sep_off_overlap_cap_audit_20261104/03_sep_off_overlap_cap_backtest.csv) |
| **3. 外部审计 8 项强制修复与保证金压力测试** | [`outputs/remediation_full_audit_20261104/FULL_8POINT_REMEDIATION_AUDIT_REPORT.md`](./outputs/remediation_full_audit_20261104/FULL_8POINT_REMEDIATION_AUDIT_REPORT.md) | [`outputs/remediation_full_audit_20261104/run_full_8point_remediation_audit.py`](./outputs/remediation_full_audit_20261104/run_full_8point_remediation_audit.py)<br>[`04_zero_shared_code_gate_v1_v2_summary.csv`](./outputs/remediation_full_audit_20261104/04_zero_shared_code_gate_v1_v2_summary.csv)<br>[`05b_overnight_gap_and_forced_liquidation_stress.csv`](./outputs/remediation_full_audit_20261104/05b_overnight_gap_and_forced_liquidation_stress.csv) |
| **4. 零共享代码独立引擎 (`ind_engine.py`)** | [`outputs/two_leg_independent_audit_20261103/TWO_LEG_INDEPENDENT_AUDIT_REPORT.md`](./outputs/two_leg_independent_audit_20261103/TWO_LEG_INDEPENDENT_AUDIT_REPORT.md) | [`outputs/expabc_independent_audit_20261104/ind_engine.py`](./outputs/expabc_independent_audit_20261104/ind_engine.py)<br>[`outputs/two_leg_independent_audit_20261103/ind_engine.py`](./outputs/two_leg_independent_audit_20261103/ind_engine.py) |
| **5. 共识爆发模式与 `Gate V1` 杠杆审计** | [`outputs/consensus_burst_mode_audit_20261104/CONSENSUS_BURST_MODE_AUDIT_REPORT.md`](./outputs/consensus_burst_mode_audit_20261104/CONSENSUS_BURST_MODE_AUDIT_REPORT.md) | [`outputs/consensus_burst_mode_audit_20261104/run_consensus_burst_audit.py`](./outputs/consensus_burst_mode_audit_20261104/run_consensus_burst_audit.py)<br>[`outputs/consensus_burst_mode_audit_20261104/run_four_experiments_abcd.py`](./outputs/consensus_burst_mode_audit_20261104/run_four_experiments_abcd.py) |
| **6. 三腿架构与 `SEP` 宏观路由审计** | [`outputs/core3_qqq_spy_g1_audit_20261103/CORE3_QQQ_SPY_G1_AUDIT_REPORT.md`](./outputs/core3_qqq_spy_g1_audit_20261103/CORE3_QQQ_SPY_G1_AUDIT_REPORT.md)<br>[`outputs/core3_structural_blindspots_audit_20261103/CORE3_STRUCTURAL_BLINDSPOTS_AUDIT_REPORT.md`](./outputs/core3_structural_blindspots_audit_20261103/CORE3_STRUCTURAL_BLINDSPOTS_AUDIT_REPORT.md) | [`outputs/core3_qqq_spy_g1_audit_20261103/run_qqq_spy_g1_audit.py`](./outputs/core3_qqq_spy_g1_audit_20261103/run_qqq_spy_g1_audit.py)<br>[`outputs/core3_structural_blindspots_audit_20261103/run_structural_blindspots_audit.py`](./outputs/core3_structural_blindspots_audit_20261103/run_structural_blindspots_audit.py) |
| **7. 各腿选股假设、技术止损证伪与 Clean-Room 审计** | [`outputs/core3_stock_selection_audit_20261103/CORE3_STOCK_SELECTION_AUDIT_REPORT.md`](./outputs/core3_stock_selection_audit_20261103/CORE3_STOCK_SELECTION_AUDIT_REPORT.md)<br>[`outputs/core3_tech_risk_controls_20261103/CORE3_TECHNICAL_BRAKES_AUDIT_REPORT.md`](./outputs/core3_tech_risk_controls_20261103/CORE3_TECHNICAL_BRAKES_AUDIT_REPORT.md)<br>[`outputs/qqq_mom_top3_claude_audit_20261103/CLAUDE_CLEANROOM_AUDIT_REPORT.md`](./outputs/qqq_mom_top3_claude_audit_20261103/CLAUDE_CLEANROOM_AUDIT_REPORT.md)<br>[`outputs/tech_top1_independent_audit_20261103/CLAUDE_INDEPENDENT_AUDIT_REPORT.md`](./outputs/tech_top1_independent_audit_20261103/CLAUDE_INDEPENDENT_AUDIT_REPORT.md) | [`outputs/core3_stock_selection_audit_20261103/run_selection_hypotheses_audit.py`](./outputs/core3_stock_selection_audit_20261103/run_selection_hypotheses_audit.py)<br>[`outputs/core3_tech_risk_controls_20261103/run_tech_brakes_audit.py`](./outputs/core3_tech_risk_controls_20261103/run_tech_brakes_audit.py) |
