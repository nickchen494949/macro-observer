# M0 Stage C Part C1 Pilot Discovery Report

> **Status**: `STAGE C PART C1 DISCOVERY UNDER CODEX RE-AUDIT`<br>
> **Generated UTC**: `2026-08-24T07:54:51Z`<br>
> **Total Execution Time**: `105.32s`

---

## 1. Source Database Preflight & Read-Only Safety
- **Source DB File**: `13f_full_4409f14.db` (research/smart_money/phase0/data/13f_full_4409f14.db)
- **File Size**: 25,881,661,440 bytes (24.10 GiB)
- **PRAGMA query_only Verification**: `query_only = 1` (Strict Read-Only)
- **Sidecar Integrity**: Checked zero `-wal`, `-shm`, `-journal` files present.

---

## 2. Evidence A: Berkshire Hathaway 2023Q4 Apple Accession Aggregation

- **Accession Number**: `0000950123-24-002518`
- **Origin Filer CIK**: `0001067983`
- **Period of Report**: `2023-12-31`
- **Acceptance Datetime (PIT)**: `2024-02-14T21:02:18.000Z`
- **Confidential Treatment Flag (`is_confidential_omit`)**: `True`
- **Raw Matching Rows Count**: 12
- **Raw Aggregate Shares Total**: **905,560,000**
- **Raw Aggregate Value Total USD**: $174,347,466,800.0
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

## 3. Evidence B: Point72 2019Q4 Multi-Manager Discovery & v0.8.2 Reconciliation

- **Status**: `PROPOSED PENDING CODEX MANUAL FREEZE`
- **Entity Name**: `Point72 Asset Management`
- **Period of Report**: `2019-12-31`
- **Canonical Entity ID (Numeric-Min CIK)**: `0001599822`
- **Seed CIKs (from `manager_names`)**: `['0001599822', '0001603466', '0001666791', '0001698051', '0001949771', '0001954961', '0002006887', '0002017863']`
- **Graph Closed CIKs (Connected Component)**: `['0001599822', '0001603465', '0001603466', '0001698051']`
- **Total Accessions in Component**: 4
- **Manager Relationships in Component**: 6
- **Total Raw Line Items Across Component**: 4,457
- **On-Time Confidential Filings**: 0 / **All-Period Confidential Filings**: 0
- **On-Time Amendment Filings**: 0 / **All-Period Amendment Filings**: 0
- **Execution Time**: 0.543s

### Source Tables Disambiguation Disclosure
- **Line-Level Sequence Lookup Source**: `OTHERMANAGER2.tsv only` (1566 sequence mappings)
- **Entity Graph Affiliation Edges Source**: `OTHERMANAGER.tsv and OTHERMANAGER2.tsv union` (2283 undirected edges)

### Point72 Policy Comparison: Primary M0 vs ZERO_SENTINEL_EXCLUDED Sensitivity

| Metric / Pipeline Stage | Primary M0 (Empirical Zero Origin) | ZERO_SENTINEL_EXCLUDED (Pre-Aggregation) | Delta |
| :--- | :---: | :---: | :---: |
| **Raw Line Items Count** | 4,457 | 4,457 | 0 |
| **Main Filing (0001567619-20-004063) Raw Rows Retained** | **917** | **0** | -917 |
| **Main Filing Shares Before Dedup** | **418,109,088** | **0** | -418,109,088 |
| **Main Filing Value USD Before Dedup** | **$19,018,144,000** | **$0** | -$19,018,144,000 |
| **Unresolved Rows Count** | 0 | 917 | +917 |
| **Unresolved Shares Total** | 0 | 418,109,088 | +418,109,088 |
| **Reconstructed Disclosures Count** | 4,457 | 3,540 | -917 |
| **Intra-Entity Deduplicated Holdings** | 4,457 | 3,540 | -917 |
| **Total Shares Deduplicated** | **563,789,558** | **145,680,470** | -418,109,088 |
| **Total Value USD Deduplicated** | **$25,013,024,000** | **$5,994,880,000** | -$19,018,144,000 |

### Accessions and Filing Events (Actual PIT Timestamps)

| Accession Number | Filer CIK | Actual Acceptance Datetime | On-Time | Form | Amendment | Conf Omit |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `0001567619-20-004060` | `0001698051` | `2020-02-14T16:42:30.000Z` | YES | 13F-HR | None | NO |
| `0001567619-20-004064` | `0001603465` | `2020-02-14T16:45:49.000Z` | YES | 13F-HR | None | NO |
| `0001567619-20-004066` | `0001599822` | `2020-02-14T16:47:23.000Z` | YES | 13F-HR | None | NO |
| `0001567619-20-004063` | `0001603466` | `2020-02-14T21:44:41.000Z` | YES | 13F-HR | None | NO |

### Manager Relationships & Sequence Mappings (Actual PIT Timestamps)

| Accession Number | Reporter CIK | Seq # | Related CIK | Related Name | Source Table | Actual Acceptance Datetime |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `0001567619-20-004063` | `0001603466` | 32422 | `0001599822` | Point72 Hong Kong Ltd | `OTHERMANAGER.tsv` | `2020-02-14T21:44:41.000Z` |
| `0001567619-20-004063` | `0001603466` | 32423 | `0001698051` | Point72 Europe (London) LLP | `OTHERMANAGER.tsv` | `2020-02-14T21:44:41.000Z` |
| `0001567619-20-004063` | `0001603466` | 32421 | `0001603465` | Cubist Systematic Strategies, LLC | `OTHERMANAGER.tsv` | `2020-02-14T21:44:41.000Z` |
| `0001567619-20-004066` | `0001599822` | 1 | `0001603466` | Point72 Asset Management, L.P. | `OTHERMANAGER2.tsv` | `2020-02-14T16:47:23.000Z` |
| `0001567619-20-004064` | `0001603465` | 1 | `0001603466` | Point72 Asset Management, L.P. | `OTHERMANAGER2.tsv` | `2020-02-14T16:45:49.000Z` |
| `0001567619-20-004060` | `0001698051` | 1 | `0001603466` | Point72 Asset Management, L.P. | `OTHERMANAGER2.tsv` | `2020-02-14T16:42:30.000Z` |

---

## 4. Evidence C: Four Canonical Split Pilot Pairs (Full World-B Pipeline)

| Symbol | CUSIP | Quarter Pair | Split Factor | Ex-Date | Continuous Entities | Raw Median | MAD_log | Adj Median | State | Action | Pass [0.8, 1.2] |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **NVDA** | `67066G104` | 2024-03-31 $\to$ 2024-06-30 | 10.0 | 2024-06-10 | 3169 | 10.021 | 0.0712 | 1.0021 | `KNOWN_SPLIT_PASS` | `INCLUDE` | **PASS** |
| **TSLA** | `88160R101` | 2022-06-30 $\to$ 2022-09-30 | 3.0 | 2022-08-25 | 1694 | 3.0 | 0.0436 | 1.0 | `KNOWN_SPLIT_PASS` | `INCLUDE` | **PASS** |
| **AMZN** | `023135106` | 2022-03-31 $\to$ 2022-06-30 | 20.0 | 2022-06-06 | 2776 | 20.2309 | 0.0595 | 1.0115 | `KNOWN_SPLIT_PASS` | `INCLUDE` | **PASS** |
| **GOOGL** | `02079K305` | 2022-06-30 $\to$ 2022-09-30 | 20.0 | 2022-07-18 | 2409 | 20.0 | 0.035 | 1.0 | `KNOWN_SPLIT_PASS` | `INCLUDE` | **PASS** |

### Before vs After Entity Graph G(Q-1, Q) Impact Comparison

The table below contrasts the naive filer grouping against the true $G(Q-1, Q)$ entity connected components and filing members equality gate:

| Symbol | Naive Filer Grouping N | True Graph $G(Q-1, Q)$ N | Delta N (%) | Raw Median | Adj Median | State | Pass [0.8, 1.2] |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **NVDA** | 3,366 | 3,169 | -197 (-5.9%) | 10.021 | 1.0021 | `KNOWN_SPLIT_PASS` | **PASS** |
| **TSLA** | 1,831 | 1,694 | -137 (-7.5%) | 3.0 | 1.0 | `KNOWN_SPLIT_PASS` | **PASS** |
| **AMZN** | 2,948 | 2,776 | -172 (-5.8%) | 20.2309 | 1.0115 | `KNOWN_SPLIT_PASS` | **PASS** |
| **GOOGL** | 2,612 | 2,409 | -203 (-7.8%) | 20.0 | 1.0 | `KNOWN_SPLIT_PASS` | **PASS** |

### Component-Level Exclusion Counts Breakdown

| Symbol | Membership Incomplete | Confidential Omission | Amendment Unresolved | New Positions | Exit Positions | Unresolved Ownership Rows (Q-1 / Q) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **NVDA** | 289 | 27 | 0 | 263 | 97 | 779 / 795 |
| **TSLA** | 171 | 46 | 0 | 179 | 81 | 657 / 637 |
| **AMZN** | 222 | 73 | 0 | 121 | 223 | 1129 / 1005 |
| **GOOGL** | 217 | 59 | 1 | 133 | 125 | 954 / 865 |

### Global Dataset Context

| Symbol | Q-1 On-Time Filers | Q On-Time Filers | Late Filings (Q-1 / Q) | Graph Connected Components | On-Time Relationship Edges |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **NVDA** | 7,130 | 7,118 | 605 / 599 | 6,601 | 2,752 |
| **TSLA** | 6,613 | 6,524 | 570 / 633 | 6,119 | 2,487 |
| **AMZN** | 6,586 | 6,613 | 668 / 570 | 6,152 | 2,429 |
| **GOOGL** | 6,613 | 6,524 | 570 / 633 | 6,119 | 2,487 |

---

## 5. Real-Data Assumption Discovery: Multi-Manager Sequences and Free-Text Manager Names

Under Contract v0.8.2, `resolve_ownership` resolves single integer sequence numbers strictly against `OTHERMANAGER2.tsv` and treats blank/N-A/exact-0 as origin sentinels. Numeric multi-sequence lists (e.g. `'1,2,4,11'`, `'1 3 4'`) and free-text manager names (e.g. `'Blue Chip Partners LLC'`, `'PARAMETRIC PORTFOLIO ASSOCIATES LLC'`) remain unresolved and excluded from Primary M0.

| Target Symbol / Filing | Q-1 Multi-Seq Rows | Q Multi-Seq Rows | Q-1 Free-Text Rows | Q Free-Text Rows | Sample Values |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Berkshire Apple 2023Q4** | 11 | N/A | 0 | N/A | `1,2,4,11, 2,4,11, 4,5` |
| **NVDA** | 210 | 211 | 214 | 217 | `1, 2, 1,3, 1,3` |
| **TSLA** | 147 | 133 | 270 | 270 | `1,2, 1 2 3, 5 6` |
| **AMZN** | 203 | 209 | 527 | 421 | `1,2,5, 1,2,3, 1,2,3` |
| **GOOGL** | 236 | 185 | 361 | 360 | `1,2, 1,2,5, 1,2,3` |

> **Impact Analysis**: Under Contract v0.8.2, multi-sequence strings, free-text names, and unmapped sequences are conservatively treated as unresolved ownership and excluded from Primary M0 without silent fallback.

---

## 6. Honest Audit Boundaries
- **Read-Only Guarantee**: Phase 0 database was accessed strictly via `open_readonly_sqlite(immutable=True)` with `PRAGMA query_only=ON`. Zero writes performed.
- **Zero Network**: No requests were made to OpenFIGI, yfinance, or SEC EDGAR.
- **Status**: Discovery evidence collected; fixtures remain proposed pending Codex independent manual audit and freeze.

---

## 7. C1 Implementation Audit & Contract v0.8.2 Reconciliation
- **Contract Specification**: `CONTRACT.md` v0.8.2 (Canonical Frozen Amended Specification).
- **Audit Status**: `STAGE C PART C1 DISCOVERY UNDER CODEX RE-AUDIT`.
- **Point72 Retained Rows (Primary)**: All 917 `DFND` / `'0'` rows retained in Primary M0, totaling 418,109,088 shares and $19,018,144,000 USD before deduplication.
- **Point72 Zero-Excluded Sensitivity**: Upstream pre-aggregation exclusion drops exactly the 917 main rows.
- **Disambiguation Proven**: Line sequence resolution queries strictly `source_table = 'OTHERMANAGER2.tsv'`; graph connected components union valid on-time edges from both `OTHERMANAGER.tsv` and `OTHERMANAGER2.tsv`.
- **Split Anchors**: All four canonical split stocks (NVDA, TSLA, AMZN, GOOGL) achieve adjusted medians in `[0.8, 1.2]` under full $G(Q-1, Q)$ graph components.
