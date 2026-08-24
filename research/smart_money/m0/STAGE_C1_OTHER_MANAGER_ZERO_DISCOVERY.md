# Stage C1 Technical Discovery Memo: Form 13F Column 7 `<otherManager>0` Sentinel & Source Table Disambiguation

> **Date**: 2026-08-24
> **Status**: `APPROVED FOR CONTRACT v0.8.2 / IMPLEMENTATION PENDING`
> **Target Module**: `research/smart_money/m0/`
> **Related Contract**: `CONTRACT.md` (Amended to v0.8.2)
> **Scope**: Pure Technical Memo & Formal Governance Decision Record

---

## 1. Executive Summary & Objective

During Stage C Part C1 pilot discovery against `research/smart_money/phase0/data/13f_full_4409f14.db` (read-only immutable), independent audit and verification against official SEC EDGAR XML filings revealed an important data-modeling blocker in SEC Form 13F Column 7 (`other_manager`):

1. **Empirical Sentinel `<otherManager>0` in Point72 Main Filing**: Point72 Asset Management, L.P. (CIK `0001603466`) in accession `0001567619-20-004063` has exactly **917 line items**, all having `INVESTMENTDISCRETION = 'DFND'` and `other_manager = '0'`, totaling **418,109,088 shares** and **$19,018,144,000 USD** in value. Under Contract v0.8.1, `'0'` is treated as an unknown integer sequence number, causing **100% of Point72 main holdings to be marked unresolved and discarded**, preventing verification of Point72 cross-CIK exact-signature deduplication.
2. **SEC Source Table Collision**: In SEC raw 13F datasets, `OTHERMANAGER.tsv` uses `OTHERMANAGER_SK` (internal surrogate keys), whereas `OTHERMANAGER2.tsv` uses `SEQUENCENUMBER` (1-based sequence numbers corresponding to Column 7). `manager_relationships` ingests rows from both. Attempting to resolve line-level sequence numbers against `OTHERMANAGER.tsv` causes lookup failures.
3. **Strict Fact vs. Inference Framework**: This memo strictly separates observed empirical facts from architectural inferences, presents reproducible target-CUSIP classification distributions and accession coexistence statistics, and establishes the formal **Contract v0.8.2 amendment**.

---

## 2. Ground-Truth Verification from Source Zero

### A. Official SEC EDGAR XML Evidence
- **Official SEC URL**: [https://www.sec.gov/Archives/edgar/data/1603466/000156761920004063/form13fInfoTable.xml](https://www.sec.gov/Archives/edgar/data/1603466/000156761920004063/form13fInfoTable.xml)
- **Accession**: `0001567619-20-004063` (Point72 Asset Management, L.P., CIK `0001603466`)
- **Period of Report**: `2019-12-31` (Filing Date: `2020-02-14`)
- **Observed XML Structure** (Example: CHEWY INC line item):
  ```xml
  <infoTable>
    <nameOfIssuer>CHEWY INC</nameOfIssuer>
    <titleOfClass>CL A</titleOfClass>
    <cusip>16679L109</cusip>
    <value>6011</value>
    <shrsOrPrnAmt>
      <sshPrnamt>207260</sshPrnamt>
      <sshPrnamtType>SH</sshPrnamtType>
    </shrsOrPrnAmt>
    <investmentDiscretion>DFND</investmentDiscretion>
    <otherManager>0</otherManager>
    <votingAuthority>
      <Sole>0</Sole>
      <Shared>207260</Shared>
      <None>0</None>
    </votingAuthority>
  </infoTable>
  ```
- **Observed Fact**: All 917 `<infoTable>` elements in this filing contain `<investmentDiscretion>DFND</investmentDiscretion>` and `<otherManager>0</otherManager>` with shared voting authority matching the reported share count.
- **Official Regulatory Guidance Fact**: [SEC Form 13F FAQs (Questions 48 & 49)](https://www.sec.gov/divisions/investment/13ffaq) state that Column 7 is a numbered link to an included manager on the Summary Page; if inapplicable, filers should leave it blank or enter `N/A`. The official SEC FAQ does not explicitly authorize `0` or `NONE`.

### B. Full Phase 0 Database Evidence on `manager_relationships`

Executing read-only queries against `research/smart_money/phase0/data/13f_full_4409f14.db`:

```sql
-- Query 1: Point72 Main Accession Line Item Aggregation
SELECT investment_discretion, other_manager, COUNT(*) AS row_cnt, SUM(sshprnamt) AS total_shrs, SUM(value_usd) AS total_val
FROM filing_line_items
WHERE accession_number = '0001567619-20-004063'
GROUP BY investment_discretion, other_manager;
```
**Output**:
| `investment_discretion` | `other_manager` | Row Count | Total Shares | Total Value USD |
| :---: | :---: | :---: | :---: | :---: |
| `DFND` | `'0'` | **917** | **418,109,088** | **$19,018,144,000** |

```sql
-- Query 2: Point72 Component Manager Relationships Ingest Breakdown
SELECT accession_number, reporter_cik, related_cik, sequence_number, source_table
FROM manager_relationships
WHERE accession_number IN (
    '0001567619-20-004063', '0001567619-20-004060', '0001567619-20-004064', '0001567619-20-004066'
)
ORDER BY accession_number, source_table, sequence_number;
```
**Output**:
| Accession Number | Reporter CIK | Related CIK | Sequence Number | Source Table | Semantic Role |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `0001567619-20-004060` | `1698051` (Europe) | `1603466` (Main) | `1` | `OTHERMANAGER2.tsv` | Line-Level Column 7 Sequence |
| `0001567619-20-004064` | `1603465` (Cubist) | `1603466` (Main) | `1` | `OTHERMANAGER2.tsv` | Line-Level Column 7 Sequence |
| `0001567619-20-004066` | `1599822` (HK) | `1603466` (Main) | `1` | `OTHERMANAGER2.tsv` | Line-Level Column 7 Sequence |
| `0001567619-20-004063` | `1603466` (Main) | `1603465` (Cubist) | `32421` | `OTHERMANAGER.tsv` | Surrogate Key (`SK`), NOT Column 7 |
| `0001567619-20-004063` | `1603466` (Main) | `1599822` (HK) | `32422` | `OTHERMANAGER.tsv` | Surrogate Key (`SK`), NOT Column 7 |
| `0001567619-20-004063` | `1603466` (Main) | `1698051` (Europe) | `32423` | `OTHERMANAGER.tsv` | Surrogate Key (`SK`), NOT Column 7 |

```sql
-- Query 3: Dataset-wide OTHERMANAGER2.tsv Sequence Number Distribution and Zero-Sequence Check
SELECT COUNT(*) AS total_numeric_rows,
       MIN(CAST(sequence_number AS INTEGER)) AS min_seq,
       MAX(CAST(sequence_number AS INTEGER)) AS max_seq,
       SUM(CASE WHEN TRIM(sequence_number) IN ('0', '00', '000') THEN 1 ELSE 0 END) AS zero_seq_count
FROM manager_relationships
WHERE source_table = 'OTHERMANAGER2.tsv' AND sequence_number GLOB '[0-9]*';
```
**Output**:
| Total Numeric Rows | Min Sequence | Max Sequence | Zero-Sequence Count (`0`/`00`/`000`) |
| :---: | :---: | :---: | :---: |
| **93,183** | **1** | **602** | **0** |

---

## 3. Disambiguation: `OTHERMANAGER.tsv` vs `OTHERMANAGER2.tsv`

### Observed Facts:
1. In the SEC raw 13F dataset (e.g. `phase0/data/zips/2020q1.zip`), `OTHERMANAGER2.tsv` contains field `SEQUENCENUMBER`, populated with 1-based sequential integers (`1` through `602`) assigned to other included managers on the Summary Page.
2. `OTHERMANAGER.tsv` contains field `OTHERMANAGER_SK`, which is an internal surrogate key assigned during SEC EDGAR ingestion.
3. In `INFOTABLE.tsv`, the Column 7 field `OTHRMANAGER` references `OTHERMANAGER2.SEQUENCENUMBER`.
4. There are exactly 0 sequence entries of `0`, `00`, or `000` in `OTHERMANAGER2.tsv`.

### Inferences & Architectural Decisions:
1. **Line-Level Sequence Lookup**: Line-level resolution (`resolve_ownership`) must strictly query `manager_relationships` where `source_table = 'OTHERMANAGER2.tsv'`. Using `OTHERMANAGER.tsv` for sequence matching is invalid because its keys are surrogate identifiers.
2. **Entity Graph Affiliation**: Both `OTHERMANAGER.tsv` and `OTHERMANAGER2.tsv` contain valid on-time institutional relationships and should both contribute undirected edges to the entity connected-components graph $G(Q-1, Q)$.

---

## 4. Target-CUSIP Distribution & Accession Coexistence

### A. Target-CUSIP Classification Table
A chunked streaming classification over all line items for the four canonical split pilot stocks produces the following distribution:

| Metric / Category | NVDA (`67066G104`) | TSLA (`88160R101`) | AMZN (`023135106`) | GOOGL (`02079K305`) |
| :--- | :---: | :---: | :---: | :---: |
| **Total Rows** | **194,587** | **148,141** | **272,695** | **217,919** |
| `BLANK_OR_NULL` | 120,094 (61.7%) | 90,514 (61.1%) | 177,661 (65.2%) | 138,258 (63.4%) |
| `ZERO_SENTINEL` (`'0'`) | 17,507 (9.0%) | 14,798 (10.0%) | 20,873 (7.7%) | 17,254 (7.9%) |
| `NA_NONE_SENTINEL` (`N/A`, `NONE`, `NA`) | 4,644 (2.4%) | 3,563 (2.4%) | 6,876 (2.5%) | 5,490 (2.5%) |
| `SINGLE_NUMERIC_SEQ` | 41,594 (21.4%) | 31,409 (21.2%) | 53,885 (19.8%) | 45,570 (20.9%) |
| `MULTI_NUMERIC_SEQ` | 8,560 (4.4%) | 6,124 (4.1%) | 10,743 (3.9%) | 9,213 (4.2%) |
| `FREE_TEXT_NAME` | 2,188 (1.1%) | 1,733 (1.2%) | 2,657 (1.0%) | 2,134 (1.0%) |

> **Audit Note on Semantics**: Blank, zero, and N/A/NONE rows are **candidate no-manager-like encodings**. They are not uniformly sole discretion; in empirical data, rows with `other_manager = '0'` occur with `investment_discretion` values of `SOLE`, `DFND`, and `OTR`.

### B. Accession Coexistence Evidence
Accessions where `'0'` and nonzero `other_manager` values coexist within the same filing:
- **NVDA (`67066G104`)**: **462 accessions**
- **TSLA (`88160R101`)**: **310 accessions**
- **AMZN (`023135106`)**: **709 accessions**
- **GOOGL (`02079K305`)**: **546 accessions**

**Inference from Coexistence**: The presence of both `'0'` and positive integer sequence numbers within the same accession demonstrates that filers use `'0'` as a line-specific indicator (indicating no other manager for that specific line item), rather than a filing-wide omission.

### C. Executable Reproducible Chunked Streaming Snippet
Auditors can reproduce the exact target-CUSIP classification and accession coexistence counts using the following chunked `fetchmany` Python script:

```python
import re
from pathlib import Path
from collections import Counter, defaultdict
from research.smart_money.m0.src.storage_guard import open_readonly_sqlite

def classify_row_other_manager(val: str | None) -> str:
    if val is None:
        return "BLANK_OR_NULL"
    s = val.strip()
    if not s:
        return "BLANK_OR_NULL"
    if s == "0":
        return "ZERO_SENTINEL"
    s_upper = s.upper()
    if s_upper in ("N/A", "NA", "NOT APPLICABLE", "NONE", "N / A"):
        return "NA_NONE_SENTINEL"
    tokens = [t for t in re.split(r"[,\s]+", s) if t]
    if all(t.isdigit() for t in tokens):
        if len(tokens) == 1:
            return "SINGLE_NUMERIC_SEQ"
        return "MULTI_NUMERIC_SEQ"
    return "FREE_TEXT_NAME"

db_path = Path("research/smart_money/phase0/data/13f_full_4409f14.db")
conn = open_readonly_sqlite(db_path, immutable=True)
cur = conn.cursor()

stocks = [("NVDA", "67066G104"), ("TSLA", "88160R101"), ("AMZN", "023135106"), ("GOOGL", "02079K305")]

for sym, cusip in stocks:
    cur.execute("SELECT accession_number, other_manager FROM filing_line_items WHERE cusip = ?;", (cusip,))
    counts = Counter()
    acc_has_zero = defaultdict(bool)
    acc_has_nonzero = defaultdict(bool)

    while True:
        chunk = cur.fetchmany(10000)
        if not chunk:
            break
        for acc, om in chunk:
            cat = classify_row_other_manager(om)
            counts[cat] += 1
            om_s = (om or "").strip()
            if om_s == "0":
                acc_has_zero[acc] = True
            elif om_s and om_s != "0":
                acc_has_nonzero[acc] = True

    coexist_cnt = sum(1 for acc in acc_has_zero if acc_has_nonzero[acc])
    print(f"{sym} ({cusip}): total={sum(counts.values())}, coexistence_accessions={coexist_cnt}")
    print(f"  counts: {dict(counts)}")

conn.close()
```

---

## 5. Adopted CONTRACT v0.8.2 Specification Amendment

### Adopted Rules

1. **Primary Origin Sentinels**:
   - `None` (NULL) and `""` (empty string).
   - Exact case-normalized `"N/A"` (authorized by official SEC Form 13F FAQ Q48/Q49).
   - Exact string `"0"` ONLY as an explicitly empirical SEC-data compatibility rule, justified because real sequence mappings in `OTHERMANAGER2.tsv` are strictly 1-based (`1` to `602`) and no sequence `0` exists.
   - When a primary origin sentinel is matched, `resolve_ownership` attributes the holding to `origin_filer_cik` with `ownership_unresolved = False`.

2. **Dirty Variants Excluded from Primary**:
   - Values such as `"NONE"`, `"NA"`, `"NOT APPLICABLE"`, `"N / A"`, `"00"`, `"0.0"` remain **unresolved in Primary M0** until separately evidenced; they may only be evaluated in sensitivity-only branches.
   - Multi-numeric lists (e.g. `"1,2,4,11"`, `"1 3 4"`) and free-text manager names (e.g. `"Blue Chip Partners LLC"`) remain strictly **unresolved** in Primary M0.

3. **Mandatory Sensitivity Branch (`ZERO_SENTINEL_EXCLUDED`)**:
   - Require a dedicated sensitivity branch derived **upstream pre-aggregation** that excludes empirical-zero (`'0'`) rows to evaluate signal robustness against this compatibility rule.

4. **Line-Level Sequence Resolution Rule**:
   - Line items in `filing_line_items` resolve sequence numbers strictly against `manager_relationships` entries where `source_table = 'OTHERMANAGER2.tsv'`. Entries from `OTHERMANAGER.tsv` are ignored for line sequence matching.

5. **Entity Graph Closure Rule**:
   - Both `OTHERMANAGER.tsv` and `OTHERMANAGER2.tsv` valid on-time relationship records are unioned to construct entity affiliation graph edges $G(Q-1, Q)$.

---

## 6. Fact vs Inference Summary Checklist

| Topic | Observed Fact | Inference / Interpretation |
| :--- | :--- | :--- |
| **Point72 2019Q4 Main Filing** | 917 rows in accession `0001567619-20-004063` have `INVESTMENTDISCRETION='DFND'`, `other_manager='0'`, and shared voting authority for all 418M shares. | Point72 intended to report these holdings as managed under its own defined authority rather than delegating to another listed manager. |
| **SEC Regulatory FAQs** | SEC FAQ Q48/Q49 explicitly specifies blank or `N/A` for non-shared discretion; does not mention `0` or `NONE`. | `'0'` is an empirical filing artifact generated by electronic filing systems when discretion is not shared. |
| **Phase 0 Relationship Tables** | `OTHERMANAGER2.tsv` contains 93,183 1-based sequence numbers ($1 \le seq \le 602$) and 0 zero sequences. `OTHERMANAGER.tsv` contains surrogate keys (`OTHERMANAGER_SK`). | `OTHERMANAGER2.tsv` is the sole table designed to resolve line-level Column 7 sequences; `OTHERMANAGER.tsv` must not be used for line resolution. |
| **Target-CUSIP Distribution** | `'0'` occurs in 7.7%–10.0% of line items; `'0'` coexists with positive sequence numbers in 310–709 accessions per split stock. | `'0'` is a line-specific origin indicator rather than an accession-wide filing default. |

---

## 7. Formal Governance & Decision Record

### Formal Decision Record
- **Decision Date**: 2026-08-24
- **Authority**: Independent Codex Auditor
- **Action**: **APPROVED** for adoption into `CONTRACT.md` v0.8.2 and `IMPLEMENTATION_PLAN.md` v0.8.2.
- **Implementation Status**: Specifications and test plan updated; source code and test suite implementation to follow under strict audit control.
