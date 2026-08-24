# M0 Contract v0.8.1 — Frozen Signal & Data Engineering Specification

**Version**: 0.8.1 (Canonical Frozen Specification)
**Status**: FROZEN SPECIFICATION; STAGE A PASS; STAGE B IMPLEMENTED UNDER CODEX RE-AUDIT; STAGE C NOT STARTED
**Sample Period**: 2013Q3–2026Q1, World B
**Role**: Baseline Diagnostic Model ($\Delta\text{Shares}$)
**Official Title**: *“M0 Signal Performance in the OpenFIGI-Mapped, yfinance-Price-Covered, Frozen-Vendor-Ledger-Adjusted US Equity Subset (2013Q3–2026Q1, World B)”*

---

## 1. 核心定位与研究目标

M0 是 Smart Money 13F 研究体系中最基础、最质朴的基准模型（Baseline Diagnostic）。它衡量机构在剔除一切主观加权、选股能力过滤和拥挤度调整后，纯粹由季度持股变动（$\Delta\text{Shares}$）所传递的信息含量。

### 1.1 核心诊断问题
> **“在可被公开市场行情成功覆盖的股票样本子集中，最原始的机构整体股数买卖信号是否具备统计上显著异于零的预测能力？”**

### 1.2 预注册假说层级 (Preregistration Hierarchy)
- **$\text{IC}(\text{M0}) \ne 0$**：仅作为**数据地基基准诊断（Baseline Diagnostic）**，非正式 Alpha 策略假说。
- **Primary Hypothesis A (正式主检验 A)**：$\text{IC}(\text{M4}) > \text{IC}(\text{M0})$（全样本 2013Q3–2026Q1，World B，待 M4 构建完成后检验）。
- **Primary Hypothesis B (正式主检验 B)**：$\text{IC}(\text{M5}) > \text{IC}(\text{M4})$（2021Q3–2026Q1 对照期，待 M5 构建完成后检验）。

---

## 2. World B 状态与交易时间窗口

### 2.1 Point-in-Time (PIT) 状态重构与时区日历比对
所有持仓状态必须严格符合 World B（Fixed-PIT）定义：
```text
Holdings State = reconstruct_origin_filer_state()
                 仅使用 acceptance_datetime 对应美东日历日期 <= compute_13f_deadline(period_of_report) 的有效申报
```
- **PIT 判定规则**：必须将 SEC 接收时间戳转换为美国东部时间（`America/New_York`）对应的日历日期，与计算出的申报截止日日历日期进行比较：
  $$\text{acceptance\_date}_{\text{America/New\_York}} \le \text{compute\_13f\_deadline}(Q)$$

### 2.2 13F 申报截止日计算日历 (SEC Rule 0-3)
SEC 规定 13F 申报截止日为季度结束后第 45 个自然日。若该日落入周末或 SEC 联邦法定节假日，顺延至下一个工作日：
```python
def compute_13f_deadline(period_of_report: str) -> str:
    # 基础 45 天
    # 遇周末 / 联邦假期（如 Presidents' Day）严格顺延至下一个交易日
    # 例：2025-12-31 截止日顺延至 2026-02-17
```

### 2.3 交易执行与持仓窗口
- **进场交易日 ($T_{\text{entry}}$)**：官方截止日后的下一个合法交易所开盘时点：
  $$T_{\text{entry}} = \text{exchange\_next\_open}(\text{compute\_13f\_deadline}(Q))$$
- **出场交易日 ($T_{\text{exit}}$)**：下一季度官方截止日后的下一个合法交易所开盘时点：
  $$T_{\text{exit}} = \text{exchange\_next\_open}(\text{compute\_13f\_deadline}(Q_{\text{next}}))$$
- **收益窗口**：严格限定为开盘至开盘前向全收益率（Open-to-Open Total Return），严禁在后验中挑选 Close、20 日、60 日等窗口。

---

## 3. 规范 M0 申报状态机与所有权作用域

严禁盲目套用 Phase 0 的 `reconstruct_state()`（其按 `(cusip, investment_discretion)` 聚合且丢失了所有权作用域）。M0 必须执行规范的单机构状态机重构：

### 3.1 所有权标识解析
每一条原始持仓明细强制解析双重身份：
- `origin_filer_cik`：提交该份 13F 的实际申报人 CIK；
- `economic_owner_cik`：
  - 若 `other_manager` 序列号成功在 `OTHERMANAGER.tsv` 中解析为相关 CIK，则赋值为该 `related_cik`；
  - 若 `other_manager` 为空，则赋值为 `origin_filer_cik`；
  - 若 `other_manager` 包含无法解析的未知序列号，标记 `ownership_unresolved = True`，`economic_owner_cik = None`。

### 3.2 Accession 内四元组聚合
在每个 accession 内部，先按 `(accession_number, cusip, asset_class, economic_owner_cik)` 聚合，并保留完整投票权与市值签名：
```python
key = (row.accession_number, row.cusip, row.asset_class, row.economic_owner_cik)
# 汇总字段: total_shares, total_value_usd, total_vote_sole, total_vote_shared, total_vote_none
```
`ownership_unresolved = True` 的记录单独隔离，从 Primary M0 排除。

### 3.3 规范 M0 单申报人状态重构 (Per-Origin-Filer State Reconstruction)
针对每一个 `(origin_filer_cik, period_of_report)`，仅提取 `acceptance_date_eastern <= deadline(period_of_report)` 的申报，**严格按带时区的绝对时间戳 (UTC Instant ASC) 及 accession_number ASC 排序**执行确定性状态转移：
1. **校验输入一致性**：若同一批次内存在不一致的 `origin_filer_cik`，或明细行的 accession/filer/period 与父级申报不一致，立即报错阻断。
2. **初始状态**：`state = {}`（键为 `(cusip, asset_class, economic_owner_cik)`）。
3. **Original (`13F-HR`) 或 `RESTATEMENT`**：以该 accession 的聚合明细**完全替换（REPLACE）**当前申报人状态：
   $$state = \{ key: row \mid row \in \text{accession\_aggregated\_rows} \}$$
4. **`ADD_NEW_HOLDINGS`**：对该 accession 中出现的键执行**就地更新/插入（UPSERT，更新为新行，绝不在原股数上累加）**，未出现的键予以保留：
   $$\forall row \in \text{accession\_aggregated\_rows}: \quad state[key] = row$$
5. **`UNKNOWN` Amendment**：若出现无法识别 amendment 类型的申报，将该 `(origin_filer_cik, period_of_report)` 标记为 `amendment_unresolved = True`，**整体隔离并从 Primary M0 中排除**。

---

## 4. 严格分期 PIT 实体图与跨申报去重

在完成各申报人独立有效状态重构后，再执行实体图构建与跨申报去重：

### 4.1 实体非独立申报节点规则 (Related-Only Nodes)
- **定义**：`filing_members(t)` 为在第 $t$ 期实际提交了 World-B 有效 13F 申报的主申报人 CIK 集合。
- **规则**：在 `OTHERMANAGER` 关系中被引用的非独立申报顾问/分支机构仅作为连通图的边，**不作为 expected filing members**。

### 4.2 严格分期 PIT 实体图构建
1. $E(Q-1) = \{ (u, v) \mid \text{申报于 } Q-1, \text{acceptance\_date\_eastern} \le \text{deadline}(Q-1) \}$
2. $E(Q) = \{ (u, v) \mid \text{申报于 } Q, \text{acceptance\_date\_eastern} \le \text{deadline}(Q) \}$
3. 当期实体连通图：$G(Q-1, Q) = E(Q-1) \cup E(Q)$。
4. 连通分量内的确定性 Canonical Entity ID 取该分量内最小的 CIK 编号。

### 4.3 实体配对完整性门槛 (Entity Membership Eligibility)
对于任意实体连通分量与季度配对 $(Q-1, Q)$：
- **合格充要条件**：
  $$\text{filing_members}(Q-1) == \text{filing_members}(Q) \quad \text{且} \quad |\text{filing_members}(Q)| > 0$$
- **违规处置**：若出现独立申报成员变动或缺报，触发 `entity_membership_incomplete = True`，该实体在 $(Q-1, Q)$ 的所有 $\Delta\text{Shares}$ 统一标记为 `Missing`，**从 Primary M0 排除**。

### 4.4 跨申报经济签名严格去重 (Cross-Disclosure Dedup)
**去重作用域严格限定在同一 `canonical_entity_id` 内部，严禁跨不同实体连通分量合并**。在同一实体连通分量内，针对同一 `(cusip, period_of_report)`，折叠去重的**充要条件**为：
1. `canonical_entity_id` 完全相同；
2. `economic_owner_cik` 完全相同；
3. 完整经济签名完全一致：
   $$(\text{total\_shares}, \text{total\_value\_usd}, \text{total\_vote\_sole}, \text{total\_vote\_shared}, \text{total\_vote\_none})$$
若实体不同、所有权不同或任何一项签名要素不相等，必须作为独立持仓全部保留。

### 4.5 机密申报剔除门槛 (Confidential Omission Gate)
若实体在 $Q$ 或 $Q-1$ 包含任何标记为 `is_confidential_omit = True` 的申报记录，整个 entity-quarter 对直接从 Primary M0 排除；在敏感性分析中可选择性纳入。

---

## 5. 信号端前置输入：证券映射与冻结第三方拆股账本

以下三项属于**信号端静态前置输入**，必须在计算 $\Delta\text{Shares}$ 和生成 Signal Manifest 之前固化：

### 5.1 OpenFIGI 确定性证券身份决议瀑布
输入 9 位合规 CUSIP 与 SEC 发行人名称，按以下瀑布规则严格匹配：
1. **资产大类**：`marketSector == 'Equity'`；
2. **证券类型**：`securityType2 IN ('Common Stock', 'ADR', 'REIT', 'Tracking Stock', 'Units', 'Closed-End Fund')`；（**严禁纳入 ETF**）；
3. **交易所**：`exchCode IN ('US', 'UN', 'UQ', 'UR', 'UA')`；
4. **发行人名称校验**：Jaro-Winkler 相似度 $\ge 0.75$（发行人名称为空或无有效字符直接拒绝）；
5. **主键锁定**：
   - 首选 `shareClassFIGI`（若存在且非空）；
   - 次选 `compositeFIGI`（标记 `composite_fallback`）；
   - **严禁**使用交易所私有 venue-level `figi` 作为主身份。
6. **歧义处置**：若最高分候选者对应多个不同的 `shareClassFIGI` 或 `compositeFIGI`，直接判定为 `mapping_ambiguous` 并**拒绝决议（从 Primary 排除）**，严禁使用字母序强行平局决议。

### 5.2 冻结第三方拆股账本与 SEC 一手信源证据
- **数据源**：冻结 yfinance 厂商拆股元数据快照（仅含 Splits 日期与正实数比例，不包含任何历史价格 K 线）。
- **SEC 一手信源证据对账表**（证据快照必须保存原始字节、SHA-256 及抓取时间戳）：

| 标的 | CUSIP | 一手信源 (SEC 8-K Filing) | 拆股条款细节 | 冻结 URL |
|---|---|---|---|---|
| **NVDA** | `67066G104` | Form 8-K (Dated 2024-05-22) | 10-for-1, 股权登记日 2024-06-06, 派发日 2024-06-07, 除权交易日 2024-06-10 | [SEC 8-K](https://www.sec.gov/Archives/edgar/data/1045810/000104581024000113/nvda-20240522.htm) |
| **TSLA** | `88160R101` | Form 8-K (Dated 2022-08-05) | 3-for-1, 股权登记日 2022-08-17, 派发日 2022-08-24 收盘后, 除权交易日 2022-08-25 | [SEC 8-K](https://www.sec.gov/Archives/edgar/data/1318605/000156459022028207/tsla-8k_20220804.htm) |
| **AMZN** | `023135106` | Form 8-K (Dated 2022-03-09) | 20-for-1, 股权登记日 2022-05-27, 派发反映日约 2022-06-03, 除权交易日 2022-06-06 | [SEC 8-K](https://www.sec.gov/Archives/edgar/data/1018724/000101872422000009/amzn-20220309.htm) |
| **GOOGL** | `02079K305` | Form 8-K (Dated 2022-02-01) | 20-for-1, 股权登记日 2022-07-01, 派发日 2022-07-15 收盘后 (注: 申报文件本身未写明 2022-07-18 交易日，不将该日期归于此文件) | [SEC 8-K](https://www.sec.gov/Archives/edgar/data/1652044/000165204422000015/goog-20220201.htm) |

---

## 6. 公司行为与拆股有序瀑布门控 (Ordered Precedence Gates)

### 6.1 冻结有理数拆股因子集 $\mathcal{K}_{\text{rational}}$
$$\mathcal{K}_{\text{base}} = \left\{ 1.25\,(5:4), \; \frac{4}{3}\,(4:3), \; 1.50\,(3:2) \right\} \cup \left\{ k \in \mathbb{Z} \mid 2 \le k \le 100 \right\}$$
$$\mathcal{K}_{\text{rational}} = \mathcal{K}_{\text{base}} \cup \left\{ \frac{1}{x} \;\middle|\; x \in \mathcal{K}_{\text{base}} \right\} \quad (204\text{ 个确定性因子})$$

### 6.2 期间配对厂商拆股系数精确定义
对于任意季度配对 $(Q-1, Q)$：
$$K_{\text{ledger}}(Q-1, Q) = \prod_{e \in \mathcal{S}(Q-1, Q)} \text{ratio}(e)$$
其中 $\mathcal{S}(Q-1, Q) = \{ e \in \text{Frozen Vendor Splits} \mid \text{period\_of\_report}(Q-1) < \text{ex\_date}(e) \le \text{period\_of\_report}(Q) \}$。
- 所有 ratio 必须为正有限浮点数；若区间内无拆股事件，则 $K_{\text{ledger}} = 1.0$；
- 若发生多起拆股，系数累乘；反向合股系数为倒数（如 1:10 合股对应 $\text{ratio} = 0.1$）。
- 该系数严格用于将 $Q-1$ 股数换算为 $Q$ 股数单位：$\text{adjusted\_shares}(Q-1) = \text{raw\_shares}(Q-1) \times K_{\text{ledger}}$。

### 6.3 连续持有者持仓对数统计量与调整后中位数
对于标的 $S$ 在 $(Q-1, Q)$ 的 $N$ 家连续持有者（必须满足 $N == \text{len}(\text{valid\_positive\_ratios})$）：
$$r_i = \frac{\text{raw\_shares}_Q(i)}{\text{raw\_shares}_{Q-1}(i)}, \quad y_i = \ln(r_i)$$
$$\mu_{\text{log}} = \text{median}(\{y_i\}), \quad \tilde{r} = \exp(\mu_{\text{log}}), \quad \text{MAD}_{\text{log}} = \text{median}(\{|y_i - \mu_{\text{log}}|\})$$
$$\mu_{\text{adj\_log}} = \text{median}(\{\ln(r_i) - \ln(K_{\text{ledger}})\}) = \mu_{\text{log}} - \ln(K_{\text{ledger}})$$
$$\tilde{r}' = \exp(\mu_{\text{adj\_log}}) = \frac{\tilde{r}}{K_{\text{ledger}}}$$

### 6.4 严格有序瀑布执行流 (Ordered Waterfall Precedence)

```text
Gate 0: 身份/所有权/重大公司行为连续性门控
  ├── 命中 CUSIP-FIGI 身份中断 / 未解析所有权 / 非现金并购 / 承继不确定
  └── 结果: CORPORATE_ACTION_UNKNOWN -> Primary EXCLUDE (STOP)

Gate 1: 冻结厂商账本存在拆股记录 (Vendor Ledger Match, K_ledger != 1.0)
  ├── 分支 1.1: 样本不足 N < 20
  │     └── 结果: KNOWN_SPLIT_LOW_POWER -> Primary INCLUDE (应用账本系数, 标低功效) (STOP)
  └── 分支 1.2: 样本充足 N >= 20
        ├── 调整后中位数 r' in [0.8, 1.2]
        │     └── 结果: KNOWN_SPLIT_PASS -> Primary INCLUDE (应用账本系数) (STOP)
        └── 调整后中位数 r' not in [0.8, 1.2]
              └── 结果: KNOWN_SPLIT_MISMATCH -> Primary EXCLUDE (STOP)

Gate 2: 冻结厂商账本无拆股记录 (No Vendor Ledger Match, K_ledger == 1.0)
  ├── 分支 2.1: 样本不足 N < 20
  │     └── 结果: LEDGER_ONLY_LOW_POWER -> Primary INCLUDE (系数=1.0, 标低功效) (STOP)
  └── 分支 2.2: 样本充足 N >= 20
        ├── 中位数未命中任何 K in K_rational (相对误差 > 5%)
        │     └── 结果: CLEAN -> Primary INCLUDE (系数=1.0) (STOP)
        ├── 命中 K (相对误差 <= 5%) 且 MAD_log <= 0.15 (紧密聚类)
        │     └── 结果: SPLIT_UNKNOWN -> Primary EXCLUDE (严禁私自插补) (STOP)
        └── 命中 K (相对误差 <= 5%) 且 MAD_log > 0.15 (离散度大)
              └── 结果: SPLIT_AUDIT_AMBIGUOUS_HIGH_DISPERSION -> Primary EXCLUDE (STOP)
```

---

## 7. M0 信号构建与 3x 审查风险启发式权重

### 7.1 实体级变动计算
$$\Delta\text{Shares}(\text{entity}, \text{stock}, Q) = \text{adjusted\_shares}(Q) - \text{adjusted\_shares}(Q-1)$$

### 7.2 3x 审查风险启发式权重 (Conservative 3x Censor-Risk Heuristic)
SEC 法定豁免申报门槛为**同时满足股数 $< 10,000$ 且市值 $< \$200,000$**（17 CFR § 240.13f-1）。
我们在研究中采用**更保守的 3 倍审查风险启发式规则 (3x Censor-Risk Heuristic)**：
- `LOW_CONFIDENCE_NEW`：新建仓 且 ($\text{shares} < 30,000$ **或** $\text{value\_usd} < \$600,000$)；
- `LOW_CONFIDENCE_EXIT`：清仓 且 前期持仓 ($\text{shares} < 30,000$ **或** $\text{value\_usd} < \$600,000$)；
- 权重：若命中上述任一启发式标签，$\text{censor\_weight} = 0.3$；其余正常持仓 $\text{censor\_weight} = 1.0$。
- **状态一致性门控**：`NEW` 必须是“前期股数/市值均为 0、当期持仓为正”；`EXIT` 必须是“当期股数/市值均为 0、前期持仓为正”；两者均否时两期持仓必须都为正。任何旗标与持仓事实冲突的记录立即报错，不允许仅凭旗标创造交易。

### 7.3 股票级聚合公式与字段说明
$$\text{M0\_signal}(\text{stock}, Q) = \sum_{\text{eligible entities}} \left( \Delta\text{Shares}(\text{entity}, \text{stock}, Q) \times \text{censor\_weight} \right)$$
- **字段规范说明**：$\text{censor\_weight}$ 是在实体-持仓明细层面计算并直接乘以 $\Delta\text{Shares}$ 的求和输入项。聚合后的 `m0_signals` 表在 `(primary_stock_id, period_of_report)` 粒度上**不存在单一聚合权重列**。严禁在实现中伪造股票级的单一 `censor_weight` 标量列。

---

## 8. 收益计算细则与缺失结果冻结政策 (Missing-Outcome Policy)

### 8.1 前复权开盘价计算
基于 `auto_adjust=False, actions=True` 的冻结日频行情快照：
$$\text{adjusted\_open}(T) = \text{raw\_open}(T) \times \frac{\text{adj\_close}(T)}{\text{raw\_close}(T)}$$
必须验证输入价格为正有限实数，若出现零、负数、NaN 或 Inf，直接判定价格缺失。

### 8.2 Primary 严格单日规则与缺失处置
- **Primary 准则**：进出场价严格取指定交易日开盘价。若当日停牌无报价、价格为 NaN/Inf 或无法获取，收益直接置为 `None`（`is_outcome_missing = 1`）。
- **现金并购结算**：若持仓期内发生现金私有化退市，根据官方 SEC 8-K 对价现金结算出场；非现金并购或无法确定对价者置为 `None`（`is_outcome_missing = 1`, `CORPORATE_ACTION_UNKNOWN` 排除）。
- **Primary IC 排除**：任何收益为 `None`（缺失）的标的从当季 Primary IC 截面中排除，并在单次预注册 LEFT JOIN 表中完整保留该行及缺失状态。

### 8.3 强制敏感性分析矩阵 (Mandatory Sensitivities)
所有敏感性分析必须基于**同一张保留全量信号行的 LEFT JOIN 评估表**派生计算：
1. **$\text{Missing} = -100\%$ 压力测试**：所有缺失出场价的标的假设归零清算；
2. **$\text{Missing} = 0\%$ 压力测试**：所有缺失出场价的标的假设持平出场；
3. **$\le 5$ 日顺延对照**：允许停牌标的向后顺延最多 5 个交易日获取首个开盘价。5 日必须按独立交易所日历计数；股票因停牌而缺少行情行时，该交易所开市日仍消耗一个顺延名额，严禁按“存在报价的 5 行”滚到第 6 个或更晚交易日。

---

## 9. 统计检验与双分母全景覆盖率协议

### 9.1 截面有效性门槛
- **最小股票数量**：每个季度 IC 截面有效股票数必须 $\ge 100$；若 $< 100$，该季度标记 `INSUFFICIENT_STOCKS` 并从平均 IC 计算中排除（但在报表中完整披露）。
- **低覆盖率预警**：若 $\text{final\_IC\_eligible} < 70\%$，该季度标记 `LOW_COVERAGE`，但只要股票数 $\ge 100$，**必须计算并报告该季度 IC，严禁选择性删除**。

### 9.2 双分母覆盖率报告标准 (Dual-Denominator Reporting)
每个季度必须在收益评估之前披露以下两套分母下的完整分布：
- **分母 1 (D1: Raw SEC Scope)**：全量 World B 中有效 cash-equity (CUSIP, Quarter) 独立键总数；
  - 报告 OpenFIGI 映射率、价格覆盖率、机构数量穿透覆盖率、申报市值穿透覆盖率。
- **分母 2 (D2: Price-Covered Scope)**：成功完成映射且具备有效价格的 (primary_stock_id, Quarter) 独立键总数；
  - 报告 8 大状态各自的计数值及在分母 2 下的百分比。
  - 报告 D1 $\to$ D2 的转换损耗率与各环节排除明细。

---

## 10. 数据隔离、单向流转、基数不变量与变更检测清单

### 10.1 物理数据库与目录隔离
- **Phase 0 源数据库** (`research/smart_money/phase0/data/13f_full_4409f14.db`):
  - 作为底层只读存据，**必须以 SQLite 只读 URI 模式 (`file:{quote(path)}?mode=ro`) 打开，严禁执行写入**。
- **独立的运行环境目录**：每一次回测运行分配全局唯一 `run_id`，持久化于独立路径：
  - 信号端目录：`research/smart_money/m0/runs/<run_id>/signal/` (包含独立派生表 `m0_signal.db`)
  - 收益端目录：`research/smart_money/m0/runs/<run_id>/outcome/` (包含独立派生表 `m0_outcome.db`)
  - 路径解析必须使用真实路径（`realpath`）并阻断符号链接别名逃逸。

### 10.2 独立派生库 Schema 定义
- **信号库 `m0_signal.db`**:
  ```sql
  CREATE TABLE IF NOT EXISTS m0_signals (
      primary_stock_id TEXT NOT NULL,
      period_of_report TEXT NOT NULL,
      m0_signal REAL NOT NULL,
      PRIMARY KEY (primary_stock_id, period_of_report)
  );
  ```
- **收益库 `m0_outcome.db`**:
  ```sql
  CREATE TABLE IF NOT EXISTS m0_forward_returns (
      primary_stock_id TEXT NOT NULL,
      period_of_report TEXT NOT NULL,
      forward_return REAL,
      outcome_status TEXT NOT NULL,
      rolled_le_5_return REAL,
      PRIMARY KEY (primary_stock_id, period_of_report)
  );
  ```

### 10.3 SHA-256 变更检测清单与跨阶段密码学绑定 (Manifest Binding)
- **标准 JSON 序列化规范**：Manifest JSON 仅接受标准合规的字符串键与有限原始类型，`allow_nan=False`，严禁非标准 JSON 字段。
- **阶段绑定 (Stage Binding)**：Stage E 的 Price Manifest 必须显式绑定 Stage D 的 `signal_manifest_sha256`、`run_id`、`contract_sha256`、`source_git_sha` 及 `m0_code_git_sha`。Stage F 预注册评估前必须验证绑定完全一致。
- **权限防护说明**：文件系统的 `chmod 444` 设置仅作为**防止程序意外覆盖的只读权限防护**。真正的审计可信度依赖于 **Git Commit SHA 冻结、外部独立审查与归档存据**。
- **工作区 Clean Tree 铁律**：生产阶段（Stage D）前置检查必须验证 `git_tree_dirty == False`，若存在未提交修改，**必须立即终止生产流程**。

### 10.4 唯一性与基数不变量门控 (Cardinality Invariant Gate)
在执行官方单向预注册 LEFT JOIN 之前与之后，必须严格满足以下唯一性与基数不变量：
1. **键唯一性约束**：
   - `m0_signals` 表在主键 `(primary_stock_id, period_of_report)` 上必须全局严格唯一；
   - `m0_forward_returns` 表在主键 `(primary_stock_id, period_of_report)` 上必须全局严格唯一；
   - 任何一方存在重复键，**评估程序必须立即抛错中止 (ABORT)**。
2. **基数守恒不变量**：
   ```sql
   SELECT
       s.period_of_report,
       s.primary_stock_id,
       s.m0_signal,
       r.forward_return,
       r.outcome_status,
       (CASE WHEN r.forward_return IS NULL THEN 1 ELSE 0 END) AS is_outcome_missing
   FROM m0_signals s
   LEFT JOIN m0_forward_returns r
     ON s.primary_stock_id = r.primary_stock_id
    AND s.period_of_report = r.period_of_report;
   ```
   - **基数恒等式**：执行 LEFT JOIN 后的输出行数必须**严格等于**输入信号行数：
     $$\text{COUNT}(\text{evaluation\_joined\_rows}) \equiv \text{COUNT}(\text{m0\_signals})$$
   - 输出表的 `(primary_stock_id, period_of_report)` 键保持严格唯一。严禁使用 `INNER JOIN`，杜绝静默删除缺失收益样本。

---

## 11. 终审全状态流转真值表 (Exhaustive State-Action Truth Table)

| 状态名称 | 门控归属 | 厂商账本 | 样本量 | 因子命中 | 聚类 MAD | 调整中位数 | Primary 动作 | 拆股系数 | Sensitivity 动作 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `CORPORATE_ACTION_UNKNOWN` | Gate 0 | *任意* | *任意* | — | — | — | **EXCLUDE** | *无* | **EXCLUDE** |
| `KNOWN_SPLIT_LOW_POWER` | Gate 1.1 | **YES** | $N < 20$ | — | — | *未检验* | **INCLUDE** (带标记) | $K_{\text{ledger}}$ | **EXCLUDE** |
| `KNOWN_SPLIT_PASS` | Gate 1.2a | **YES** | $N \ge 20$ | — | — | $\in [0.8, 1.2]$ | **INCLUDE** | $K_{\text{ledger}}$ | **INCLUDE** |
| `KNOWN_SPLIT_MISMATCH` | Gate 1.2b | **YES** | $N \ge 20$ | — | — | $\notin [0.8, 1.2]$ | **EXCLUDE** | *无* | **EXCLUDE** |
| `LEDGER_ONLY_LOW_POWER` | Gate 2.1 | **NO** | $N < 20$ | — | — | — | **INCLUDE** (带标记) | $1.0$ | **EXCLUDE** |
| `CLEAN` | Gate 2.2a | **NO** | $N \ge 20$ | **未命中** | — | — | **INCLUDE** | $1.0$ | **INCLUDE** |
| `SPLIT_UNKNOWN` | Gate 2.2b | **NO** | $N \ge 20$ | **命中** | $\le 0.15$ | — | **EXCLUDE** | *无* | **EXCLUDE** |
| `SPLIT_AUDIT_AMBIGUOUS_HIGH_DISPERSION` | Gate 2.2c | **NO** | $N \ge 20$ | **命中** | $> 0.15$ | — | **EXCLUDE** | *无* | **EXCLUDE** |

---

## 12. 精确重跑准则与人话边界声明 (Rerun Rule & Honest Boundaries)

1. **唯一官方正式结果**：第一次无技术/机械性 Bug 的运行结果即为正式回测结果。
2. **严禁后验调参**：“IC 不符合预期”绝不是 Bug。任何由于代码错误引起的重跑，必须完整记录 Git Diff、修复说明、旧结果与新结果对比；信号公式与参数绝对不可变。
3. **样本子集限制**：本研究所有结论严格受限于“可被 OpenFIGI 成功映射且 yfinance 提供有效行情”的股票子集，绝不冒充全市场无偏结论。
4. **零点诊断性质**：M0 IC 显著与否仅作为数据流基准诊断，不构成任何 Alpha 策略盈利性宣称。
