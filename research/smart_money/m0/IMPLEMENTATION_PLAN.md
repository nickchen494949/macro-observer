# M0 Staged Implementation Plan — Test-Before-Production Protocol

**Version**: v0.8.1 Implementation Plan
**Status**: FROZEN IMPLEMENTATION PLAN; STAGE A IMPLEMENTED (PURE FUNCTIONS & UNIT SUITE) UNDER CODEX RE-AUDIT; STAGE B/C NOT STARTED
**Guiding Principle**: 先测试后生产，先证明再入库；源数据库绝对只读，信号与收益物理隔离；单向预注册 LEFT JOIN 评估；未获 Codex 审计批准前，严禁触碰未来价格数据。

---

## 阶段流水线总览 (Stage Pipeline Overview)

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ Stage A: 模块架构、独立派生库 Schema 与纯函数 (Pure Functions)               │
│ └── 门控 A: 10 大独立模块纯函数单元测试 100% PASS (无网络、不读历史价格 K 线) │
├─────────────────────────────────────────────────────────────────────────────┤
│ Stage B: 合约级 6 大类参数化合成反例对抗测试套件 (Synthetic Test Matrix)      │
│ └── 门控 B: 严格对应 B01–B23 测试用例，信号端、基数不变量与收益策略端全通过   │
├─────────────────────────────────────────────────────────────────────────────┤
│ Stage C: 真实样本 Pilot 基准验证 (基于冻结 Fixture 与 SEC 8-K 一手对账)       │
│ └── 门控 C: 真实申报与 SEC 8-K 证据对账 100% 吻合 (Point72 / Berkshire / 拆股)│
├─────────────────────────────────────────────────────────────────────────────┤
│ Stage D: 53-ZIP 全量信号端生产、拆股审计报表与 Manifest 校验和清单固化       │
│ └── 门控 D (核心硬阻断): 必须 Clean Tree，提交 Manifest 与存储预检供 Codex 审批│
├─────────────────────────────────────────────────────────────────────────────┤
│ Stage E: 行情快照入库与前向收益库独立构建 (outcome/m0_outcome.db)             │
│ └── 门控 E: 跨阶段 Manifest 绑定验证、收益键唯一性检查与 Price Manifest 固化 │
├─────────────────────────────────────────────────────────────────────────────┤
│ Stage F: 单次官方预注册 LEFT JOIN、Baseline IC 测算与强制敏感性分析          │
│ └── 门控 F: 绑定与基数守恒校验通过，产出最终全景研究报告 M0_RESULTS.md        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 阶段详细设计 (Detailed Stage Specifications)

### Stage A: 模块架构、独立 DB Schema 与纯函数实现

#### 目标
构建 M0 所需的代码与测试隔离目录，建立独立的派生数据库结构，实现 10 个无副作用的计算与解析纯模块。

#### 隔离目录与存储规范
- **代码与测试目录**：
  - 核心代码：`research/smart_money/m0/src/`
  - 测试用例：`research/smart_money/m0/tests/`
  *(严禁使用仓库根目录 `src/` 或 `tests/`)*
- **运行实例目录**：每一次回测运行分配全局唯一 `run_id`：
  - 信号端：`research/smart_money/m0/runs/<run_id>/signal/` (包含 `m0_signal.db`)
  - 收益端：`research/smart_money/m0/runs/<run_id>/outcome/` (包含 `m0_outcome.db`)
- **Phase 0 源数据库** (`research/smart_money/phase0/data/13f_full_4409f14.db`):
  - 必须以只读 URI 模式打开 (`file:{quote(path)}?mode=ro`)，支持路径特殊字符；
  - 严禁在源库中执行 `CREATE TABLE` 或 `UPDATE` 操作。

#### 10 大独立功能模块划分 (`research/smart_money/m0/src/`)
1. `storage_guard.py`: SQLite 只读模式守护器 (`mode=ro` URI 编码)、写入拦截阻断与派生库 Schema 初始化。
2. `run_paths.py`: 物理真实路径隔离管理器 (`realpath` 解析、禁止符号链接逃逸与目录重叠)。
3. `manifest_integrity.py`: 规范化标准 JSON 序列化 (`allow_nan=False`)、确定性 SHA-256 计算、工作区 Clean Tree 校验、缓存哈希核验（违规立即抛错）及跨阶段 Manifest 绑定核验。
4. `ownership_state_machine.py`: 所有权归属解析 (`origin_filer_cik`, `economic_owner_cik`)、机密申报门控与单机构申报状态机重构（严格按绝对时间戳 UTC instant ASC 及 accession_number ASC 排序；拒绝混入不同申报人或元数据不符行）。
5. `entity_membership_dedup.py`: PIT 实体图构建、独立申报成员一致性校验与跨申报经济签名去重（严格限定在同一 `canonical_entity_id` 内部）。
6. `security_mapping.py`: OpenFIGI 确定性瀑布决议（排除 ETF、非权益资产与非法 CUSIP）、名称相似度计算与多重候选歧义拒决。
7. `split_waterfall.py`: 期间配对厂商拆股系数 $K_{\text{ledger}}$ 计算（严格检验正实数与日期）、对数中位数与 $\text{MAD}_{\text{log}}$ 计算（强制持有者数量与样本一致）、Gate 0/1/2 严格有序瀑布状态机。
8. `signal_math.py`: 拆股调整 $\Delta\text{Shares}$ 计算、3x 审查风险启发式权重施加与股票级汇总（聚合后输出表无虚假股票级单一权重列）。
9. `coverage_keys.py`: D1 (`raw_cusip, period`) 与 D2 (`primary_stock_id, period`) 键生成与转换损耗追踪。
10. `outcome_policies.py`: 前复权开盘价计算（正实数价格校验）、真实交易日/顺延 $\le 5$ 日开盘选取函数、真实单股现金对价现金并购结算函数、单向预注册 LEFT JOIN 基数守恒校验及 4 大敏感性分支派生。

*(注：Stage A/B 期间绝不连接网络，不读取真实历史行情，收益策略逻辑全量基于合成数据测试)*

#### 阶段验收门控 (Gate A)
- **命令**: `pytest research/smart_money/m0/tests/test_stage_a_pure_functions.py`
- **标准**: 10 大模块单元测试通过率 100%，无类型与算术异常。
- **预估磁盘占用**: $\approx 0\text{ MB}$（纯代码）。

---

### Stage B: 合约级 6 大参数化对抗测试套件矩阵 (B01–B23)

#### 目标
在接触任何生产数据前，编写 6 大类参数化合成测试用例，严格对齐 B01–B23 编号，验证所有边界逻辑与基数不变量已被代码阻断。**所有 Stage B 测试均为纯数据逻辑测试，绝不读取真实历史价格 K 线**。

#### 6 大类参数化测试套件 (`research/smart_money/m0/tests/test_stage_b_counterexamples.py`)

- **Suite 1: 存储保护、路径隔离、Manifest 幂等性与 Clean Tree 门禁 (B01–B06)**
  - Test-B01: 只读 SQLite URI 写入拦截与含特殊字符（`?`, `#`）路径编码；
  - Test-B02: 信号端与收益端物理路径独立性、`realpath` 解析与符号链接逃逸拦截；
  - Test-B03: 规范化 JSON Manifest 序列化、`allow_nan=False` 与 SHA-256 确定性幂等性；
  - Test-B04: 重跑代码在相同输入下产生完全一致的信号校验和；
  - Test-B05: 原始 API 缓存文件篡改检测（校验和不匹配立即抛错阻断）；
  - Test-B06: 工作区 Clean Tree 校验门禁（模拟 `git_tree_dirty == True` 时 Manifest 生成函数必须立即抛错中止）。

- **Suite 2: 所有权作用域、状态机与实体成员完整性 (B07–B12)**
  - Test-B07: `ownership_unresolved` 显式隔离（未解析序列号从 Primary 排除，严禁 fallback 为自有）；
  - Test-B08: 作用域重叠持仓保留与去重（必须在同一 `canonical_entity_id` 内部去重，严禁跨实体合并）；
  - Test-B09: 非独立申报顾问节点连通性（不作为 expected filing member）；
  - Test-B10: 独立申报成员缺报/迟交假清仓防范（16-CIK 实体 1 成员迟交触发 `membership_incomplete`，整实体当季置为 Missing）；
  - Test-B11: 状态机带时区绝对时间戳排序（UTC Instant ASC）、Original/RESTATEMENT 全替换、ADD_NEW_HOLDINGS 就地覆盖（更新现有行绝不累加）、UNKNOWN 状态隔离及混入不同申报人异常拦截；
  - Test-B12: 实体关系时间戳美东日期无未来函数（$Q-1$ 边集严格 $\le \text{deadline}(Q-1)$）。

- **Suite 3: 拆股瀑布 8 大状态与有序门控 (B13.1–B13.8)**
  - Test-B13.1 (Gate 0 优先): 身份中断/非现金并购直接置为 `CORPORATE_ACTION_UNKNOWN` (EXCLUDE)；
  - Test-B13.2 (Gate 1.1): 账本有记录但 $N < 20 \to \text{KNOWN\_SPLIT\_LOW\_POWER}$ (INCLUDE, 标低功效)；
  - Test-B13.3 (Gate 1.2a): 账本有记录且 $N \ge 20$、调整后中位数 $1.01 \to \text{KNOWN\_SPLIT\_PASS}$ (INCLUDE)；
  - Test-B13.4 (Gate 1.2b): 账本有记录且 $N \ge 20$、调整后中位数 $1.45 \to \text{KNOWN\_SPLIT\_MISMATCH}$ (EXCLUDE)；
  - Test-B13.5 (Gate 2.1): 账本无记录且 $N < 20 \to \text{LEDGER\_ONLY\_LOW\_POWER}$ (INCLUDE, 标低功效)；
  - Test-B13.6 (Gate 2.2a): 账本无记录且 $N \ge 20$、中位数 $1.02 \to \text{CLEAN}$ (INCLUDE)；
  - Test-B13.7 (Gate 2.2b): 账本无记录且 $N \ge 20$、中位数 $3.99$、$\text{MAD}_{\text{log}} = 0.04 \to \text{SPLIT\_UNKNOWN}$ (EXCLUDE)；
  - Test-B13.8 (Gate 2.2c): 账本无记录且 $N \ge 20$、中位数 $1.58$、$\text{MAD}_{\text{log}} = 0.35 \to \text{SPLIT\_AUDIT\_AMBIGUOUS\_HIGH\_DISPERSION}$ (EXCLUDE)。

- **Suite 4: 标的映射、歧义拒决、3x 审查风险与机密申报 (B14–B16)**
  - Test-B14: OpenFIGI `shareClassFIGI` 优先选取、ETF 严格排除、非法 CUSIP 拦截及多重同分候选歧义拒决；
  - Test-B15: 3x 审查风险启发式 OR 门槛逻辑（$\text{shares} < 30,000$ 或 $\text{value\_usd} < \$600,000$ 满足其一即赋权重 0.3）；
  - Test-B16: 机密申报剔除门槛（实体-季度对包含 `is_confidential_omit=True` 申报时从 Primary 排除）。

- **Suite 5: 双分母 D1 与 D2 键语义 (B17)**
  - Test-B17: 验证 D1 严格基于 `(raw_cusip, period)`，D2 严格基于 `(primary_stock_id, period)`，转换损耗被完整统计。

- **Suite 6: 收益策略、键唯一性与基数不变量对抗套件 (B18–B23)**
  - Test-B18: 前复权开盘价公式 $\text{adjusted\_open} = \text{raw\_open} \times (\text{adj\_close} / \text{raw\_close})$ 计算吻合与非正实数价格拦截；
  - Test-B19: 真实指定交易日开盘选取、停牌/NaN/Inf 时判定缺失（`is_outcome_missing = 1`）及按独立交易所日历计数的 $\le 5$ 交易日顺延回退逻辑（缺报价行仍消耗交易日名额）；
  - Test-B20: 真实官方 SEC 8-K 纯现金并购对价结算收益与非现金/不确定并购置为缺失（`is_outcome_missing = 1`）；
  - Test-B21: 键唯一性违规拦截（模拟 `m0_signals` 或 `m0_forward_returns` 出现重复 `(primary_stock_id, period)` 键时，LEFT JOIN 预检必须立即抛错中止）；
  - Test-B22: 基数守恒不变量（验证单向预注册 LEFT JOIN 输出行数与信号表输入行数严格相等：$\text{rows}(\text{joined}) \equiv \text{rows}(\text{signals})$，缺失收益行被 100% 保留且标记 `is_outcome_missing = 1`）；
  - Test-B23: 在同一张保留全量行的 LEFT JOIN 表上，派生计算 Primary（过滤 NaN/缺失）、$\text{Missing}=-100\%$、$\text{Missing}=0\%$ 及 $\le 5$ 日顺延分支。

#### 阶段验收门控 (Gate B)
- **命令**: `pytest research/smart_money/m0/tests/test_stage_b_counterexamples.py`
- **标准**: 6 大套件所有参数化测试用例严格 **PASS**。
- **预估磁盘占用**: $\approx 5\text{ MB}$（测试 SQLite 内存库）。

---

### Stage C: 真实样本 Pilot 基准验证 (手工可审计对账)

#### 目标
在真实 13F 历史数据切片中，先固化手工可审计的期望值夹具（Expected Fixtures）与 SEC 一手 8-K 证据，再执行程序对账。

#### 核心验证标的与固定夹具
- **Point72 实体组件** (未冻结规划夹具，需先固化):
  - 提取 2019Q4 真实申报 Accession 列表与引用序列号，固化手工对账夹具；
  - 验证跨 CIK 相同经济签名行被精确去重，不同签名持仓完整保留（严禁在夹具固化前声称 100% 正确）。
- **Berkshire Hathaway 苹果持仓** (CIK `0001067983`, CUSIP `037833100`):
  - 引用原始申报 `0000950123-24-002518`；
  - 验证 2023Q4 聚合后总股数严格等于 SEC 官方申报的 905,560,000 股。
- **四大冻结拆股基准一手对账** (引用 SEC 8-K 申报证据):
  - NVDA (10:1, 2024Q2) $\to$ 连续持有者调整后中位数 $\in [0.8, 1.2]$。
  - TSLA (3:1, 2022Q3) $\to$ 连续持有者调整后中位数 $\in [0.8, 1.2]$。
  - AMZN (20:1, 2022Q2) $\to$ 连续持有者调整后中位数 $\in [0.8, 1.2]$。
  - GOOGL (20:1, 2022Q3) $\to$ 连续持有者调整后中位数 $\in [0.8, 1.2]$。

#### 阶段验收门控 (Gate C)
- **命令**: `python -m research.smart_money.m0.src.run_pilot_benchmarks`
- **标准**: 与固化夹具比对完全吻合，四大基准拆股调整中位数全量落在 $[0.8, 1.2]$。
- **预估磁盘占用**: 暂存切片数据 $\approx 200\sim 500\text{ MB}$（严禁自动删除用户数据）。

---

### Stage D: 53-ZIP 全量信号端生产、拆股审计报表与 Manifest 校验和清单固化

#### 目标
在全量 53-ZIP 数据库（只读模式）上完成 13F 数据流解析、实体构建、OpenFIGI 标的映射、厂商拆股元数据对账及 $\text{M0\_signal}$ 计算，并输出拆股审计报表与 Signal Manifest。

#### 核心输出
1. 信号端独立派生库落地 (`research/smart_money/m0/runs/<run_id>/signal/m0_signal.db`)，并确保 `(primary_stock_id, period_of_report)` 唯一键无冲突；
2. 拆股瀑布门控审计报表 (`research/smart_money/m0/runs/<run_id>/signal/m0_split_waterfall_audit.md`)；
3. 映射与信号覆盖率报表 (`research/smart_money/m0/runs/<run_id>/signal/m0_signal_coverage.md`)；
4. **变更检测校验和清单**: `SHA256_SIGNAL_MANIFEST.json`，完整记录：
   - `phase0_db_path` 与 `phase0_db_sha256`
   - `source_git_sha` 与 `m0_code_git_sha`、`git_tree_dirty` 状态 (必须为 `False`)
   - `contract_version` 与 `contract_sha256`
   - `schema_versions` 与 `query_versions`
   - `python_version`、`os_info` 与 `dependency_versions` (含精确版本号)
   - `created_utc` 时间戳
   - `openfigi_raw_cache` (所有请求、响应、URL、HTTP 状态码及 SHA-256 校验和)
   - `vendor_split_raw_cache` (URL、HTTP 状态码及 SHA-256 校验和)
   - `sec_benchmark_evidence` (原始 8-K 字节哈希、URL 与抓取时间戳)
   - `entity_fixture_version`
   - `signal_tables_sha256` (各信号表物理文件的 SHA-256 哈希)
5. 文件系统权限设置：`chmod 444` 设置为意外写防护只读状态。

#### 阶段验收门控 (Gate D — 核心硬阻断)
- **工作区 Clean Tree 铁律**: Preflight 检查工作区状态，若 `git status --short` 非空（`git_tree_dirty == True`），**立即中止 Stage D 生产写入**。
- **键唯一性门控**: 验证 `m0_signals` 主键 `(primary_stock_id, period_of_report)` 无重复记录。
- **存储安全预检**: 从 Pilot 实际消耗外推全量空间需求，确保磁盘剩余空间大于预估值 2 倍且 WAL 具备安全裕量。**未获 Codex 存储审批前，严禁执行 Stage D 全量写入**。
- **硬阻断**: 输出报表与 Manifest，**停机等待 Codex 审计**。必须获得 Codex 明确的 **APPROVE** 指令，方可进入 Stage E。
- **预估磁盘占用**: 暂定 $\approx 3.5\sim 4.5\text{ GB}$（以 Pilot 实测外推为准）。

---

### Stage E: 行情快照入库与前向收益表构建

#### 目标
在信号端产物完全只读锁定的前提下，一次性下载并固化 yfinance 日频行情快照（`auto_adjust=False, actions=True`），独立构建前向收益库。

#### 核心输出与行为限制
1. 收益端独立派生库 (`research/smart_money/m0/runs/<run_id>/outcome/m0_outcome.db`)，包含 `m0_forward_returns`，并确保 `(primary_stock_id, period_of_report)` 唯一键无冲突；
2. **严禁重新计算拆股状态**：仅关联 Stage D 已固化的拆股状态进行双分母披露；
3. **收益变更检测校验和清单**: `SHA256_PRICE_MANIFEST.json`，完整记录：
   - `run_id`、`signal_manifest_sha256` (与 Stage D 严格绑定)
   - `contract_version`、`contract_sha256`、`source_git_sha`、`m0_code_git_sha`
   - `price_requests_cache` (请求代码、日期间隔、HTTP 状态码、原始数据文件 SHA-256)
   - `dependency_versions`
   - `schedule_rule_version` (交易日开盘选取规则版本)
   - `cash_m_and_a_evidence` (现金并购官方 8-K URL、对价与哈希)
   - `outcome_tables_sha256` (收益表物理文件 SHA-256 哈希)
4. 双分母覆盖率全景报表 (`research/smart_money/m0/runs/<run_id>/outcome/m0_dual_denominator_coverage.md`)。

#### 阶段验收门控 (Gate E)
- **标准**:
  - 跨阶段 Manifest 绑定核验 100% 一致；
  - 行情快照 SHA-256 固化完成；
  - `m0_forward_returns` 键唯一性检验通过；
  - 8 大拆股状态在双分母 (D1/D2) 下完整穿透披露；
  - 收益端与信号端在物理库上保持完全隔离。
- **预估磁盘占用**: 暂定 $\approx 2.0\sim 2.5\text{ GB}$（以实测外推为准）。

---

### Stage F: 单次官方预注册 LEFT JOIN 与诊断评价

#### 目标
校验两个 Manifest 的跨阶段绑定哈希一致性，执行唯一一次正式单向预注册 LEFT JOIN，输出正式 M0 基准诊断指标。

#### 核心产物与交付
1. **单次预注册 LEFT JOIN 执行与基数不变量验证**:
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
   - **基数守恒强制门控**: 校验输出行数严格等于 `m0_signals` 行数 ($\text{rows}(\text{joined}) \equiv \text{rows}(\text{signals})$)。
2. **官方核心指标测算**:
   - 官方全样本 Rank IC 均值 (Mean Quarterly Spearman Rank IC, 仅在 LEFT JOIN 后过滤有效收益)；
   - Newey-West HAC $t$-统计量 ($\text{maxlags}=1$) 及双边 $p$-值；
   - 普通 $t$-统计量 (辅助参考)；
   - 季度胜率 (Hit Rate, $\text{IC} > 0$ 季度占比)；
   - 逐年 IC 拆解 (Annual IC Breakdown)。
3. **强制敏感性对照矩阵 (基于同一张 LEFT JOIN 表派生)**:
   - Primary 结果 vs 排除 `LEDGER_ONLY_LOW_POWER` (高统计功效子集)；
   - 排除 `KNOWN_SPLIT_LOW_POWER` 对照；
   - 退市缺失标的收益设为 $-100\%$ 压力测试；
   - 退市缺失标的收益设为 $0\%$ 压力测试；
   - 停牌交易日顺延 $\le 5$ 日对照。
4. **正式审计交付报告**: `research/smart_money/m0/runs/<run_id>/M0_RESULTS.md`。

#### 阶段验收门控 (Gate F)
- **标准**: 基数守恒校验通过，无任何技术报错，敏感性分析完整，报表冠以官方诚实标题并包含人话总结与 ASCII 状态图。
- **预估磁盘占用**: $\approx 50\text{ MB}$。

---

## 磁盘空间与资源安全管理 (Disk Footprint & Safety Protocol)

### 1) 当前真实环境基线
- **系统可用空间**: $\approx 15\text{ GiB}$ (Verified Baseline)
- **Phase 0 源数据库**: $\approx 24.5\text{ GB}$ (只读存据，严禁写入)

### 2) 暂定空间预算与外推机制
所有生产阶段的磁盘预估值均为**暂定外推值（Provisional Estimates）**，必须在 Stage C Pilot 完成后根据实际行数字节比进行精确二次校验：

| 阶段 | 主要产物 | 暂定预估占用 | 累计暂定占用 | 当前 15 GiB 裕量状态 |
|---|---|:---:|:---:|:---:|
| **Stage A & B** | 代码、轻量内存单元测试 | $\approx 5\text{ MB}$ | $5\text{ MB}$ | 极充裕 ($>14.9\text{ GiB}$) |
| **Stage C** | Pilot 样本切片 DB | $\approx 300\text{ MB}$ | $305\text{ MB}$ | 充裕 ($>14.6\text{ GiB}$) |
| **Stage D** | 全量信号库 (`m0_signal.db`) | $\approx 3.5\sim 4.5\text{ GB}$ | $\approx 4.8\text{ GB}$ | 安全 ($>10.0\text{ GiB}$) |
| **Stage E** | 全量收益库 (`m0_outcome.db`) | $\approx 2.0\sim 2.5\text{ GB}$ | $\approx 7.3\text{ GB}$ | 安全 ($>7.5\text{ GiB}$) |
| **Stage F** | 评估结果与报表文件 | $\approx 50\text{ MB}$ | $\approx 7.35\text{ GB}$ | 安全 ($>7.5\text{ GiB}$) |

### 3) 生产写入四大铁律
1. **Preflight 检查**: 每一个生产阶段启动前，程序自动执行 `df -h` 磁盘预检，若可用空间低于目标阶段预估值的 2 倍，**自动抛错拒绝执行**。
2. **WAL 熔断保护**: 继承 Phase 0 的 `_safe_wal_checkpoint` 熔断机制，每批提交后执行 checkpoint，若 WAL 增长超过 1.5 GB 自动抛错中止，杜绝爆盘。
3. **数据保护**: 严禁在代码中编写 `rm` 或自动删除 Pilot/用户历史数据的逻辑。
4. **存储硬审批**: Stage C 完成后必须向 Codex 提交 Pilot 实测空间外推报告，**获得 Codex 明确存储批准后方可启动 Stage D 全量写入**。
