# Smart Money Research Specification Matrix v1.5
*升级自 v1.4，2026-08-23 — Phase 0 Freeze Audit 最终修正*

> **v1.5 = 规格正式冻结。**
> 模型架构（M0–M6）冻结；数据工程规格冻结。
> v1.5 之后进入 Phase 0 全量下载 → CH-1 to CH-12 → freeze pipeline → M0。

---

## v1.4 → v1.5 修正摘要

| # | 严重度 | 修正项目 | v1.4（错误） | v1.5（修正） |
|---|--------|---------|------------|------------|
| 1 | 🔴 | World A 实际返回空数据 | `acceptance_datetime <= period_of_report` | **A1/A2 重新定义；A1 用 World B 已知状态 + 季末时间戳** |
| 2 | 🔴 | Amendment 状态机语义错误 | `LatestBefore(t)` 单一规则 | **RESTATEMENT → REPLACE；ADD_NEW_HOLDINGS → MERGE** |
| 3 | 🔴 | `.shares.last()` 用于 dedup | 同 CUSIP 多行取最后一行 | **Discretion-aware sum → shared-ownership graph → cross-accession dedup** |
| 4 | 🔴 | PUT/CALL 未与现股分离 | 混入同 CUSIP 合计 | **Phase 0 强制分离；M0 只用 cash-equity SH 行** |
| 5 | 🔴 | 截止日简单写 `+45 calendar days` | 不处理周末/联邦假期 | **Rule 0-3 calendar：顺延至下一个 SEC 工作日** |
| 6 | 🟠 | Submissions API 分页不完整 | 只读 main JSON | **展开 `files[]` + 优先使用 `submissions.zip` bulk** |
| 7 | 🟠 | De minimis 门槛未处理 | 0→position = "新建仓" | **靠近阈值的 NEW/EXIT 加 `reporting_threshold_censor_flag`** |
| 8 | 🟠 | Free Prototype 无法算 PIT MCap/BM | Controls 含 ln(Size) ln(BM) | **Free 版 controls 改为纯价格类（Momentum + Reversal + Liquidity）** |
| 9 | 🟠 | CUSIP → 价格 mapping 无正式规格 | "CUSIP PIT mapping" 笼统 | **Phase 0 新增子项目 0.13；SEC 13(f) list 作主干** |
| 10 | ✅ | 2026Q2 bulk 判断 | 正确 | 不变 |

---

## 1. 数据状态三个世界（v1.5 重写）

### 1.1 三世界正确定义

```
WORLD A1 — Backdated Disclosure（v1.5 新定义）
────────────────────────────────────────────────
Holdings state:  与 World B 完全相同
                 （= 13F deadline 前已 accepted 的 filings）
Trade timestamp: 人为设为 quarter-end（不是 deadline）
用途:            测量 Disclosure Delay Cost
                 Return(A1) − Return(B) = 纯粹来自"早知道 45 天"的价值
不可交易:        季末没有 13F 数据，无法实操

实现:
  holdings_state = get_world_b_state(period_of_report)  # 与 B 完全一样
  trade_date = quarter_end_date                          # 仅时间戳不同

WORLD A2 — Final Corrected State（理论上界）
────────────────────────────────────────────────
Holdings state:  包含后来所有 restatements + confidential releases
Trade timestamp: quarter-end
用途:            理论信息上限；不可拆分为 "Delay Cost"
注意:            A2 − B 包含 Disclosure Delay + Restatement Information
                 不能将 A2 − B 称为"Delay Cost"（v1.4 已有此说明）

WORLD B — Fixed-PIT（Primary；唯一可交易的）
────────────────────────────────────────────────
Holdings state:  get_world_b_state(period_of_report)
                 = LatestVersionBefore(filing_deadline)
Trade timestamp: filing_deadline + 1 market open

```

### 1.2 get_world_b_state() 的正确实现

```python
def get_world_b_state(period_of_report: str, cik: str) -> dict:
    """
    Returns the set of all accepted filings for this (cik, period_of_report)
    that were accepted before the filing deadline.
    """
    deadline = compute_13f_deadline(period_of_report)  # see Section 1.3
    
    rows = db.query("""
        SELECT * FROM filing_events
        WHERE cik = ? AND period_of_report = ?
          AND acceptance_datetime <= ?
        ORDER BY acceptance_datetime ASC
    """, (cik, period_of_report, deadline))
    
    return reconstruct_state(rows)  # see Section 2: Amendment State Machine
```

### 1.3 13F Filing Deadline Calendar（v1.5 修正）

```python
import pandas_market_calendars as mcal  # or custom SEC calendar

SEC_FEDERAL_HOLIDAYS = [
    # New Year's Day, MLK Day, Presidents' Day, Memorial Day,
    # Juneteenth, Independence Day, Labor Day, Columbus Day,
    # Veterans Day, Thanksgiving, Christmas
    # Source: SEC observes Federal Reserve holidays
]

def compute_13f_deadline(period_of_report: str) -> str:
    """
    SEC Rule: 13F must be filed within 45 calendar days of quarter end.
    If 45th day falls on weekend or federal holiday → next SEC business day.

    Example confirmed by SEC FAQ:
      Q4 2025: period = 2025-12-31
      45th day = 2026-02-14 (Saturday)
      Feb 16 = Presidents' Day (federal holiday)
      True deadline = 2026-02-17 (Tuesday)
    """
    quarter_end = pd.Timestamp(period_of_report)
    raw_due = quarter_end + pd.Timedelta(days=45)
    
    # Roll forward to next SEC business day if needed
    while raw_due.weekday() >= 5 or raw_due in SEC_FEDERAL_HOLIDAYS:
        raw_due += pd.Timedelta(days=1)
    
    return raw_due.strftime('%Y-%m-%d')

# Preferred implementation:
#   Maintain a 13F_due_calendar table with official dates
#   Source: SEC FAQ / EDGAR filing calendar
#   Use Rule 0-3 algorithm only as fallback
```

---

## 2. Amendment State Machine（v1.5 重写）

### 2.1 两种语义

```
13F Amendment 有两种完全不同的语义（SEC FAQ 明确区分）：

TYPE A: RESTATEMENT
  语义: 修正错误 → 完整新版本替代旧版本
  Rule: new_state = amendment_holdings (REPLACE original)
  识别: amendment 包含完整 holdings table；SEC 说"corrected filing"

TYPE B: ADD_NEW_HOLDINGS
  语义: 补充遗漏 → 追加到原有 holdings
  Rule: new_state = original_holdings UNION amendment_additions (MERGE)
  识别: amendment 说明"supplements the original filing"

关键错误示例（如不区分）：
  Original: AAPL 5m, MSFT 3m, GOOG 2m
  Amendment (ADD type): adds NVDA 1m
  Wrong (LatestBefore only): state = NVDA 1m  → AAPL/MSFT/GOOG 全部丢失！
  Correct (MERGE): state = AAPL 5m, MSFT 3m, GOOG 2m, NVDA 1m
```

### 2.2 数据库结构（v1.5 新增字段）

```sql
CREATE TABLE filing_events (
    accession_number     TEXT PRIMARY KEY,
    cik                  TEXT NOT NULL,
    period_of_report     TEXT NOT NULL,    -- PERIODOFREPORT (YYYY-MM-DD)
    acceptance_datetime  TEXT,             -- from Submissions API
    filing_date          TEXT,
    form_type            TEXT,             -- 13F-HR, 13F-HR/A, 13F-NT, 13F-NT/A
    amendment_type       TEXT,             -- NULL / RESTATEMENT / ADD_NEW_HOLDINGS
    supersedes_accession TEXT,             -- populated for RESTATEMENT type
    is_confidential_omit BOOLEAN,
    conf_flag_quality    TEXT              -- A / B / C
);

CREATE TABLE filing_line_items (
    accession_number     TEXT,
    line_seq             INTEGER,          -- original row order preserved
    cusip                TEXT,
    security_name        TEXT,
    title_of_class       TEXT,
    value_usd            INTEGER,          -- after normalization
    sshprnamt            INTEGER,          -- shares or principal amount
    sshprnamttype        TEXT,             -- SH / PRN
    put_call             TEXT,             -- NULL / PUT / CALL
    investment_discretion TEXT,           -- SOLE / SHARED / DFND / OTR
    other_manager        TEXT,
    voting_auth_sole     INTEGER,
    voting_auth_shared   INTEGER,
    voting_auth_none     INTEGER,
    PRIMARY KEY (accession_number, line_seq)
);
```

### 2.3 reconstruct_state() 算法

```python
def reconstruct_state(filing_rows: list, as_of_dt: str) -> list:
    """
    Given all filing events for a (cik, period_of_report) sorted by
    acceptance_datetime ASC, reconstruct the correct known state at as_of_dt.

    Returns: list of (cusip, shares, put_call, investment_discretion, ...)
    """
    state = {}  # cusip+discretion → line items (from original)

    for filing in sorted(filing_rows, key=lambda r: r.acceptance_datetime):
        if filing.acceptance_datetime > as_of_dt:
            break

        if filing.form_type == '13F-HR' and filing.amendment_type is None:
            # Original filing: set base state
            state = {row.key: row for row in filing.line_items}

        elif filing.amendment_type == 'RESTATEMENT':
            # Complete replacement
            state = {row.key: row for row in filing.line_items}

        elif filing.amendment_type == 'ADD_NEW_HOLDINGS':
            # Supplement: merge additions into existing state
            for row in filing.line_items:
                state[row.key] = row  # add or update specific entries

    return list(state.values())
```

---

## 3. Line-Item Aggregation（v1.5 — .last() 完全移除）

### 3.1 正确的三步聚合

```
STEP 1: Within-accession aggregation（按 investment discretion 分类）

  同一 accession，同一 CUSIP，可能有多行（不同 discretion）：
    AAPL  SOLE     1,000,000 shares
    AAPL  SHARED   2,000,000 shares
    AAPL  DFND       500,000 shares

  Rule: 对于信号研究，经济持仓 = 所有 discretion 类型的 shares 之和
        （manager 对这些股票有某种程度的投资权力）

  BUT: "OtherManager" 字段必须先检查
    → 如果 OtherManager 指向另一个已独立报告的 CIK
    → 该行可能是 shared-discretion 的重复报告
    → 需要 Shared-Ownership Resolution（Step 2）

STEP 2: Shared-Ownership Graph Resolution

  构建图：
    Node = CIK
    Edge = 两个 CIK 通过 OtherManager 字段相互引用同一持仓

  Rule:
    同一持仓（CUSIP + shares）如果被两个 CIK 都报告
    → 只计入一次（归属 ultimate decision-maker CIK）
    → 其他 CIK 的该行打 shared_counted = False

  简化版（免费 prototype）:
    对 OtherManager 字段非空的行 → 标注 shared_flag = True
    aggregate 时排除 shared_flag = True 的行（保守处理）
    记录 coverage gap in QA log

STEP 3: Cross-accession dedup（Entity dedup）

  对同一 (ultimate_manager_cik, cusip, period_of_report)
  使用 reconstruct_state() 的最终结果（已处理 RESTATEMENT/MERGE）
  不再使用 .last()

  Note: 同一 economic entity 可能有多个 CIK filings（见 v1.4）
        → 只保留 ultimate_manager_cik 层级的汇总
```

---

## 4. PUT/CALL 分离（v1.5 — M0 前强制执行）

### 4.1 分离规则

```python
def classify_line_item(row) -> str:
    """
    Returns: 'cash_equity' / 'call_option' / 'put_option' / 'bond' / 'other'
    """
    if row.put_call == 'CALL':
        return 'call_option'
    elif row.put_call == 'PUT':
        return 'put_option'
    elif row.sshprnamttype == 'PRN':
        return 'bond'
    elif row.sshprnamttype == 'SH' and row.put_call is None:
        return 'cash_equity'
    else:
        return 'other'

# M0 Cash Equity = rows where classify() == 'cash_equity' ONLY

# Option Layer (separate; for future research):
#   CALL: manager holds call → potential bullish signal
#   PUT:  manager holds put → potential bearish/hedge signal
#   研究价值：CALL change + SHORT decrease = 更强 bullish confirmation？
#   但绝对不能与 cash shares 混同合计
```

### 4.2 重要说明

```
PUT/CALL 行使用 underlying security 的 CUSIP（SEC 官方规定）

因此简单 groupby(CUSIP).sum() 会得到：
  Cash AAPL:   5,000,000 shares
  CALL AAPL:  20,000,000 underlying shares (notional equiv)
  Total:      25,000,000  ← 错误！这不是持股量

CH-10 验收：
  对任意已知 manager（如 Pershing Square）的某季度
  确认：cash equity shares = 官方公告持股数
  不包含 option notional
```

---

## 5. Submissions API 完整分页（v1.5）

### 5.1 推荐策略：优先 submissions.zip

```python
# 策略 1（推荐）: 下载 SEC bulk submissions archive
# URL: https://data.sec.gov/submissions/submissions.zip (nightly refresh)
# 包含：所有 CIK 的近期 + files[] 历史链接
# 一次性下载，大幅减少 per-CIK 请求

# 策略 2（补充）: 逐 CIK API 请求（处理 submissions.zip 中仅有链接的历史部分）
def fetch_all_submissions(cik: str) -> list:
    """
    SEC API: main JSON 只保证近 1 年 or 最新 1000 filings
    Historical filings 通过 files[] 数组引用
    """
    main_url = f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json"
    main_data = requests.get(main_url, headers=HEADERS).json()
    
    all_filings = main_data['filings']['recent']  # recent batch
    
    # Paginate through historical files
    for hist_file in main_data['filings'].get('files', []):
        hist_url = f"https://data.sec.gov/submissions/{hist_file['name']}"
        hist_data = requests.get(hist_url, headers=HEADERS).json()
        # merge hist_data into all_filings
        for key in all_filings:
            all_filings[key].extend(hist_data.get(key, []))
    
    return all_filings

# Rate limit: 10 requests/sec; User-Agent required
# Cache locally: write to SQLite; skip if already present
```

---

## 6. De Minimis Reporting Threshold（v1.5 新增）

```
SEC 允许 manager 豁免报告满足以下两个条件的持仓：
  shares < 10,000 AND value < $200,000

信号影响：
  Q1: 8,000 shares (未报告) → Q2: 10,100 shares (报告)
  信号解读: "突然新建仓！" → 实际: 只增仓 2,100 shares

解决方案：censor flag
```

```python
DE_MINIMIS_SHARES = 10_000
DE_MINIMIS_VALUE_USD = 200_000

def compute_censor_flag(position, prev_position):
    """
    Flag potential censoring at reporting threshold boundary.
    """
    is_new_entry = (prev_position is None or prev_position.shares == 0)
    is_exit = (position is None or position.shares == 0)
    
    if is_new_entry and position:
        near_threshold = (
            position.shares < DE_MINIMIS_SHARES * 3 or    # within 3x threshold
            position.value_usd < DE_MINIMIS_VALUE_USD * 3
        )
        if near_threshold:
            return 'LOW_CONFIDENCE_NEW'
    
    if is_exit and prev_position:
        near_threshold = (
            prev_position.shares < DE_MINIMIS_SHARES * 3 or
            prev_position.value_usd < DE_MINIMIS_VALUE_USD * 3
        )
        if near_threshold:
            return 'LOW_CONFIDENCE_EXIT'
    
    return 'NORMAL'

# Usage in Signal Construction:
# signal_weight = 1.0 if censor_flag == 'NORMAL' else 0.3
# 大型基金（Berkshire 等）几乎不受影响；全市场 consensus 尤其小盘受影响
```

---

## 7. Free Prototype Controls（v1.5 修正）

### 7.1 问题：PIT MCap/BM 在免费版不可得

```
v1.4 写的 Controls:
  ln(Size), ln(BM), Past 12-1M Momentum, Past 1M Reversal

问题:
  ln(Size) = ln(Price × Shares Outstanding)
  → Shares Outstanding: yfinance 非 PIT（当前值回填）
  → 不能用"今天 shares × 2015 price" → lookahead

  ln(BM) = ln(Book Equity / Market Cap)
  → Book Equity: 需要 CRSP/Compustat or SEC CompanyFacts
  → 无 free PIT 来源（默认不可用）
```

### 7.2 两个版本的控制变量

```
FREE PROTOTYPE CONTROLS（全部 PIT，无付费数据）:
  Past 12-1M Return     (price momentum)        ← yfinance adj_close OK
  Past 1M Return        (short-term reversal)    ← yfinance adj_close OK
  Price Level           (proxy for size/micro)   ← yfinance OK
  Avg Daily Volume      (liquidity proxy)         ← yfinance OK
  Universe: Price > $5 + liquidity threshold
  Note: MCap > $300M filter becomes "price × approx shares" proxy

ACADEMIC CONTROLS（CRSP/Compustat）:
  ln(Size) = ln(MCap)   PIT monthly CRSP
  ln(BM)                PIT quarterly Compustat
  Past 12-1M Momentum   CRSP
  Past 1M Reversal      CRSP
  Universe: CRSP SHRCD 10/11; MCap > $300M

ALTERNATIVE FREE PATH（SEC CompanyFacts）:
  Historical shares outstanding via:
    https://data.sec.gov/api/xbrl/companyfacts/CIK{}.json
    → us-gaap:CommonStockSharesOutstanding
    → 使用 filed date 作 PIT timestamp
  Book equity via:
    us-gaap:StockholdersEquity or us-gaap:RetainedEarningsAccumulatedDeficit
  Coverage: ~2010+; filing-date lagged（not instant）
  工程量: Phase 0 大幅扩展（标注为 Phase 0B，可选）
```

---

## 8. CUSIP → 价格 Mapping（v1.5 正式子项目）

```
Phase 0 子项目 0.13: CUSIP-to-Price Mapping

数据来源层级（按优先级）:

LAYER 1: SEC Official 13(f) Securities List（免费）
  URL: https://www.sec.gov/rules-regulations/staff-guidance/official-list-section-13f-securities
  内容: 每季度 CUSIP + security name + class (archived)
  价值: 验证 CUSIP 的合法性 + class 信息

LAYER 2: OpenFIGI API（免费，需注册）
  URL: https://www.openfigi.com/api
  Mapping: CUSIP → FIGI → exchange ticker → Bloomberg ticker
  Coverage: 主要存活证券；历史 coverage 有限

LAYER 3: yfinance（通过 ticker 取价格）
  Challenge: ticker 可能已变化 / 退市
  问题: yfinance.Ticker('AAPL').history() OK
        Delisted stocks: 通常无历史数据

LAYER 4: SEC EDGAR Submission 中的 ticker
  CIK JSON 有 tickers 字段（当前；非历史）

LAYER 5: CRSP（付费；最完整）
  PERMNO → CUSIP（PIT）→ ticker → delisting-adjusted price

免费 Prototype 实现:
  1. SEC 13(f) list → valid CUSIPs per quarter
  2. OpenFIGI → ticker mapping
  3. yfinance → price history（surviving stocks）
  4. 退市 CUSIP → 标 delisted_flag；return = NaN → Missing outcome
  5. QA: 每季度报告 CUSIP coverage rate

CH-13 验收（新增）:
  对 2020Q1 universe 随机抽 100 CUSIPs
  确认 ticker mapping 正确率 > 90%
  退市 CUSIP 有 delisted_flag 而非静默丢弃
```

---

## 9. Phase 0 完整规格（v1.5 最终版）

### 验收检查列表（CH-1 to CH-13）

```
所有检查必须在"打开未来收益数据"之前完成并通过。

CH-1: VALUE normalization reconciliation
  PASS: |Σ position_value_usd − tableValueTotal_normalized| / total < 1%
  CHECK: 2023Q1 附近无 1000× discontinuity
  CASE: Berkshire 2023-02-14 filing (period 2022-12-31) → nearest dollar

CH-2: 已知持仓对账
  CASE: Berkshire 2023Q4 (period 2023-12-31)
  PASS: Top 10 positions shares 与 SEC 官方一致 ±1%

CH-3: Split adjustment 验证
  CASE: NVDA 2024-06-10 10:1 split
  PASS: Q2 2024 ΔShares NVDA 无虚假 9× 增加

CH-4: Amendment state(t) 正确性
  CASE A: RESTATEMENT type → state = amendment holdings only
  CASE B: ADD_NEW_HOLDINGS type → state = original UNION amendment
  PASS: 两种语义均正确；original holdings 不因 ADD type 而丢失

CH-5: Entity dedup 验证
  CASE: Point72 parent + subsidiary
  PASS: 同一 CUSIP 无重复经济持仓

CH-6: CUSIP 连续性
  PASS: 无 corporate action 情况下，同一 manager CUSIP 无无故断裂

CH-7: Universe 无未来函数
  PASS: 取一个后来退市的股票，确认在退市前各季度均在 universe
  CHECK: 无以"未来无 return"为由删除的观测

CH-8: AcceptedTimestamp 完整性
  PASS: > 95% accessions 有 acceptance_datetime
  METHOD: submissions.zip bulk + files[] pagination

CH-9: Amendment semantics
  CASE: 找一个已知 ADD_NEW_HOLDINGS 型 amendment
  PASS: reconstruct_state() 返回 original + additions（而非只有 additions）

CH-10: Option separation
  CASE: 找一个已知有 CALL options 的 manager
  PASS: cash_equity shares ≠ cash + option notional
  PASS: put_call 字段正确填充；cash equity 层 put_call = NULL only

CH-11: Deadline calendar
  CASE: Q4 2025 (period 2025-12-31) → 验证 deadline = 2026-02-17（非 2026-02-14）
  PASS: SEC holiday / weekend rollforward 正确执行

CH-12: Historical submissions completeness
  CASE: 大型 filer（如 Morgan Stanley CIK 895421）
  PASS: 2013–2026 所有 13F accessions 均有 acceptance_datetime
  METHOD: files[] pagination 或 submissions.zip 全量

CH-13: CUSIP → ticker mapping coverage（v1.5 新增）
  CASE: 2020Q1 universe 随机 100 CUSIPs
  PASS: mapping 正确率 > 90%
  PASS: 退市 CUSIP 有 delisted_flag（非静默 drop）

── 全部 CH-1 to CH-13 通过 ──
── 冻结 pipeline ──
── 然后才第一次打开 future returns ──
```

### Phase 0 子任务列表

```
0.1:  EDGAR 13F bulk → 按 PERIODOFREPORT 重建
0.2:  Submissions API + submissions.zip → acceptance_datetime enrichment
0.3:  VALUE normalization by acceptance_datetime
0.4:  Corporate action split adjustment
0.5:  Amendment state machine（RESTATEMENT/MERGE + filing_events table）
0.6:  Line-item classification（cash_equity / call / put / bond）
0.7:  Within-accession aggregation（discretion-aware）
0.8:  Shared-ownership graph resolution
0.9:  Cross-accession entity dedup
0.10: CUSIP PIT mapping（SEC 13(f) list + OpenFIGI）  ← 0.13 拆出
0.11: Confidential flag quality tier（A/B/C）
0.12: Universe filter（无未来函数）
0.13: CUSIP → price mapping（yfinance + delisted_flag）[new]
0.14: De minimis censor flag（new）
0.15: Deadline calendar（Rule 0-3 + SEC holiday table）[new]
0.16: FF5 + MOM factor data（French Library）
0.17: FINRA SI（2021-06+）
      [Optional 0.18: SEC CompanyFacts PIT fundamentals]
```

---

## 10. 完整数据状态架构（v1.5 最终）

```
RAW SEC FILING (ZIP + live API)
         │
         ↓
PERIODOFREPORT indexing (not ZIP quarter)
         │
         ↓
Acceptance Time enrichment (submissions.zip + files[])
         │
         ↓
VALUE Unit Normalization (by acceptance_datetime; not period)
         │
         ↓
Amendment State Machine
    ┌────┴────┐
    ↓         ↓
RESTATEMENT  ADD_NEW_HOLDINGS
  REPLACE       MERGE
    └────┬────┘
         ↓
Filing State(t) = LatestBefore(t) [correctly typed]
         │
         ↓
Line-Item Classification
    ┌────┬────┐
    ↓    ↓    ↓
Cash  CALL  PUT
Eq.  Opt.  Opt.
    │
    ↓ (cash equity only beyond this point for M0–M6)
Within-accession discretion-aware sum
         │
         ↓
Shared-ownership graph resolution
         │
         ↓
Cross-accession entity dedup (no .last())
         │
         ↓
De minimis censor flag
         │
         ↓
CUSIP → price mapping (+ delisted_flag)
         │
         ↓
Universe filter (t-date info only)
         │
         ↓
MANAGER × STOCK × QUARTER
         │
    ┌────┴────────────────────────────┐
    ↓                                 ↓
ΔShares (split-adjusted)          ΔValue (unit-normalized)
    └────────────┬────────────────────┘
                 ↓
              M0 signal
              × M1 (HF)
              × M2 (Skill)
              × M3 (Conviction C2 primary)
              ↓ [aggregate to Stock level]
              M4 (Consensus)
              + M5 (Short Interest, 2021-06+)
              → M6 A/B (Crowding Overlay)
```

---

## 11. 模型架构（M0–M6 冻结；不再修改）

*所有模型定义与 v1.4 完全相同。*
*v1.5 只修数据工程；投资逻辑冻结。*

**预注册主规格**（v1.4 已固定；v1.5 不变）:
- **Primary A**: `IC(M4) > IC(M0)`，样本 2013Q3–2026Q1，World B
- **Primary B**: `IC(M5) > IC(M4)`，样本 2021-06–2026Q1，同期对照

---

*矩阵版本 v1.5 — 2026-08-23*
*5 blocking bugs 修复 | Phase 0 = 0.1–0.17 子任务 | CH-1 to CH-13 验收*
*M0–M6 模型架构正式冻结*
*此版本之后 green-light Phase 0 全量下载*
