# Stage C Part C1 Pilot Discovery Audit Report

**Status**: STAGE C PART C1 DISCOVERY UNDER CODEX AUDIT
**Execution Timestamp (UTC)**: 2026-08-24T06:40:56Z
**Total Runtime**: 104.299 seconds

---

## 1. Database Preflight & Storage Integrity

- **Source DB Path**: `research/smart_money/phase0/data/13f_full_4409f14.db`
- **Database File Size**: 25,881,661,440 bytes (24.10 GiB)
- **Immutable Open Guard**: Verified (zero sibling sidecars)
- **PRAGMA query_only**: 1 (read-only enforced)

---

## 2. Evidence A: Berkshire Hathaway 2023Q4 Apple Accession Aggregation

- **Accession Number**: `0000950123-24-002518`
- **Origin Filer CIK**: `0001067983`
- **Period of Report**: `2023-12-31`
- **Acceptance Datetime**: `2024-02-14T21:02:18.000Z`
- **Confidential Omission Flag**: `is_confidential_omit = True`
- **Raw Matching Line Items**: 12
- **Raw Aggregate Shares**: **905,560,000** (Validates official SEC anchor)
- **Preregistered Expected Anchor**: **905,560,000**
- **Raw Anchor Match**: **EXACT MATCH (100%)**

### Primary Eligibility Assessment
- **Primary Eligible**: **NO (EXCLUDED)**
- **Resolved Primary Shares**: 0
- **Unresolved Rows Count**: 12 / 12
- **Unresolved Shares Total**: 905,560,000
- **Multi-Sequence (`other_manager` lists) Rows**: 11
- **Ineligibility Reasons**:
  - `CONFIDENTIAL_TREATMENT_OMISSION (is_confidential_omit=1)`
  - `ALL_ROWS_UNRESOLVED_OTHER_MANAGER (missing manager_relationships mappings)`

### Raw Matching Line Items Breakdown

| Line Seq | Security Name | Shares | Value USD | Discretion | Other Mgr | Multi-Seq | Resolved Owner | Unresolved |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 11 | APPLE INC | 692,000 | $133,230,760 | DFND | 4 | NO | `None` | YES |
| 12 | APPLE INC | 3,840,000 | $739,315,200 | DFND | 1,2,4,11 | YES | `None` | YES |
| 13 | APPLE INC | 24,294,000 | $4,677,323,820 | DFND | 2,4,11 | YES | `None` | YES |
| 14 | APPLE INC | 59,147,916 | $11,387,748,267 | DFND | 4,5 | YES | `None` | YES |
| 15 | APPLE INC | 2,724,000 | $524,451,720 | DFND | 4,6 | YES | `None` | YES |
| 16 | APPLE INC | 20,424,207 | $3,932,272,574 | DFND | 4,7 | YES | `None` | YES |
| 17 | APPLE INC | 61,542,988 | $11,848,871,480 | DFND | 4,8,11 | YES | `None` | YES |
| 18 | APPLE INC | 12,152,000 | $2,339,624,560 | DFND | 4,5,9 | YES | `None` | YES |
| 19 | APPLE INC | 47,832,000 | $9,209,094,960 | DFND | 4,10 | YES | `None` | YES |
| 20 | APPLE INC | 666,422,889 | $128,306,398,819 | DFND | 4,11 | YES | `None` | YES |
| 21 | APPLE INC | 2,712,000 | $522,141,360 | DFND | 4,12 | YES | `None` | YES |
| 22 | APPLE INC | 3,776,000 | $726,993,280 | DFND | 4,14 | YES | `None` | YES |

---

## 3. Evidence B: Point72 2019Q4 Multi-Manager Discovery (Proposed Fixture)

- **Status**: `PROPOSED PENDING CODEX MANUAL FREEZE`
- **Entity Name**: `Point72 Asset Management`
- **Period of Report**: `2019-12-31`
- **Canonical Entity ID (Numeric-Min CIK)**: `0001599822`
- **Seed CIKs (from `manager_names`)**: `['0001599822', '0001603466', '0001666791', '0001698051', '0001949771', '0001954961', '0002006887', '0002017863']`
- **Graph Closed CIKs (Connected Component)**: `['0001599822', '0001603465', '0001603466', '0001698051', '1599822', '1603465', '1603466', '1698051']`
- **Total Accessions in Component**: 4
- **Manager Relationships in Component**: 6
- **Total Raw Line Items**: 4,457
- **Reconstructed Disclosures**: 3,540
- **Intra-Entity Deduplicated Holdings**: 3,540
- **Execution Time**: 0.482s

### Accessions and Filing Events (Actual PIT Timestamps)

| Accession Number | Filer CIK | Actual Acceptance Datetime | On-Time | Form | Amendment | Conf Omit |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `0001567619-20-004060` | `0001698051` | `2020-02-14T16:42:30.000Z` | YES | 13F-HR | None | NO |
| `0001567619-20-004064` | `0001603465` | `2020-02-14T16:45:49.000Z` | YES | 13F-HR | None | NO |
| `0001567619-20-004066` | `0001599822` | `2020-02-14T16:47:23.000Z` | YES | 13F-HR | None | NO |
| `0001567619-20-004063` | `0001603466` | `2020-02-14T21:44:41.000Z` | YES | 13F-HR | None | NO |

### Manager Relationships & Sequence Mappings (Actual PIT Timestamps)

| Accession Number | Reporter CIK | Seq # | Related CIK | Related Name | Actual Acceptance Datetime |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `0001567619-20-004063` | `0001603466` | 32422 | `0001599822` | Point72 Hong Kong Ltd | `2020-02-14T21:44:41.000Z` |
| `0001567619-20-004063` | `0001603466` | 32423 | `0001698051` | Point72 Europe (London) LLP | `2020-02-14T21:44:41.000Z` |
| `0001567619-20-004063` | `0001603466` | 32421 | `0001603465` | Cubist Systematic Strategies, LLC | `2020-02-14T21:44:41.000Z` |
| `0001567619-20-004066` | `0001599822` | 1 | `0001603466` | Point72 Asset Management, L.P. | `2020-02-14T16:47:23.000Z` |
| `0001567619-20-004064` | `0001603465` | 1 | `0001603466` | Point72 Asset Management, L.P. | `2020-02-14T16:45:49.000Z` |
| `0001567619-20-004060` | `0001698051` | 1 | `0001603466` | Point72 Asset Management, L.P. | `2020-02-14T16:42:30.000Z` |

---

## 4. Evidence C: Four Canonical Split Pilot Pairs (Full World-B Pipeline)

| Symbol | CUSIP | Quarter Pair | Split Factor | Ex-Date | Continuous Entities | Raw Median | MAD_log | Adj Median | State | Action | Pass [0.8, 1.2] |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **NVDA** | `67066G104` | 2024-03-31 $\to$ 2024-06-30 | 10.0 | 2024-06-10 | 2730 | 10.01 | 0.0718 | 1.0015 | `KNOWN_SPLIT_PASS` | `INCLUDE` | **PASS** |
| **TSLA** | `88160R101` | 2022-06-30 $\to$ 2022-09-30 | 3.0 | 2022-08-25 | 1445 | 3.00 | 0.0420 | 1.0000 | `KNOWN_SPLIT_PASS` | `INCLUDE` | **PASS** |
| **AMZN** | `023135106` | 2022-03-31 $\to$ 2022-06-30 | 20.0 | 2022-06-06 | 2417 | 20.23 | 0.0593 | 1.0113 | `KNOWN_SPLIT_PASS` | `INCLUDE` | **PASS** |
| **GOOGL** | `02079K305` | 2022-06-30 $\to$ 2022-09-30 | 20.0 | 2022-07-18 | 2068 | 20.00 | 0.0350 | 1.0000 | `KNOWN_SPLIT_PASS` | `INCLUDE` | **PASS** |

### Before vs After Entity Graph G(Q-1, Q) Impact Comparison

The table below contrasts the naive filer grouping against the true $G(Q-1, Q)$ entity connected components and filing members equality gate:

| Symbol | Naive Filer Grouping N | True Graph $G(Q-1, Q)$ N | Delta N (%) | Raw Median | Adj Median | State | Pass [0.8, 1.2] |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **NVDA** | 3,366 | 2,730 | -636 (-18.9%) | 10.01 | 1.0015 | `KNOWN_SPLIT_PASS` | **PASS** |
| **TSLA** | 1,831 | 1,445 | -386 (-21.1%) | 3.00 | 1.0000 | `KNOWN_SPLIT_PASS` | **PASS** |
| **AMZN** | 2,948 | 2,417 | -531 (-18.0%) | 20.23 | 1.0113 | `KNOWN_SPLIT_PASS` | **PASS** |
| **GOOGL** | 2,612 | 2,068 | -544 (-20.8%) | 20.00 | 1.0000 | `KNOWN_SPLIT_PASS` | **PASS** |

### Component-Level Exclusion Counts Breakdown

| Symbol | Membership Incomplete | Confidential Omission | Amendment Unresolved | New Positions | Exit Positions | Unresolved Ownership Rows (Q-1 / Q) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **NVDA** | 240 | 24 | 1 | 250 | 114 | 1331 / 1426 |
| **TSLA** | 147 | 35 | 0 | 174 | 94 | 1061 / 1056 |
| **AMZN** | 196 | 59 | 0 | 121 | 216 | 1496 / 1570 |
| **GOOGL** | 195 | 49 | 1 | 133 | 133 | 1326 / 1201 |

### Global Dataset Context

| Symbol | Q-1 On-Time Filers | Q On-Time Filers | Late Filings (Q-1 / Q) | Graph Connected Components | On-Time Relationship Edges |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **NVDA** | 8,785 | 8,798 | 672 / 675 | 6,898 | 4,451 |
| **TSLA** | 8,288 | 8,179 | 630 / 698 | 6,438 | 4,036 |
| **AMZN** | 8,250 | 8,288 | 755 / 630 | 6,483 | 3,981 |
| **GOOGL** | 8,288 | 8,179 | 630 / 698 | 6,438 | 4,036 |

---

## 5. Real-Data Assumption Discovery: Multi-Manager Comma-Separated Sequences

Under the frozen Contract v0.8.1 specification, `resolve_ownership` resolves single integer sequence numbers against `manager_relationships`. In real SEC 13F filings, filers frequently supply comma-separated lists of sequence numbers (e.g. `'1,2,4,11'` or `'4,5'`) in the `other_manager` field.

| Target Symbol / Filing | Q-1 Multi-Seq Rows | Q Multi-Seq Rows | Sample Multi-Sequence Values |
| :--- | :--- | :--- | :--- |
| **Berkshire Apple 2023Q4** | 11 | N/A | `1,2,4,11, 2,4,11, 4,5` |
| **NVDA** | 259 | 264 | `Blue Chip Partners LLC, 1 3 4, 1 4` |
| **TSLA** | 180 | 171 | `Blue Chip Partners LLC, 1 4, 1 3 4` |
| **AMZN** | 223 | 248 | `Blue Chip Partners LLC, 1 4, 1 3 4` |
| **GOOGL** | 271 | 232 | `Blue Chip Partners LLC, 1 3 4, 1 4` |

> **Impact Analysis**: Under existing frozen rules, multi-sequence strings are conservatively treated as unresolved ownership and excluded from Primary M0. They are neither silently attributed to origin filers nor artificially split across managers. This discovery is surfaced for Codex and user consideration.

---

## 6. Honest Audit Boundaries
- **Read-Only Guarantee**: Phase 0 database was accessed strictly via `open_readonly_sqlite(immutable=True)` with `PRAGMA query_only=ON`. Zero writes performed.
- **Zero Network**: No requests were made to OpenFIGI, yfinance, or SEC EDGAR.
- **Status**: Discovery evidence collected; fixtures remain proposed pending Codex independent manual audit and freeze.
