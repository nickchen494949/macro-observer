#!/usr/bin/env python3
"""
Parse Yardeni / LSEG sector quarterly Operating EPS workbook (Yardeni_Sector_Operating_EPS.xlsm,
sheet '取值明细') into data/sector_eps/ — REPLACES the previous S&P DJI based files.

Usage:
  python3 build_yardeni_eps.py <path-to-xlsm> [out_dir]      (default out_dir: data/sector_eps)

Output (same schema as the old build_sector_eps.py so server.js / index.html keep working):
  sector_eps_quarterly.csv : index, sector, basis, period, period_end, eps, status, method, sens_2px
  sector_eps_meta.json

IMPORTANT data caveats (carried into meta.note and shown in the dashboard):
  * Only the OPERATING basis exists in this file (no as-reported, no S&P 500 aggregate row).
  * 689 of 700 values are read off a chart curve (approximate; method='curve_approx');
    only the 11 values of the latest quarter are printed on the chart (method='printed').
  * sens_2px = EPS change if the y pixel moves by 2 px. It is NOT an error bound.
"""
import csv
import json
import sys
from datetime import date
from pathlib import Path

import openpyxl

SHEET = "取值明细"
METHOD = {"曲线近似值": "curve_approx", "图中印刷值": "printed"}


def quarter_end(period: str) -> str:
    y, q = int(period[:4]), int(period[5])
    m = q * 3
    d = {3: 31, 6: 30, 9: 30, 12: 31}[m]
    return date(y, m, d).isoformat()


def main():
    xlsm = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/sector_eps")
    out.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.load_workbook(xlsm, data_only=True)
    ws = wb[SHEET]
    rows = []
    for r in ws.iter_rows(min_row=1, values_only=True):
        per, sector, _cn, eps, method, sens = r[0], r[1], r[2], r[3], r[4], r[5]
        if not (isinstance(per, str) and len(per) == 6 and per[4] == "Q" and isinstance(eps, (int, float))):
            continue
        rows.append(dict(index="S&P 500", sector=str(sector).strip(), basis="operating", period=per,
                         period_end=quarter_end(per), eps=round(float(eps), 6), status="actual",
                         method=METHOD.get(method, "curve_approx"),
                         sens_2px=round(float(sens), 4) if isinstance(sens, (int, float)) else ""))
    rows.sort(key=lambda x: (x["sector"], x["period"]))
    if not rows:
        sys.exit("no data rows parsed — wrong sheet layout?")

    cols = ["index", "sector", "basis", "period", "period_end", "eps", "status", "method", "sens_2px"]
    with open(out / "sector_eps_quarterly.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    last = max(r["period"] for r in rows)
    first = min(r["period"] for r in rows)
    n_print = sum(r["method"] == "printed" for r in rows)
    meta = dict(
        source="Yardeni Research / LSEG I/B/E/S — S&P 500 sectors quarterly operating EPS (Figure 11)",
        source_url="https://yardeni.com/charts/us-stock-market/stock-market-fundamentals/sp-500-quarterly-metrics",
        provider="yardeni",
        file_as_of="2026-10-20",
        header_actuals_through=quarter_end(last),
        last_actual_quarter={"operating": last, "as_reported": None},
        first_estimate_quarter={"operating": None, "as_reported": None},
        first_quarter=first,
        n_values=len(rows),
        n_printed=n_print,
        n_curve_approx=len(rows) - n_print,
        note=("Operating EPS only. %d of %d values are read off a chart curve (approximate); "
              "only %d latest-quarter values are printed on the chart. Sector EPS is per sector-index "
              "unit; levels are NOT additive across sectors. Real Estate starts 2016Q3." %
              (len(rows) - n_print, len(rows), n_print)),
    )
    (out / "sector_eps_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    print(f"rows={len(rows)} sectors={len({r['sector'] for r in rows})} {first}..{last} printed={n_print}")


if __name__ == "__main__":
    main()
