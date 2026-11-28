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
   Note: Subdial's public API serves a rolling 2-year daily window; incremental merge preserves all historical dates on disk.

2. Official Physical Swiss Watch Exports (Swiss National Bank SNB / BAZG cube `ausshawarm`, monthly SA, 2012-01 -> present):
   - LUX_SWISS_WATCH_EXPORTS.json : Monthly Swiss Watches & Clocks Exports (Mil. CHF, CPA2 C2652)
   - LUX_SWISS_WATCH_YOY.json     : Monthly YoY % growth (2013-01 -> present, ~165+ consecutive months)

All updates are strictly incremental (merge by date, never erase older cached history).
"""

import csv
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
    "Accept": "application/json,text/csv,text/html,*/*",
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
                    "firstDate": vals[0][0],
                    "lastDate": vals[-1][0],
                    "lastValue": vals[-1][1],
                }
            else:
                results[file_id] = {"ok": False, "error": "empty_series"}
        except Exception as e:
            results[file_id] = {"ok": False, "error": str(e), "cachedPoints": len(by_date)}
    return results


def update_snb_swiss_watch_exports():
    """Fetch full official monthly Swiss Watches & Clocks Exports (SA, Mil. CHF, 2012-01..present) from SNB API."""
    url = "https://data.snb.ch/api/cube/ausshawarm/data/csv/en?dimSel=D0(A),D1(C2652)&fromDate=1988-01"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        body = urllib.request.urlopen(req, timeout=20).read().decode("utf-8-sig")
        exp_map = {}
        for row in csv.reader(io.StringIO(body), delimiter=";"):
            if len(row) < 5:
                continue
            ym, d0, d1, d2, val_s = row[0], row[1], row[2], row[3], row[4]
            if d0 == "A" and d1 == "C2652" and d2 == "WMF" and val_s and re.match(r"^\d{4}-\d{2}$", ym):
                exp_map[f"{ym}-01"] = float(val_s)

        if not exp_map:
            return {"ok": False, "error": "no_snb_rows"}

        exp_vals = save_series(
            "LUX_SWISS_WATCH_EXPORTS",
            exp_map,
            {
                "source": "Swiss National Bank (SNB / BAZG) cube ausshawarm D0=A D1=C2652 D2=WMF",
                "unit": "Mil CHF (SA)",
            },
        )
        yoy_map = {}
        for dt, cur_val in exp_map.items():
            yr = int(dt[:4]) - 1
            prev_dt = f"{yr:04d}{dt[4:]}"
            prev_val = exp_map.get(prev_dt)
            if prev_val and prev_val > 0:
                yoy_map[dt] = (cur_val / prev_val - 1.0) * 100.0

        yoy_vals = save_series(
            "LUX_SWISS_WATCH_YOY",
            yoy_map,
            {
                "source": "Swiss National Bank (SNB / BAZG) cube ausshawarm D0=A D1=C2652 YoY%",
                "unit": "%",
            },
        )
        return {
            "ok": True,
            "exportPoints": len(exp_vals),
            "yoyPoints": len(yoy_vals),
            "firstDate": yoy_vals[0][0] if yoy_vals else None,
            "lastDate": yoy_vals[-1][0] if yoy_vals else None,
            "lastYoY": yoy_vals[-1][1] if yoy_vals else None,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def main():
    subdial_res = update_subdial()
    snb_res = update_snb_swiss_watch_exports()
    any_ok = any(v.get("ok") for v in subdial_res.values()) or snb_res.get("ok")
    out = {"ok": any_ok, "subdial": subdial_res, "snb_swiss_watches": snb_res}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
