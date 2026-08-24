# Stage C Part C1 Pilot Discovery Audit Report

**Status**: STAGE C PART C1 DISCOVERY UNDER CODEX AUDIT
**Execution Timestamp (UTC)**: 2026-08-24T06:30:59Z
**Total Runtime**: 104.826 seconds

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
- **Raw Matching Line Items**: 12
- **Aggregated Total Shares**: **905,560,000**
- **Preregistered Expected Anchor**: **905,560,000**
- **Exact Match Status**: **EXACT MATCH (100%)**
- **Execution Time**: 0.004s

### Raw Matching Line Items Breakdown

| Line Seq | Security Name | Shares | Value USD | Discretion | Other Mgr | Sole Vote | Shared Vote | None Vote |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 11 | APPLE INC | 692,000 | $133,230,760 | DFND | 4 | 692,000 | 0 | 0 |
| 12 | APPLE INC | 3,840,000 | $739,315,200 | DFND | 1,2,4,11 | 3,840,000 | 0 | 0 |
| 13 | APPLE INC | 24,294,000 | $4,677,323,820 | DFND | 2,4,11 | 24,294,000 | 0 | 0 |
| 14 | APPLE INC | 59,147,916 | $11,387,748,267 | DFND | 4,5 | 59,147,916 | 0 | 0 |
| 15 | APPLE INC | 2,724,000 | $524,451,720 | DFND | 4,6 | 2,724,000 | 0 | 0 |
| 16 | APPLE INC | 20,424,207 | $3,932,272,574 | DFND | 4,7 | 20,424,207 | 0 | 0 |
| 17 | APPLE INC | 61,542,988 | $11,848,871,480 | DFND | 4,8,11 | 61,542,988 | 0 | 0 |
| 18 | APPLE INC | 12,152,000 | $2,339,624,560 | DFND | 4,5,9 | 12,152,000 | 0 | 0 |
| 19 | APPLE INC | 47,832,000 | $9,209,094,960 | DFND | 4,10 | 47,832,000 | 0 | 0 |
| 20 | APPLE INC | 666,422,889 | $128,306,398,819 | DFND | 4,11 | 666,422,889 | 0 | 0 |
| 21 | APPLE INC | 2,712,000 | $522,141,360 | DFND | 4,12 | 2,712,000 | 0 | 0 |
| 22 | APPLE INC | 3,776,000 | $726,993,280 | DFND | 4,14 | 3,776,000 | 0 | 0 |

---

## 3. Evidence B: Point72 2019Q4 Multi-Manager Discovery (Proposed Fixture)

- **Status**: `PROPOSED PENDING CODEX MANUAL FREEZE`
- **Entity Name**: `Point72 Asset Management`
- **Period of Report**: `2019-12-31`
- **Canonical Entity ID (Numeric-Min CIK)**: `0001599822`
- **Total Accessions Found**: 4
- **Manager Relationships Found**: 6
- **Total Raw Line Items**: 4,457
- **Reconstructed Disclosures**: 3,540
- **Intra-Entity Deduplicated Holdings**: 3,540
- **Execution Time**: 0.182s

### Accessions and Filing Events

| Accession Number | Filer CIK | Manager Name | Acceptance Time | On-Time | Form |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `0001567619-20-004060` | `0001698051` | Point72 Europe (London) LLP | `2020-02-14T16:42:30.000Z` | YES | 13F-HR |
| `0001567619-20-004066` | `0001599822` | Point72 Asia (Hong Kong) Ltd | `2020-02-14T16:47:23.000Z` | YES | 13F-HR |
| `0001567619-20-004063` | `0001603466` | Point72 Asset Management, L.P. | `2020-02-14T21:44:41.000Z` | YES | 13F-HR |
| `0001567619-20-004064` | `0001603465` | Cubist Systematic Strategies, LLC | `2020-02-14T16:45:49.000Z` | YES | 13F-HR |

### Manager Relationships & Sequence Mappings

| Accession Number | Reporter CIK | Seq # | Related CIK | Related Name | Source |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `0001567619-20-004060` | `0001698051` | 1 | `0001603466` | Point72 Asset Management, L.P. | OTHERMANAGER2.tsv |
| `0001567619-20-004063` | `0001603466` | 32421 | `0001603465` | Cubist Systematic Strategies, LLC | OTHERMANAGER.tsv |
| `0001567619-20-004063` | `0001603466` | 32422 | `0001599822` | Point72 Hong Kong Ltd | OTHERMANAGER.tsv |
| `0001567619-20-004063` | `0001603466` | 32423 | `0001698051` | Point72 Europe (London) LLP | OTHERMANAGER.tsv |
| `0001567619-20-004064` | `0001603465` | 1 | `0001603466` | Point72 Asset Management, L.P. | OTHERMANAGER2.tsv |
| `0001567619-20-004066` | `0001599822` | 1 | `0001603466` | Point72 Asset Management, L.P. | OTHERMANAGER2.tsv |

---

## 4. Evidence C: Four Canonical Split Pilot Pairs (Full Pipeline)

| Symbol | CUSIP | Quarter Pair | Split Factor | Ex-Date | Continuous Entities | Raw Median | MAD_log | Adj Median | State | Action | Pass [0.8, 1.2] |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **NVDA** | `67066G104` | 2024-03-31 $\to$ 2024-06-30 | 10.0 | 2024-06-10 | 3366 | 10.00 | 0.0746 | 1.0000 | `KNOWN_SPLIT_PASS` | `INCLUDE` | **PASS** |
| **TSLA** | `88160R101` | 2022-06-30 $\to$ 2022-09-30 | 3.0 | 2022-08-25 | 1831 | 3.00 | 0.0488 | 1.0000 | `KNOWN_SPLIT_PASS` | `INCLUDE` | **PASS** |
| **AMZN** | `023135106` | 2022-03-31 $\to$ 2022-06-30 | 20.0 | 2022-06-06 | 2948 | 20.19 | 0.0619 | 1.0094 | `KNOWN_SPLIT_PASS` | `INCLUDE` | **PASS** |
| **GOOGL** | `02079K305` | 2022-06-30 $\to$ 2022-09-30 | 20.0 | 2022-07-18 | 2612 | 20.00 | 0.0357 | 1.0000 | `KNOWN_SPLIT_PASS` | `INCLUDE` | **PASS** |

### Split Pipeline Exclusion Breakdown

| Symbol | Late Filings (Q-1 / Q) | Unresolved Ownership Rows | Membership Incomplete Entities | Confidential Omission Entities | New Positions | Exit Positions |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **NVDA** | 672 / 675 | 1331 / 1426 | 33 | 38 | 435 | 284 |
| **TSLA** | 630 / 698 | 1061 / 1056 | 5 | 47 | 273 | 209 |
| **AMZN** | 755 / 630 | 1496 / 1570 | 30 | 77 | 248 | 365 |
| **GOOGL** | 630 / 698 | 1326 / 1201 | 17 | 68 | 241 | 277 |

> **Note on GOOGL**: The CONTRACT SEC 8-K document states the 20:1 stock split ratio, but does not explicitly mention the July 18, 2022 ex-dividend trading date, which is supplied from vendor ledger conventions.

---

## 5. Honest Audit Boundaries
- **Read-Only Guarantee**: Phase 0 database was accessed strictly via `open_readonly_sqlite(immutable=True)` with `PRAGMA query_only=ON`. Zero writes performed.
- **Zero Network**: No requests were made to OpenFIGI, yfinance, or SEC EDGAR.
- **Status**: Discovery evidence collected; fixtures remain proposed pending Codex independent manual audit and freeze.
