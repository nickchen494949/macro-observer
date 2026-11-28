#!/usr/bin/env python3
"""
update_luxury_indices.py
========================
Maintains and auto-updates physical luxury market time series in `data/valuation/`:

1. Secondary Luxury Watch Market (Bloomberg x Subdial, daily USD, free public JSON API):
   - LUX_SUBDIAL50.json  : Bloomberg x Subdial 50 (Top 50 most-traded watches: Rolex Daytona, Patek Nautilus, AP Royal Oak, etc.)
   - LUX_ROLEX.json      : Subdial Rolex Index (Top 25 Rolex models)
   - LUX_PATEK.json      : Subdial Patek Philippe Index (Ultra-HNW top 0.1% barometer)
   - LUX_ENTRY100.json   : Subdial Entry-Level 100 Index (Mass-affluent watch demand)

2. Official Physical Swiss Watch Exports (Federation of the Swiss Watch Industry FH, monthly):
   - LUX_SWISS_WATCH_EXPORTS.json : World monthly export value (Mil. CHF)
   - LUX_SWISS_WATCH_YOY.json     : World monthly export YoY % growth

All updates are strictly incremental (merge by date, never erase older cached history).
"""

import io
import json
import os
import re
import urllib.request
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VAL_DIR = os.path.join(BASE_DIR, "data", "valuation")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/html,*/*",
}

MONTH_MAP = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def load_series(file_id):
    p = os.path.join(VAL_DIR, f"{file_id}.json")
    if not os.path.exists(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        return {str(dt): float(val) for dt, val in d.get("values", []) if val is not None}
    except Exception:
        return {}


def save_series(file_id, by_date, meta=None):
    os.makedirs(VAL_DIR, exist_ok=True)
    values = [[d, round(by_date[d], 4)] for d in sorted(by_date.keys())]
    payload = {
        "id": file_id,
        "updated": datetime.now(timezone.utc).isoformat(),
        "values": values,
    }
    if meta:
        payload.update(meta)
    p = os.path.join(VAL_DIR, f"{file_id}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    return values


def discover_subdial50_ticker():
    """Auto-discover active Subdial50_yrYYYY ticker from subdial.com/market so year rollovers never break."""
    fallback = f"Subdial50_yr{datetime.now(timezone.utc).year}"
    try:
        req = urllib.request.Request("https://subdial.com/market", headers=HEADERS)
        html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="ignore")
        m = re.search(r"Subdial50_yr\d{4}", html)
        if m:
            return m.group(0)
    except Exception:
        pass
    return fallback


def update_subdial():
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    subdial50_ticker = discover_subdial50_ticker()
    targets = [
        ("LUX_SUBDIAL50", subdial50_ticker, "Bloomberg x Subdial 50 Watch Index (USD)"),
        ("LUX_ROLEX", "rolexIndex", "Subdial Rolex 25 Watch Index (USD)"),
        ("LUX_PATEK", "patekphilippeIndex", "Subdial Patek Philippe Watch Index (USD)"),
        ("LUX_ENTRY100", "EntryLevel100", "Subdial Entry-Level 100 Watch Index (USD)"),
    ]
    results = {}
    for file_id, ticker, desc in targets:
        by_date = load_series(file_id)
        try:
            url = (
                f"https://subdial.com/api/market/prices"
                f"?ticker={ticker}&currency=USD&start_date=2018-01-01&end_date={today_str}"
            )
            req = urllib.request.Request(url, headers=HEADERS)
            raw = json.loads(urllib.request.urlopen(req, timeout=18).read().decode("utf-8"))
            pts = raw.get("index_prices", [])
            added = 0
            for pt in pts:
                dt = pt.get("date")
                pr = pt.get("price")
                if dt and pr is not None:
                    dt_s = str(dt)[:10]
                    if dt_s not in by_date:
                        added += 1
                    by_date[dt_s] = float(pr)
            if by_date:
                vals = save_series(file_id, by_date, {"source": "Subdial", "ticker": ticker, "description": desc})
                results[file_id] = {
                    "ok": True,
                    "points": len(vals),
                    "added": added,
                    "lastDate": vals[-1][0],
                    "lastValue": vals[-1][1],
                }
            else:
                results[file_id] = {"ok": False, "error": "empty_series"}
        except Exception as e:
            results[file_id] = {"ok": False, "error": str(e), "cachedPoints": len(by_date)}
    return results


def update_fh_swiss_watch_exports():
    """Fetch official monthly Swiss watch exports (World, Mil. CHF) from FH and compute YoY %."""
    exp_map = load_series("LUX_SWISS_WATCH_EXPORTS")
    yoy_map = load_series("LUX_SWISS_WATCH_YOY")
    try:
        import pypdf
    except Exception as e:
        return {"ok": False, "error": f"pypdf_missing: {e}", "cachedPoints": len(yoy_map)}

    try:
        req = urllib.request.Request("https://www.fhs.swiss/eng/statistics.html", headers=HEADERS)
        html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="ignore")
        m = re.search(r"(/eng/statistics/pdf/histo_marches_\d+_a\.pdf)", html)
        if not m:
            return {"ok": False, "error": "pdf_link_not_found", "cachedPoints": len(yoy_map)}
        pdf_url = "https://www.fhs.swiss" + m.group(1)
        pdf_bytes = urllib.request.urlopen(
            urllib.request.Request(pdf_url, headers=HEADERS), timeout=20
        ).read()
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        text = reader.pages[0].extract_text() or ""

        # Parse monthly rows like: "Oct 26 2,456.4 178.2 ..."
        # First numeric token after "Mon YY" is World total in Mil. CHF.
        row_re = re.compile(
            r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{2})\s+([\d,]+\.\d)",
            re.MULTILINE,
        )
        parsed = 0
        for mon_str, yy_str, val_str in row_re.findall(text):
            year = 2000 + int(yy_str)
            month = MONTH_MAP[mon_str]
            dt = f"{year:04d}-{month:02d}-01"
            val = float(val_str.replace(",", ""))
            if 500.0 <= val <= 10000.0:  # sanity check for monthly World CHF millions
                exp_map[dt] = val
                parsed += 1

        if exp_map:
            exp_vals = save_series(
                "LUX_SWISS_WATCH_EXPORTS",
                exp_map,
                {"source": "Federation of the Swiss Watch Industry FH", "unit": "Mil CHF", "pdf": pdf_url},
            )
            # Compute YoY % wherever (year-1, month) exists
            for dt, cur_val in exp_map.items():
                yr = int(dt[:4]) - 1
                prev_dt = f"{yr:04d}{dt[4:]}"
                prev_val = exp_map.get(prev_dt)
                if prev_val and prev_val > 0:
                    yoy_map[dt] = (cur_val / prev_val - 1.0) * 100.0
            yoy_vals = save_series(
                "LUX_SWISS_WATCH_YOY",
                yoy_map,
                {"source": "Federation of the Swiss Watch Industry FH", "unit": "%", "pdf": pdf_url},
            )
            return {
                "ok": True,
                "parsedMonths": parsed,
                "exportPoints": len(exp_vals),
                "yoyPoints": len(yoy_vals),
                "lastDate": yoy_vals[-1][0] if yoy_vals else None,
                "lastYoY": yoy_vals[-1][1] if yoy_vals else None,
            }
        return {"ok": False, "error": "no_monthly_rows_parsed", "cachedPoints": len(yoy_map)}
    except Exception as e:
        return {"ok": False, "error": str(e), "cachedPoints": len(yoy_map)}


def main():
    subdial_res = update_subdial()
    fh_res = update_fh_swiss_watch_exports()
    any_ok = any(v.get("ok") for v in subdial_res.values()) or fh_res.get("ok")
    out = {"ok": any_ok, "subdial": subdial_res, "fh_swiss_watches": fh_res}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
