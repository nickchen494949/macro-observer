# Smart Money 13F — Phase 0 Data Pipeline
**v1.5 spec | Audit-ready**

This pipeline ingests all SEC Form 13F bulk data (2013–2026), enforces
the v1.5 data-engineering spec, and runs 13 mechanical acceptance checks
(CH-1 to CH-13) before any future returns data is opened.

---

## Reproduce from scratch (fully free, ~90 min)

```bash
# 1. Clone
git clone https://github.com/nickchen494949/macro-observer.git
cd macro-observer/research/smart_money/phase0

# 2. Python env
python3 -m venv .venv && source .venv/bin/activate
pip install requests pandas

# 3. REQUIRED: set before importing pipeline.py (it checks at import time)
export SEC_USER_AGENT="Your Name your@email.com"

# 4. Unit tests (fast, no network)
python unit_tests.py
# Expected: 25/25 PASS

# 5. Integration tests (requires data/zips/2013q3.zip)
python integration_tests.py
# Expected: 37/37 PASS

# 6. Full pipeline on a FRESH database
#    If data/13f.db already exists from an older version, use a new path:
export DB_PATH=data/13f_v2.db   # omit this if starting from scratch
python run_phase0.py
# Downloads ~2.9GB from SEC (public data, no login needed)
# Takes ~60–90 min depending on connection speed

# 7. Inspect results
python pipeline.py status
python pipeline.py qa
```

All raw data comes directly from SEC public servers — no proprietary
data sources, no login required.

---

## What the pipeline enforces (v1.5 spec)

### Critical fixes vs naive implementations

| Issue | Naive / Wrong | This pipeline |
|-------|--------------|---------------|
| VALUE unit normalization | Use `period_of_report >= 2022-12-31` | Use `acceptance_datetime >= 2023-01-03` |
| ZIP quarter vs holdings quarter | Treat ZIP name as holdings period | Rebuild by `PERIODOFREPORT` field |
| Amendments | Ignore all `13F-HR/A` | `RESTATEMENT → REPLACE`; `ADD_NEW_HOLDINGS → MERGE` |
| PUT/CALL options | Sum all rows per CUSIP | Classify first; M0 uses `cash_equity` only |
| Filing deadline | `+45 calendar days` fixed | `+45 days` + weekend/federal holiday rollforward |
| Acceptance timestamp | Use `FILING_DATE` | Fetch `acceptanceDateTime` from Submissions API |

### Real SEC filing proof (manual verification)

Each fix was verified against actual SEC filings before full corpus ingest:

| Check | Evidence | SEC Link |
|-------|---------|---------|
| VALUE regime by acceptance date | Berkshire Q4 2022 (period 2022-12-31, accepted 2023-02-14) → nearest dollar | [filing index](https://www.sec.gov/Archives/edgar/data/1067983/000095012323002585/) |
| AAPL multi-row sum | Berkshire 2023Q4: multiple SH rows sum to 905,560,000 shares | [filing index](https://www.sec.gov/Archives/edgar/data/1067983/0000950123-24-002518-index.htm) |
| ADD amendment MERGE | Berkshire 2024-05-15 amendment adds Chubb 20.1M (not in original) | [amendment](https://www.sec.gov/Archives/edgar/data/1067983/000095012324005664/) |
| RESTATEMENT case | Murchinson Ltd 2024Q2 explicit restatement | [filing](https://www.sec.gov/Archives/edgar/data/1838556/000149315224032561/) |
| CALL/cash on same CUSIP | AAPL CUSIP 037833100: cash COM 5,000 + CALL 150,000 in same filing | [infotable](https://www.sec.gov/Archives/edgar/data/1350605/000117266115001118/) |
| Deadline calendar | Q4 2025: 45th day = 2026-02-14 (Sat) + Presidents Day → 2026-02-17 | [SEC FAQ](https://www.sec.gov/rules-regulations/staff-guidance/division-investment-management-frequently-asked-questions/frequently-asked-questions-about-form-13f) |

---

## CH-1 to CH-13 Acceptance Checks

All checks must PASS before any future return data is opened.

| ID | What it checks | Test case |
|----|---------------|-----------|
| CH-1 | VALUE normalization — no 1000× jump at 2023 boundary | Berkshire `0000950123-23-002585` |
| CH-2 | Berkshire 2023Q4 holdings match known positions | AAPL ~905M shares |
| CH-3 | NVDA 10:1 split 2024-06-10 — no spurious Δshares | 2024Q2 holders |
| CH-4 | RESTATEMENT type → full replace | Murchinson Ltd 2024Q2 |
| CH-5 | Entity dedup — no double-count for multi-CIK managers | Point72 |
| CH-6 | CUSIP continuity — no unexplained gaps | Cross-quarter |
| CH-7 | Universe has no future-return filter | By design (SKIP) |
| CH-8 | acceptance_datetime coverage > 95% | Submissions API |
| CH-9 | ADD_NEW_HOLDINGS → merge; original preserved | Berkshire + Chubb |
| CH-10 | PUT/CALL separated from cash equity shares | AAPL COM + CALL |
| CH-11 | Deadline calendar: 2025-12-31 → 2026-02-17 | ✅ Already PASS |
| CH-12 | Historical submissions complete for large filers | Morgan Stanley CIK 895421 |
| CH-13 | CUSIP → ticker coverage > 90% (random 100 from 2020Q1) | Post-mapping |

**Invariant**: CH-1 to CH-13 are purely mechanical data integrity checks.
No future return data is looked at until ALL checks pass.
Pipeline tuning to improve IC is forbidden.

---

## Data sources (all free, all public)

| Source | What | URL |
|--------|------|-----|
| SEC 13F bulk ZIPs | Holdings (2013–2026) | [sec.gov](https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets) |
| SEC Submissions API | `acceptanceDateTime` per filing | `data.sec.gov/submissions/CIK{}.json` |
| SEC submissions.zip | Bulk acceptance timestamps | `data.sec.gov/submissions/submissions.zip` |
| SEC 13(f) securities list | CUSIP → security type | [sec.gov](https://www.sec.gov/rules-regulations/staff-guidance/official-list-section-13f-securities) |
| OpenFIGI API | CUSIP → ticker mapping | [openfigi.com](https://www.openfigi.com/api) |
| Kenneth French | FF5 + Momentum factors | [mba.tuck.dartmouth.edu](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html) |
| FINRA | Short interest (2021-06+) | [finra.org](https://www.finra.org/finra-data/browse-catalog/equity-short-interest/files) |

---

## File structure

```
phase0/
├── pipeline.py        Core pipeline: schema, ingest, state machine, QA
├── run_phase0.py      Full execution: discover → download → ingest → enrich → QA
├── unit_tests.py      25 unit tests (all must pass before corpus work)
├── manifest.py        53 SEC ZIP URLs with metadata and test case annotations
├── .gitignore         Excludes data/ (ZIPs + SQLite, ~4GB total)
└── data/              ← NOT in git (regenerate with run_phase0.py)
    ├── zips/          Raw SEC ZIPs (~2.9GB)
    ├── 13f.db         SQLite database (~3-5GB after full ingest)
    └── pipeline.log   Ingest progress log
```

---

## Signal model (M0–M6, frozen at v1.5)

The data pipeline feeds into a 6-layer signal ablation:

```
M0  Raw Δshares (split-adjusted, cash equity only)
M1  HF manager filter
M2  × Manager Skill (rolling Rank IC)
M3  × Conviction (C2: actual weight / equal weight)
────────────────────────────────────────── aggregate to stock level
M4  × Independent Consensus (overlap-adjusted)
M5  + Short Interest confirmation (FINRA, 2021-06+)
M6  − Crowding overlay (M6-A: risk-off; M6-B: reallocation)
```

**Model architecture is frozen. Only data pipeline bugs may be fixed
after CH checks begin. Signal formula cannot be tuned post-hoc.**

---

## Spec document

Full research specification: [`smart_money_research_matrix.md`](../smart_money_research_matrix.md)
Current version: v1.5 (frozen 2026-08-23)

---

## Comparison with related audit

[smart-money-13f-backtest-audit](https://github.com/nickchen494949/smart-money-13f-backtest-audit)
(commit 2d81917) uses a similar ablation approach but differs in:

| Dimension | That repo | This pipeline |
|-----------|-----------|--------------|
| VALUE normalization | `period_of_report >= 2022-12-31` (wrong) | `acceptance_datetime >= 2023-01-03` (correct) |
| Amendments | Excluded entirely | RESTATEMENT/MERGE semantics |
| Deadline | Fixed `+50 days` | `+45 days` + holiday calendar |
| Manager weighting | Top-15 equal vote | Skill-weighted across all qualified |
| Sample | 2019–2026 (27 quarters) | 2013–2026 (~50 quarters) |
| Benchmark | SPY | FF5 + Momentum |

Both repos share the same overall research question and ablation structure.
