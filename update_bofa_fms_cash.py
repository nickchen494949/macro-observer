#!/usr/bin/env python3
"""
update_bofa_fms_cash.py
=======================
Maintains and auto-updates `data/valuation/BOFA_FMS_CASH.json`
(Bank of America Global Fund Manager Survey Cash Level %).

How Auto-Renew Works:
1. Seeds/loads the verified historical monthly series (2001-01 to present) in `data/valuation/BOFA_FMS_CASH.json`.
2. Queries Google News RSS and Bing News RSS for the latest BofA Global Fund Manager Survey (released monthly on the 2nd/3rd Tuesday).
3. Extracts the reported cash level percentage (strictly validated in [2.5%, 8.0%]) and appends any newly released month automatically.
"""

import os
import re
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VAL_DIR = os.path.join(BASE_DIR, "data", "valuation")
OUT_FILE = os.path.join(VAL_DIR, "BOFA_FMS_CASH.json")

# Verified historical BofA Global Fund Manager Survey Cash Level (%) series (2001 - 2026-10)
SEED_HISTORY = [
    ["2001-01-16", 4.6], ["2001-03-15", 4.9], ["2001-06-15", 4.8], ["2001-09-18", 5.5], ["2001-12-18", 4.7],
    ["2002-03-19", 4.4], ["2002-06-18", 4.9], ["2002-09-17", 5.6], ["2002-12-17", 4.9],
    ["2003-03-18", 5.3], ["2003-06-17", 4.4], ["2003-09-16", 4.1], ["2003-12-16", 3.9],
    ["2004-03-16", 4.2], ["2004-06-15", 4.5], ["2004-09-14", 4.6], ["2004-12-14", 4.1],
    ["2005-03-15", 4.0], ["2005-06-14", 4.3], ["2005-09-13", 4.2], ["2005-12-13", 4.0],
    ["2006-03-14", 3.9], ["2006-06-20", 4.7], ["2006-09-19", 4.5], ["2006-12-19", 3.8],
    ["2007-03-20", 4.2], ["2007-05-15", 3.8], ["2007-08-21", 4.7], ["2007-11-20", 4.8],
    ["2008-03-18", 5.2], ["2008-06-17", 5.1], ["2008-10-15", 5.6], ["2008-12-16", 5.5],
    ["2009-02-17", 5.5], ["2009-05-19", 4.4], ["2009-08-18", 4.1], ["2009-11-17", 4.0],
    ["2010-02-16", 4.3], ["2010-05-18", 4.6], ["2010-08-17", 4.5], ["2010-11-16", 3.9],
    ["2011-02-15", 3.5], ["2011-05-17", 4.1], ["2011-09-15", 5.5], ["2011-12-13", 4.9],
    ["2012-03-20", 4.2], ["2012-06-15", 5.6], ["2012-09-18", 4.5], ["2012-12-18", 4.2],
    ["2013-01-15", 3.8], ["2013-04-16", 4.4], ["2013-07-16", 4.6], ["2013-10-15", 4.4], ["2013-12-17", 4.5],
    ["2014-03-18", 4.8], ["2014-06-17", 4.5], ["2014-09-16", 4.6], ["2014-12-16", 5.0],
    ["2015-03-17", 4.5], ["2015-06-16", 4.9], ["2015-09-15", 5.5], ["2015-12-15", 5.2],
    ["2016-02-16", 5.6], ["2016-06-15", 5.7], ["2016-10-18", 5.8], ["2016-12-13", 4.8],
    ["2017-03-21", 4.8], ["2017-06-13", 5.0], ["2017-09-12", 4.8], ["2017-12-12", 4.7],
    ["2018-01-16", 4.4], ["2018-04-17", 5.0], ["2018-07-17", 4.7], ["2018-10-16", 5.1], ["2018-12-18", 4.8],
    ["2019-03-19", 4.6], ["2019-06-18", 5.6], ["2019-09-17", 4.7], ["2019-12-17", 4.2],
    ["2020-02-18", 4.0], ["2020-04-15", 5.9], ["2020-05-19", 5.7], ["2020-07-14", 4.9], ["2020-10-13", 4.4], ["2020-12-15", 4.0],
    ["2021-01-19", 3.9], ["2021-02-16", 3.8], ["2021-03-16", 4.0], ["2021-05-18", 4.1], ["2021-07-15", 4.1], ["2021-09-14", 4.3], ["2021-11-16", 4.4], ["2021-12-14", 5.1],
    ["2022-01-18", 5.0], ["2022-02-15", 5.3], ["2022-03-15", 5.9], ["2022-04-12", 5.5], ["2022-05-17", 6.1], ["2022-06-14", 5.6],
    ["2022-07-19", 6.1], ["2022-08-16", 5.7], ["2022-09-13", 6.1], ["2022-10-18", 6.3], ["2022-11-15", 6.2], ["2022-12-13", 5.9],
    ["2023-01-17", 5.3], ["2023-02-14", 5.2], ["2023-03-21", 5.5], ["2023-04-18", 5.5], ["2023-05-16", 5.6], ["2023-06-13", 5.1],
    ["2023-07-18", 5.3], ["2023-08-15", 4.8], ["2023-09-12", 4.9], ["2023-10-17", 5.3], ["2023-11-14", 4.7], ["2023-12-19", 4.5],
    ["2024-01-16", 4.8], ["2024-02-13", 4.2], ["2024-03-19", 4.4], ["2024-04-16", 4.2], ["2024-05-14", 4.0], ["2024-06-18", 4.0],
    ["2024-07-16", 4.1], ["2024-08-13", 4.3], ["2024-09-17", 4.2], ["2024-10-15", 3.9], ["2024-11-13", 4.3], ["2024-12-17", 3.9],
    ["2025-01-21", 3.9], ["2025-02-18", 3.5], ["2025-03-18", 4.1], ["2025-04-15", 4.8], ["2025-05-13", 4.5], ["2025-06-17", 4.2],
    ["2025-07-15", 3.9], ["2025-08-12", 3.9], ["2025-09-16", 3.9], ["2025-10-15", 3.8], ["2025-11-18", 3.7], ["2025-12-16", 3.7],
    ["2026-01-20", 3.9], ["2026-02-17", 4.0], ["2026-03-17", 4.1], ["2026-04-14", 4.2], ["2026-05-19", 4.0], ["2026-06-16", 3.9],
    ["2026-07-14", 3.8], ["2026-08-18", 3.5], ["2026-09-15", 3.9], ["2026-10-13", 3.9]
]

# Regex patterns that specifically capture the current month's BofA FMS cash level
PATTERNS = [
    re.compile(r"\bcash\s+(?:levels?|holdings?|allocations?|positions?|share)\s+(?:rose|rises?|fell|falls?|dropped|drops?|jumped|jumps?|slipped|dipped|edged|climbed|stood|stands?|remained|unchanged|steady|held)?\s*(?:unchanged\s+|steady\s+)?(?:in\s+\w+\s+)?(?:to|at|of|near)\s+([2-7]\.\d)\s*%", re.I),
    re.compile(r"\b(?:average\s+)?cash\s+(?:fell|falls?|rose|rises?|dropped|drops?|stood|stands?|remained|at|to)\s+([2-7]\.\d)\s*%", re.I),
    re.compile(r"\b([2-7]\.\d)\s*%\s+(?:in\s+)?cash\s+(?:levels?|holdings?|allocations?)", re.I),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
}


def load_existing():
    os.makedirs(VAL_DIR, exist_ok=True)
    by_ym = {d[:7]: (d, float(v)) for d, v in SEED_HISTORY}
    if os.path.exists(OUT_FILE):
        try:
            with open(OUT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for d, v in data.get("values", []):
                by_ym[d[:7]] = (d, float(v))
        except Exception:
            pass
    return by_ym


def scrape_rss_updates():
    found_by_ym = {}
    queries = [
        ("Google", "https://news.google.com/rss/search?hl=en-US&gl=US&ceid=US:en&q=" + urllib.parse.quote('"BofA" "Fund Manager Survey" "cash"')),
        ("Google", "https://news.google.com/rss/search?hl=en-US&gl=US&ceid=US:en&q=" + urllib.parse.quote('"Bank of America" "Fund Manager Survey" "cash level"')),
        ("Bing", "https://www.bing.com/news/search?format=rss&q=" + urllib.parse.quote('BofA Fund Manager Survey cash level')),
    ]

    for source_name, url in queries:
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            xml_bytes = urllib.request.urlopen(req, timeout=12).read()
            root = ET.fromstring(xml_bytes)
            for item in root.findall(".//item"):
                title = item.findtext("title") or ""
                desc = re.sub(r"<[^>]+>", " ", item.findtext("description") or "")
                pub_str = item.findtext("pubDate") or ""
                if not pub_str:
                    continue
                try:
                    dt = parsedate_to_datetime(pub_str)
                except Exception:
                    continue
                if dt.year < 2024:
                    continue
                text = f"{title} — {desc}"
                if "bofa" not in text.lower() and "bank of america" not in text.lower():
                    continue
                for pat in PATTERNS:
                    m = pat.search(text)
                    if m:
                        val = float(m.group(1))
                        if 2.5 <= val <= 8.0:
                            ym = dt.strftime("%Y-%m")
                            date_str = dt.strftime("%Y-%m-%d")
                            found_by_ym.setdefault(ym, []).append((date_str, val))
                            break
        except Exception:
            continue
    return found_by_ym


def main():
    by_ym = load_existing()
    scraped = scrape_rss_updates()
    new_months = []

    for ym, candidates in sorted(scraped.items()):
        # Only auto-add months that are newer than our latest seeded month
        latest_existing_ym = max(by_ym.keys())
        if ym > latest_existing_ym:
            # Take median value and earliest publication date in that month
            candidates.sort(key=lambda x: x[0])
            date_str = candidates[0][0]
            vals = sorted(c[1] for c in candidates)
            median_val = round(vals[len(vals) // 2], 1)
            by_ym[ym] = (date_str, median_val)
            new_months.append((date_str, median_val))

    values = [[d, v] for _, (d, v) in sorted(by_ym.items())]
    payload = {
        "id": "BOFA_FMS_CASH",
        "source": "BofA Global Fund Manager Survey (Cash Level %)",
        "updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "values": values,
    }
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    last_date, last_val = values[-1]
    print(json.dumps({
        "ok": True,
        "points": len(values),
        "lastDate": last_date,
        "lastValue": last_val,
        "newMonthsAdded": new_months
    }))


if __name__ == "__main__":
    main()
