# Stage C1 Technical Discovery Memo: Form 13F Column 7 `<otherManager>0` Sentinel & Source Table Disambiguation

> **Date**: 2026-08-24
> **Status**: `BLOCKED PENDING CONTRACT AMENDMENT DECISION`
> **Target Module**: `research/smart_money/m0/`
> **Related Contract**: Proposed Amendment to `CONTRACT.md` (v0.8.1 $\to$ v0.8.2)
> **Author**: Antigravity M0 Implementation Engine

---

## 1. Executive Summary

During Stage C Part C1 discovery on Point72 2019Q4 multi-manager accession `0001567619-20-004063` (Point72 Asset Management, L.P., CIK `0001603466`), independent verification against official SEC filings and the underlying SEC raw TSV datasets revealed a critical contract-level data modeling issue:

1. **Origin-Owner Sentinel `<otherManager>0`**: Point72's main filing contains exactly **917 line items**, all having `other_manager = '0'` representing **418,109,088 shares** ($19,018,144,000 value). Under the current frozen Contract v0.8.1 rule, `'0'` is treated as an unrecognized integer sequence number, causing **100% of Point72 main holdings to be marked unresolved and discarded**, preventing verification of Point72 cross-CIK exact-signature deduplication.
2. **SEC Source Table Semantic Collision**: In the SEC Form 13F dataset, `OTHERMANAGER.tsv` contains `OTHERMANAGER_SK` (an internal SEC surrogate key), whereas `OTHERMANAGER2.tsv` contains `SEQUENCENUMBER` (the actual Form 13F Summary Page sequence number corresponding to Column 7). In Phase 0 DB, `manager_relationships` ingests rows from both tables. Attempting to resolve line-level sequence numbers against `OTHERMANAGER.tsv` causes lookup failures or invalid mappings.
3. **Dataset-Wide Prevalence**: An audit of all line items across the four canonical split pilot stocks (NVDA, TSLA, AMZN, GOOGL) demonstrates that `0` is used in **7.7% to 10.0%** of all filing rows, and `N/A` / `NONE` sentinels account for **2.4% to 2.5%**. Together with blank/null fields, **72% to 75%** of all 13F line items represent direct origin-filer sole discretion.

This memo documents the ground-truth evidence, disambiguates the SEC source tables, provides target-CUSIP distribution statistics, and proposes a formal, conservative **Contract v0.8.2 amendment** for Codex review and user decision.

---

## 2. Ground-Truth Evidence from Source Zero

### A. Official SEC EDGAR XML Filing Evidence
- **Official SEC URL**: [https://www.sec.gov/Archives/edgar/data/1603466/000156761920004063/form13fInfoTable.xml](https://www.sec.gov/Archives/edgar/data/1603466/000156761920004063/form13fInfoTable.xml)
- **Accession**: `0001567619-20-004063` (Point72 Asset Management, L.P., CIK `0001603466`)
- **Period of Report**: `2019-12-31`
- **Filing Date / Acceptance**: `2020-02-14T21:44:41.000Z`
- **XML Tag Verification**:
  Every `<infoTable>` element in this official SEC XML filing contains `<otherManager>0</otherManager>`. For example:
  ```xml
  <infoTable>
    <nameOfIssuer>AGILENT TECHNOLOGIES INC</nameOfIssuer>
    <titleOfClass>COM</titleOfClass>
    <cusip>00846U101</cusip>
    <value>18420</value>
    <shrsOrPrnAmt>
      <sshPrnamt>215919</sshPrnamt>
      <sshPrnamtType>SH</sshPrnamtType>
    </shrsOrPrnAmt>
    <investmentDiscretion>SOLE</investmentDiscretion>
    <otherManager>0</otherManager>
    <votingAuthority>
      <Sole>215919</Sole>
      <Shared>0</Shared>
      <None>0</None>
    </votingAuthority>
  </infoTable>
  ```
- **Total Occurrences**: Exactly **917** occurrences of `<otherManager>0`.

### B. SEC Raw Dataset Ingest Verification (`2020q1.zip`)
- **File Location**: `research/smart_money/phase0/data/zips/2020q1.zip`
- **Metadata Documentation (`FORM13F_readme.htm`)**:
  - `INFOTABLE.tsv`: Contains field `OTHRMANAGER` defined as *"The sequence number of another manager sharing investment discretion"*.
  - `OTHERMANAGER.tsv`: Contains field `OTHERMANAGER_SK` defined by SEC as an internal surrogate key assigned to manager relationships.
  - `OTHERMANAGER2.tsv`: Contains field `SEQUENCENUMBER` defined by SEC as the 1-based sequence number assigned to other included managers on the Summary Page of Form 13F.
- **Official SEC Form 13F FAQ Guidance**:
  - [SEC Form 13F FAQs (Questions 48 & 49)](https://www.sec.gov/divisions/investment/13ffaq): Column 7 is designated for another manager sequence number when investment discretion is shared. When investment discretion is not shared (or sole to the origin filer), filers leave Column 7 blank or enter `N/A`, `NONE`, or `0` (used by common filing software packages such as Workiva / Merrill Bridge).

### C. SQLite Phase 0 DB Verification Query & Results
Query executed against `research/smart_money/phase0/data/13f_full_4409f14.db` (read-only immutable):

```sql
-- 1. Point72 Main Filing Line Items Breakdown
SELECT other_manager, COUNT(*) AS row_count, SUM(sshprnamt) AS total_shares, SUM(value_usd) AS total_value
FROM filing_line_items
WHERE accession_number = '0001567619-20-004063'
GROUP BY other_manager;
```

**Result**:
| `other_manager` | Row Count | Total Shares | Total Value USD |
| :--- | :---: | :---: | :---: |
| `'0'` | **917** | **418,109,088** | **$19,018,144,000** |

```sql
-- 2. Point72 Component Manager Relationships Ingestion Source Table Breakdown
SELECT accession_number, reporter_cik, related_cik, sequence_number, source_table
FROM manager_relationships
WHERE accession_number IN (
    '0001567619-20-004063', '0001567619-20-004060', '0001567619-20-004064', '0001567619-20-004066'
)
ORDER BY accession_number, source_table, sequence_number;
```

**Result**:
| Accession Number | Reporter CIK | Related CIK | Sequence Number | Source Table | Semantic Role |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `0001567619-20-004060` | `1698051` (Europe) | `1603466` (Main) | `1` | `OTHERMANAGER2.tsv` | Line-Level Column 7 Sequence |
| `0001567619-20-004064` | `1603465` (Cubist) | `1603466` (Main) | `1` | `OTHERMANAGER2.tsv` | Line-Level Column 7 Sequence |
| `0001567619-20-004066` | `1599822` (HK) | `1603466` (Main) | `1` | `OTHERMANAGER2.tsv` | Line-Level Column 7 Sequence |
| `0001567619-20-004063` | `1603466` (Main) | `1603465` (Cubist) | `32421` | `OTHERMANAGER.tsv` | Surrogate Key (`SK`), NOT Column 7 |
| `0001567619-20-004063` | `1603466` (Main) | `1599822` (HK) | `32422` | `OTHERMANAGER.tsv` | Surrogate Key (`SK`), NOT Column 7 |
| `0001567619-20-004063` | `1603466` (Main) | `1698051` (Europe) | `32423` | `OTHERMANAGER.tsv` | Surrogate Key (`SK`), NOT Column 7 |

---

## 3. Disambiguation: `OTHERMANAGER.tsv` vs `OTHERMANAGER2.tsv`

### Fact vs Inference Summary
- **Observed Fact**: In SEC 13F dataset raw files, `OTHERMANAGER2.tsv` contains the small integer sequence numbers (`1`, `2`, `3`, etc.) that match the `OTHRMANAGER` Column 7 in `INFOTABLE.tsv`. `OTHERMANAGER.tsv` contains large 5-digit surrogate keys (`OTHERMANAGER_SK`, e.g. `32421`, `32422`).
- **Observed Fact**: In Point72's main filing `0001567619-20-004063`, Point72 lists its subsidiaries on the cover/summary page, generating surrogate keys in `OTHERMANAGER.tsv`. However, for its 917 holding line items, Point72 enters `<otherManager>0`, indicating sole discretion.
- **Inference**: Filers using automated software that outputs `0` for sole discretion intend to attribute the holding to the origin reporting manager (`origin_filer_cik`), exactly identical to a blank or `NULL` entry.

### Architectural Disambiguation Rule
To prevent data contamination and lookup failure:
1. **Graph Edges Construction ($G(Q-1, Q)$)**: All valid on-time records from **both** `OTHERMANAGER.tsv` and `OTHERMANAGER2.tsv` represent legitimate entity affiliations and should be unioned to form connected components.
2. **Line-Level Sequence Resolution (`resolve_ownership`)**: Line items in `filing_line_items` reference sequence numbers. Therefore, line-level resolution must **strictly use mappings sourced from `OTHERMANAGER2.tsv`** (`source_table = 'OTHERMANAGER2.tsv'`).

---

## 4. Dataset-Wide Distribution Across Split Pilot Stocks

To verify the scope of this behavior across the entire SEC database, a target-CUSIP query was performed across the four split pilot stocks (`67066G104`, `88160R101`, `023135106`, `02079K305`) in `filing_line_items`.

### Target-CUSIP other_manager Classification Breakdown

| Metric / Category | NVDA (`67066G104`) | TSLA (`88160R101`) | AMZN (`023135106`) | GOOGL (`02079K305`) |
| :--- | :---: | :---: | :---: | :---: |
| **Total Rows Audited** | **194,587** | **148,141** | **272,695** | **217,919** |
| `BLANK_OR_NULL` | 120,094 (61.7%) | 90,514 (61.1%) | 177,661 (65.2%) | 138,258 (63.4%) |
| `ZERO_SENTINEL` (`'0'`) | 17,507 (9.0%) | 14,798 (10.0%) | 20,873 (7.7%) | 17,254 (7.9%) |
| `NA_NONE_SENTINEL` (`N/A`, `NONE`, `NA`) | 4,644 (2.4%) | 3,563 (2.4%) | 6,876 (2.5%) | 5,490 (2.5%) |
| `SINGLE_NUMERIC_SEQ` (`1`, `2`, `4`, etc.) | 41,616 (21.4%) | 31,435 (21.2%) | 53,899 (19.8%) | 45,612 (20.9%) |
| `MULTI_NUMERIC_SEQ` (`1,2,4,11`, `1 3 4`) | 8,623 (4.4%) | 6,167 (4.2%) | 10,795 (4.0%) | 9,284 (4.3%) |
| `FREE_TEXT_NAME` (e.g. `Blue Chip Partners`) | 2,103 (1.1%) | 1,664 (1.1%) | 2,591 (1.0%) | 2,021 (0.9%) |

### Key Observations:
- **Origin-Filer Discretion Sum**: `BLANK_OR_NULL` + `ZERO_SENTINEL` + `NA_NONE_SENTINEL` represents **73.1% (NVDA)**, **73.5% (TSLA)**, **75.4% (AMZN)**, and **73.8% (GOOGL)** of all disclosed positions.
- Treating `'0'` as an unknown manager sequence rather than an origin-owner sentinel needlessly discards ~8% to 10% of valid holdings across all stocks.

---

## 5. Proposed CONTRACT v0.8.2 Specification Amendment

### Proposed Amendment Details (For Review Only - NOT YET APPLIED)

```markdown
### Proposed Amendment: Contract v0.8.1 -> v0.8.2 Section 2.1 (Ownership Resolution)

1. Origin-Owner Sentinels:
   Before resolving sequence numbers against manager relationships, the `other_manager` string
   must be stripped of leading/trailing whitespace.
   The following normalized values are strictly defined as ORIGIN_FILER sentinels:
   - `None` (NULL)
   - `""` (Empty string)
   - `"0"` (Numeric zero)
   - `"N/A"`, `"NA"`, `"NOT APPLICABLE"`, `"NONE"`, `"N / A"` (Case-insensitive)

   When an origin-owner sentinel is detected, `resolve_ownership` returns:
   `(economic_owner_cik = origin_filer_cik, ownership_unresolved = False)`.

2. Line-Level Sequence Number Resolution:
   - Line-level sequence numbers (e.g. `"1"`, `"2"`) must be resolved strictly against
     `manager_relationships` entries where `source_table = 'OTHERMANAGER2.tsv'`.
   - `manager_relationships` entries where `source_table = 'OTHERMANAGER.tsv'` contain surrogate keys
     and MUST NOT be used for line-level sequence lookup.

3. Entity Graph Relationship Closure:
   - Both `OTHERMANAGER.tsv` and `OTHERMANAGER2.tsv` on-time records are unioned to establish
     undirected entity affiliation graph edges G(Q-1, Q).

4. Conservative Preservation:
   - Multi-numeric sequence lists (e.g. `"1,2,4,11"`, `"1 3 4"`) and free-text manager names
     (e.g. `"Blue Chip Partners LLC"`) remain strictly UNRESOLVED (excluded from Primary M0).
```

---

## 6. Decision Table & Trade-Off Analysis

| Option | Description | Pros | Cons / Risks | Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| **Option A (Amend to v0.8.2)** | Adopt origin sentinels (`0`, `N/A`, `NONE`) and restrict sequence lookup to `OTHERMANAGER2.tsv`. | • Point72 main filing (917 rows) successfully retained.<br>• Reconstructs full Point72 intra-entity deduplication.<br>• Restores ~9% valid holdings in split benchmarks. | Requires formal contract version bump and regression test suite expansion. | **RECOMMENDED** |
| **Option B (Maintain v0.8.1)** | Keep `0` treated as unknown sequence number. Discard Point72 main accession. | • Zero contract changes.<br>• Simplest specification. | • Point72 main accession 100% discarded.<br>• Fails Stage C plan requirement for cross-CIK deduplication fixture.<br>• Unnecessarily drops 9% of SEC dataset. | **REJECT** |

---

## 7. Action Plan if Contract v0.8.2 is Approved

If the user / Codex approves Contract v0.8.2:
1. Update `CONTRACT.md` and `IMPLEMENTATION_PLAN.md` to v0.8.2.
2. Update `resolve_ownership` in `ownership_state_machine.py` to handle origin sentinels (`0`, `N/A`, `NONE`).
3. Update `pilot_extractor.py` to filter line-level `rel_map` by `source_table = 'OTHERMANAGER2.tsv'`.
4. Add regression tests in `test_stage_a_pure_functions.py`, `test_stage_b_counterexamples.py`, and `test_stage_c1_pilot_extractor.py`.
5. Rerun the full 76+ test suite and rerun real-data `run_full_c1_discovery` against Phase 0 DB.
6. Regenerate `STAGE_C1_DISCOVERY.json` and `STAGE_C_DISCOVERY.md` with fully deduplicated Point72 holdings.

---

## 8. Current Working State
- **Current Branch**: `agent/phase4-composite-validation`
- **Current Status**: `BLOCKED PENDING CONTRACT AMENDMENT DECISION`
- **Local Tree**: Clean (all code, tests, and artifacts from `36191f3` remain untouched).
