"""Fast synthetic tests for CH-3, CH-5, CH-6 and CH-13.

CH-7 is a source-ZIP parity test and is exercised against the real corpus by
``pipeline.py qa``.
"""

import os
import sqlite3

os.environ.setdefault("SEC_USER_AGENT", "Phase0Tests tests@example.com")

from pipeline import SCHEMA, check_ch3, check_ch5, check_ch6, check_ch13
from qa_support import ensure_support_schema


def new_db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    ensure_support_schema(db)
    return db


def recorder():
    result = {}

    def record(check_id, status, detail=""):
        result[check_id] = (status, detail)

    return result, record


def insert_filing(db, accession, cik, period):
    db.execute(
        """
        INSERT INTO filing_events
        (accession_number,cik,period_of_report,acceptance_datetime,form_type,ingest_zip,ingest_ts)
        VALUES (?,?,?,?,?,?,?)
        """,
        (accession, cik, period, period + "T12:00:00", "13F-HR", "test", "test"),
    )


def insert_holding(db, accession, seq, cusip, shares, value):
    db.execute(
        """
        INSERT INTO filing_line_items
        (accession_number,line_seq,cusip,raw_value_reported,value_usd,sshprnamt,
         sshprnamttype,asset_class,voting_sole,voting_shared,voting_none)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (accession, seq, cusip, value, value, shares, "SH", "cash_equity", shares, 0, 0),
    )


def test_ch3():
    db = new_db()
    for number in range(100):
        cik = str(1_000_000 + number)
        q1, q2 = f"q1-{cik}", f"q2-{cik}"
        insert_filing(db, q1, cik, "2024-03-31")
        insert_filing(db, q2, cik, "2024-06-30")
        insert_holding(db, q1, 0, "67066G104", 1_000 + number, 100_000)
        insert_holding(db, q2, 0, "67066G104", (1_000 + number) * 10, 1_000_000)
    result, record = recorder()
    check_ch3(db, record)
    assert result["CH-3"][0] == "PASS", result
    db.execute(
        """
        UPDATE filing_line_items SET sshprnamt=sshprnamt/10
        WHERE accession_number LIKE 'q2-%'
        """
    )
    failed, failed_record = recorder()
    check_ch3(db, failed_record)
    assert failed["CH-3"][0] == "FAIL", failed


def test_ch5():
    db = new_db()
    db.executemany(
        """
        INSERT INTO manager_relationships
        (accession_number,period_of_report,reporter_cik,related_cik,sequence_number,source_table)
        VALUES (?,?,?,?,?,?)
        """,
        [
            ("p", "2019-12-31", "1603466", "1599822", "1", "OTHERMANAGER.tsv"),
            ("p", "2019-12-31", "1603466", "1698051", "2", "OTHERMANAGER.tsv"),
        ],
    )
    for index, cik in enumerate(("1603466", "1599822", "1698051"), start=1):
        accession = f"p{index}"
        insert_filing(db, accession, cik, "2019-12-31")
        # All three overlap on AAPL.  CIK 1 and 2 deliberately disclose the
        # exact same position; CIK 3 has a genuinely different position.
        shares = 100 if index < 3 else 200
        insert_holding(db, accession, 0, "037833100", shares, shares * 100)
    result, record = recorder()
    check_ch5(db, record)
    assert result["CH-5"][0] == "PASS", result
    assert "removed=1" in result["CH-5"][1], result


def test_ch6():
    db = new_db()
    seq = 0
    for year in range(2016, 2024):
        for month_day in ("03-31", "06-30", "09-30", "12-31"):
            period = f"{year}-{month_day}"
            accession = f"brk-{period}"
            insert_filing(db, accession, "1067983", period)
            insert_holding(db, accession, seq, "037833100", 100, 10_000)
            seq += 1
    result, record = recorder()
    check_ch6(db, record)
    assert result["CH-6"][0] == "PASS", result
    db.execute("DELETE FROM filing_line_items WHERE accession_number='brk-2020-06-30'")
    failed, failed_record = recorder()
    check_ch6(db, failed_record)
    assert failed["CH-6"][0] == "FAIL", failed


def test_ch13():
    db = new_db()
    for order in range(100):
        cusip = f"{order:09d}"
        db.execute(
            """
            INSERT INTO qa_cusip_sample(check_id,period_of_report,sample_order,cusip,sec_name)
            VALUES ('CH-13','2020-03-31',?,?,?)
            """,
            (order + 1, cusip, f"ISSUER {order}"),
        )
        status = "mapped" if order < 92 else "unmapped"
        db.execute(
            """
            INSERT INTO cusip_mappings
            (cusip,ticker,mapped_name,mapping_status,name_match_score,source,mapped_at)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                cusip,
                f"T{order}" if status == "mapped" else None,
                f"ISSUER {order}" if status == "mapped" else None,
                status,
                1.0 if status == "mapped" else 0.0,
                "test",
                "test",
            ),
        )
    db.execute(
        """
        INSERT INTO cusip_mappings
        (cusip,ticker,mapped_name,mapping_status,name_match_score,delisted_flag,
         delisted_date,source,mapped_at)
        VALUES ('90184L102','TWTR','TWITTER INC','mapped',1,1,'2022-10-28','test','test')
        """
    )
    result, record = recorder()
    check_ch13(db, record)
    assert result["CH-13"][0] == "PASS", result
    db.execute(
        """
        UPDATE cusip_mappings SET mapping_status='unmapped', ticker=NULL
        WHERE cusip IN ('000000090','000000091')
        """
    )
    failed, failed_record = recorder()
    check_ch13(db, failed_record)
    assert failed["CH-13"][0] == "FAIL", failed


if __name__ == "__main__":
    tests = (test_ch3, test_ch5, test_ch6, test_ch13)
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"{len(tests)}/{len(tests)} PASS")
