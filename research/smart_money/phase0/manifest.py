"""
SEC 13F Bulk Data Manifest
v1.5 spec: packages indexed by filing_window (NOT holdings period)
Holdings period = PERIODOFREPORT field inside each ZIP

Total: 52 packages (2013Q3 filing window → 2026 Mar-May filing window)
Source: https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets
"""

BASE_URL = "https://www.sec.gov/Archives/edgar/full-index/13f/"
BULK_BASE = "https://efts.sec.gov/LATEST/search-index?q=%2213F%22&dateRange=custom"

# Official SEC bulk ZIP packages
# Format: (filing_window_label, zip_url, approx_size_mb, notes)
PACKAGES = [
    # 2013 — XML mandatory start (May 2013); early packages are small / transitional
    ("2013q3", "https://www.sec.gov/Archives/edgar/full-index/13f/2013q3_form13f.zip", 36.5,
     "First substantial XML package; PERIODOFREPORT mostly 2013-06-30"),
    ("2013q4", "https://www.sec.gov/Archives/edgar/full-index/13f/2013q4_form13f.zip", None,
     "PERIODOFREPORT mostly 2013-09-30"),

    # 2014
    ("2014q1", "https://www.sec.gov/Archives/edgar/full-index/13f/2014q1_form13f.zip", None, ""),
    ("2014q2", "https://www.sec.gov/Archives/edgar/full-index/13f/2014q2_form13f.zip", None, ""),
    ("2014q3", "https://www.sec.gov/Archives/edgar/full-index/13f/2014q3_form13f.zip", None, ""),
    ("2014q4", "https://www.sec.gov/Archives/edgar/full-index/13f/2014q4_form13f.zip", None, ""),

    # 2015
    ("2015q1", "https://www.sec.gov/Archives/edgar/full-index/13f/2015q1_form13f.zip", None, ""),
    ("2015q2", "https://www.sec.gov/Archives/edgar/full-index/13f/2015q2_form13f.zip", None, ""),
    ("2015q3", "https://www.sec.gov/Archives/edgar/full-index/13f/2015q3_form13f.zip", None, ""),
    ("2015q4", "https://www.sec.gov/Archives/edgar/full-index/13f/2015q4_form13f.zip", None, ""),

    # 2016
    ("2016q1", "https://www.sec.gov/Archives/edgar/full-index/13f/2016q1_form13f.zip", None, ""),
    ("2016q2", "https://www.sec.gov/Archives/edgar/full-index/13f/2016q2_form13f.zip", None, ""),
    ("2016q3", "https://www.sec.gov/Archives/edgar/full-index/13f/2016q3_form13f.zip", None, ""),
    ("2016q4", "https://www.sec.gov/Archives/edgar/full-index/13f/2016q4_form13f.zip", None, ""),

    # 2017
    ("2017q1", "https://www.sec.gov/Archives/edgar/full-index/13f/2017q1_form13f.zip", None, ""),
    ("2017q2", "https://www.sec.gov/Archives/edgar/full-index/13f/2017q2_form13f.zip", None, ""),
    ("2017q3", "https://www.sec.gov/Archives/edgar/full-index/13f/2017q3_form13f.zip", None, ""),
    ("2017q4", "https://www.sec.gov/Archives/edgar/full-index/13f/2017q4_form13f.zip", None, ""),

    # 2018
    ("2018q1", "https://www.sec.gov/Archives/edgar/full-index/13f/2018q1_form13f.zip", None, ""),
    ("2018q2", "https://www.sec.gov/Archives/edgar/full-index/13f/2018q2_form13f.zip", None, ""),
    ("2018q3", "https://www.sec.gov/Archives/edgar/full-index/13f/2018q3_form13f.zip", None, ""),
    ("2018q4", "https://www.sec.gov/Archives/edgar/full-index/13f/2018q4_form13f.zip", None, ""),

    # 2019
    ("2019q1", "https://www.sec.gov/Archives/edgar/full-index/13f/2019q1_form13f.zip", None, ""),
    ("2019q2", "https://www.sec.gov/Archives/edgar/full-index/13f/2019q2_form13f.zip", None, ""),
    ("2019q3", "https://www.sec.gov/Archives/edgar/full-index/13f/2019q3_form13f.zip", None, ""),
    ("2019q4", "https://www.sec.gov/Archives/edgar/full-index/13f/2019q4_form13f.zip", None, ""),

    # 2020
    ("2020q1", "https://www.sec.gov/Archives/edgar/full-index/13f/2020q1_form13f.zip", None, "COVID period"),
    ("2020q2", "https://www.sec.gov/Archives/edgar/full-index/13f/2020q2_form13f.zip", None, ""),
    ("2020q3", "https://www.sec.gov/Archives/edgar/full-index/13f/2020q3_form13f.zip", None, ""),
    ("2020q4", "https://www.sec.gov/Archives/edgar/full-index/13f/2020q4_form13f.zip", None, ""),

    # 2021
    ("2021q1", "https://www.sec.gov/Archives/edgar/full-index/13f/2021q1_form13f.zip", None, ""),
    ("2021q2", "https://www.sec.gov/Archives/edgar/full-index/13f/2021q2_form13f.zip", None, "FINRA SI starts 2021-06"),
    ("2021q3", "https://www.sec.gov/Archives/edgar/full-index/13f/2021q3_form13f.zip", None, ""),
    ("2021q4", "https://www.sec.gov/Archives/edgar/full-index/13f/2021q4_form13f.zip", None, ""),

    # 2022
    ("2022q1", "https://www.sec.gov/Archives/edgar/full-index/13f/2022q1_form13f.zip", None, ""),
    ("2022q2", "https://www.sec.gov/Archives/edgar/full-index/13f/2022q2_form13f.zip", None, ""),
    ("2022q3", "https://www.sec.gov/Archives/edgar/full-index/13f/2022q3_form13f.zip", None, ""),
    ("2022q4", "https://www.sec.gov/Archives/edgar/full-index/13f/2022q4_form13f.zip", None,
     "Last quarter where all filings use old $000 regime"),

    # 2023 — VALUE regime change 2023-01-03
    ("2023q1", "https://www.sec.gov/Archives/edgar/full-index/13f/2023q1_form13f.zip", None,
     "CRITICAL: Mixed regime. Filings accepted < 2023-01-03 → $000; >= → nearest dollar. "
     "Berkshire Q4 2022 (period=2022-12-31) filed 2023-02-14 → NEW regime."),
    ("2023q2", "https://www.sec.gov/Archives/edgar/full-index/13f/2023q2_form13f.zip", None, ""),
    ("2023q3", "https://www.sec.gov/Archives/edgar/full-index/13f/2023q3_form13f.zip", None,
     "Confidential flag more explicit post-2023 reform"),
    ("2023q4", "https://www.sec.gov/Archives/edgar/full-index/13f/2023q4_form13f.zip", None, ""),

    # 2024
    ("2024q1", "https://www.sec.gov/Archives/edgar/full-index/13f/2024q1_form13f.zip", None,
     "Berkshire 2023Q4 ADD amendment filed 2024-05-15 → CH-4/CH-9 test case"),
    ("2024q2", "https://www.sec.gov/Archives/edgar/full-index/13f/2024q2_form13f.zip", None, ""),
    ("2024q3", "https://www.sec.gov/Archives/edgar/full-index/13f/2024q3_form13f.zip", None,
     "NVDA 10:1 split 2024-06-10 → CH-3 test case"),
    ("2024q4", "https://www.sec.gov/Archives/edgar/full-index/13f/2024q4_form13f.zip", None, ""),

    # 2025
    ("2025q1", "https://www.sec.gov/Archives/edgar/full-index/13f/2025q1_form13f.zip", None, ""),
    ("2025q2", "https://www.sec.gov/Archives/edgar/full-index/13f/2025q2_form13f.zip", None, ""),
    ("2025q3", "https://www.sec.gov/Archives/edgar/full-index/13f/2025q3_form13f.zip", None, ""),
    ("2025q4", "https://www.sec.gov/Archives/edgar/full-index/13f/2025q4_form13f.zip", None,
     "Deadline = 2026-02-17 (Tue); 45th day 2026-02-14 Sat + Presidents Day 2026-02-16 → CH-11"),

    # 2026 — Latest available bulk (as of 2026-08-23)
    # Contains filings submitted Mar-May 2026 → mostly PERIODOFREPORT = 2025-12-31 (Q4 2025)
    ("2026q1_filings", "https://www.sec.gov/Archives/edgar/full-index/13f/2026q1_form13f.zip", None,
     "Filing window: Jan-Mar 2026; PERIODOFREPORT mostly 2025-09-30"),
    ("2026q2_filings", "https://www.sec.gov/Archives/edgar/full-index/13f/2026q2_form13f.zip", None,
     "Filing window: Apr-Jun 2026; PERIODOFREPORT mostly 2025-12-31. "
     "Check availability: may not exist yet."),
    ("2026q3_partial", None, None,
     "2026Q2 holdings (period=2026-06-30): deadline ~2026-08-14. "
     "Use live EDGAR API; reconcile when bulk ZIP published."),
]

# Derived: holdings periods covered (PERIODOFREPORT values)
# Each filing window package maps to: holdings ~= previous quarter-end
# e.g., 2013q3 filing window → mostly period=2013-06-30 (Q2 2025 holdings)
# Must verify via actual PERIODOFREPORT field, not assumed from zip name.

HOLDINGS_PERIODS = [
    "2013-06-30",  # covered by 2013q3 + 2013q4 filing windows
    "2013-09-30",
    "2013-12-31",
    "2014-03-31", "2014-06-30", "2014-09-30", "2014-12-31",
    "2015-03-31", "2015-06-30", "2015-09-30", "2015-12-31",
    "2016-03-31", "2016-06-30", "2016-09-30", "2016-12-31",
    "2017-03-31", "2017-06-30", "2017-09-30", "2017-12-31",
    "2018-03-31", "2018-06-30", "2018-09-30", "2018-12-31",
    "2019-03-31", "2019-06-30", "2019-09-30", "2019-12-31",
    "2020-03-31", "2020-06-30", "2020-09-30", "2020-12-31",
    "2021-03-31", "2021-06-30", "2021-09-30", "2021-12-31",
    "2022-03-31", "2022-06-30", "2022-09-30", "2022-12-31",
    "2023-03-31", "2023-06-30", "2023-09-30", "2023-12-31",
    "2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31",
    "2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31",
    "2026-03-31",  # 2026Q1 holdings; deadline ~2026-05-15 (past)
    "2026-06-30",  # 2026Q2 holdings; deadline ~2026-08-14; use live API
]

# First usable ΔOwnership period (needs t and t-1)
FIRST_DELTA_PERIOD = "2013-09-30"   # = Q3 2013 holdings vs Q2 2013 holdings
FIRST_SIGNAL_PERIOD = "2013-09-30"  # Primary A sample starts here

# 2026Q2 live API endpoint (when bulk ZIP not yet available)
LIVE_EDGAR_SEARCH = (
    "https://efts.sec.gov/LATEST/search-index?q=%2213F-HR%22"
    "&dateRange=custom&startdt=2026-07-01&enddt=2026-08-20"
    "&forms=13F-HR"
)

KNOWN_TEST_CASES = {
    "CH3_split": {
        "description": "NVDA 10:1 split 2024-06-10",
        "cik": "1045810",  # NVIDIA CIK (for price); check manager holdings
        "period": "2024-06-30",
        "test": "Δshares for NVDA holders should not show 9x increase",
    },
    "CH4_CH9_merge": {
        "description": "Berkshire 2023Q4 ADD_NEW_HOLDINGS amendment",
        "cik": "1067983",
        "period": "2023-12-31",
        "original_accession": "0000950123-24-002518",
        "original_accepted": "2024-02-14 16:02:18",
        "amendment_type": "ADD_NEW_HOLDINGS",
        "amendment_accession": "TBD",  # 2024-05-15 filing
        "test": "reconstruct_state() at deadline must include BOTH original + amendment holdings",
    },
    "CH11_deadline": {
        "description": "Q4 2025 deadline calendar",
        "period": "2025-12-31",
        "raw_45th_day": "2026-02-14",  # Saturday
        "feb_16_holiday": "Presidents' Day 2026",
        "expected_deadline": "2026-02-17",  # Tuesday
        "test": "compute_13f_deadline('2025-12-31') == '2026-02-17'",
    },
    "CH1_value_berkshire": {
        "description": "Berkshire Q4 2022 — mixed regime test",
        "cik": "1067983",
        "period": "2022-12-31",
        "acceptance_datetime": "2023-02-14",
        "expected_regime": "nearest_dollar",  # NOT $000
        "test": "value normalization uses nearest dollar (not ×1000) for this filing",
    },
}

if __name__ == "__main__":
    available = [(label, url, size, notes)
                 for label, url, size, notes in PACKAGES if url is not None]
    print(f"Total packages with URLs: {len(available)}")
    print(f"Holdings periods covered: {len(HOLDINGS_PERIODS)}")
    print(f"First ΔOwnership period: {FIRST_DELTA_PERIOD}")
    print(f"\nKnown test cases:")
    for k, v in KNOWN_TEST_CASES.items():
        print(f"  {k}: {v['description']}")
