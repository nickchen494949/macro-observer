#!/usr/bin/env python3
"""
Auto-renew official US positioning & leverage indicators:
1. FINRA Margin Debt YoY % & Total Margin Debt ($T)
   Source: Official FINRA Margin Statistics Excel (https://www.finra.org/rules-guidance/key-topics/margin-accounts/margin-statistics)
2. CFTC Traders in Financial Futures (TFF) Positioning (% of Open Interest):
   - E-mini S&P 500 (13874A): Asset Manager (Institutional) Net % of Open Interest (CFTC_ES_AM_NET)
   - E-mini Nasdaq-100 (209742 / 20974A): Leveraged Funds (Hedge Funds) Net % of Open Interest (CFTC_NQ_LEV_NET)
   Source: Official CFTC Socrata API (https://publicreporting.cftc.gov/resource/gpe5-46if.json)
"""
import io
import json
import os
import re
import ssl
import urllib.request
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
VAL_DIR = os.path.join(ROOT, "data", "valuation")


def get_ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def update_finra():
    ctx = get_ssl_ctx()
    xlsx_url = "https://www.finra.org/sites/default/files/2021-03/margin-statistics.xlsx"
    # Dynamically check FINRA page in case the xlsx URL changes in the future
    try:
        page_req = urllib.request.Request(
            "https://www.finra.org/rules-guidance/key-topics/margin-accounts/margin-statistics",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(page_req, timeout=12, context=ctx) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        links = re.findall(
            r"(https?://[^\s\"\'<>]+margin-statistics\.xlsx|/sites/default/files/[^\s\"\'<>]+margin-statistics\.xlsx)",
            html,
        )
        if links:
            link = links[0]
            xlsx_url = link if link.startswith("http") else f"https://www.finra.org{link}"
    except Exception:
        pass

    req = urllib.request.Request(xlsx_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
        xlsx_bytes = resp.read()

    xl = pd.ExcelFile(io.BytesIO(xlsx_bytes))
    df = xl.parse(xl.sheet_names[0])
    df = df.rename(
        columns={
            df.columns[0]: "ym",
            df.columns[1]: "margin_debt",
            df.columns[2]: "fc_cash",
            df.columns[3]: "fc_margin",
        }
    )
    df["ym"] = df["ym"].astype(str).str.slice(0, 7)
    df = df[df["ym"].str.match(r"^\d{4}-\d{2}$")].copy()
    df["margin_debt"] = pd.to_numeric(df["margin_debt"], errors="coerce")
    df = df.dropna(subset=["margin_debt"]).sort_values("ym").reset_index(drop=True)

    # Convert YYYY-MM to month-end date string YYYY-MM-28 (or exact month end)
    df["date"] = (pd.to_datetime(df["ym"] + "-01") + pd.offsets.MonthEnd(1)).dt.strftime("%Y-%m-%d")
    df["debt_trillions"] = (df["margin_debt"] / 1_000_000.0).round(3)
    df["margin_yoy"] = (df["margin_debt"].pct_change(12) * 100.0).round(2)
    df["max_yoy_12m"] = df["margin_yoy"].rolling(12).max().round(2)

    os.makedirs(VAL_DIR, exist_ok=True)

    # Save FINRA_MARGIN_DEBT.json ($T)
    debt_vals = [[r["date"], float(r["debt_trillions"])] for _, r in df.iterrows()]
    with open(os.path.join(VAL_DIR, "FINRA_MARGIN_DEBT.json"), "w", encoding="utf-8") as f:
        json.dump({"id": "FINRA_MARGIN_DEBT", "values": debt_vals}, f, indent=2)

    # Save FINRA_MARGIN_YOY.json (%)
    yoy_df = df.dropna(subset=["margin_yoy"]).copy()
    yoy_vals = [[r["date"], float(r["margin_yoy"])] for _, r in yoy_df.iterrows()]
    last_row = yoy_df.iloc[-1]
    meta = {
        "lastDate": str(last_row["date"]),
        "lastYm": str(last_row["ym"]),
        "lastYoY": float(last_row["margin_yoy"]),
        "maxYoY12M": float(last_row["max_yoy_12m"]),
        "lastDebtTrillions": float(last_row["debt_trillions"]),
        "rolloverWarning": bool(
            last_row["max_yoy_12m"] > 45.0
            and last_row["margin_yoy"] <= last_row["max_yoy_12m"] - 10.0
        ),
    }
    with open(os.path.join(VAL_DIR, "FINRA_MARGIN_YOY.json"), "w", encoding="utf-8") as f:
        json.dump({"id": "FINRA_MARGIN_YOY", "meta": meta, "values": yoy_vals}, f, indent=2)

    return meta


def fetch_cftc_contract(where_clause, out_id, long_col, short_col):
    ctx = get_ssl_ctx()
    url = (
        "https://publicreporting.cftc.gov/resource/gpe5-46if.json?"
        f"$where={where_clause}&$order=report_date_as_yyyy_mm_dd%20ASC&$limit=5000"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
        raw = json.loads(resp.read().decode("utf-8"))

    df = pd.DataFrame(raw)
    df["date_str"] = df["report_date_as_yyyy_mm_dd"].astype(str).str.slice(0, 10)
    for col in ["open_interest_all", long_col, short_col]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["open_interest_all", long_col, short_col]).copy()
    df = df[df["open_interest_all"] > 0].sort_values("date_str").drop_duplicates("date_str", keep="last").reset_index(drop=True)

    df["net_oi"] = ((df[long_col] - df[short_col]) / df["open_interest_all"] * 100.0).round(2)
    # 3-year (156-week) rolling Z-score
    roll_mean = df["net_oi"].rolling(156, min_periods=52).mean()
    roll_std = df["net_oi"].rolling(156, min_periods=52).std()
    df["z3y"] = ((df["net_oi"] - roll_mean) / roll_std).round(2)

    vals = [[r["date_str"], float(r["net_oi"])] for _, r in df.iterrows()]
    last = df.iloc[-1]
    meta = {
        "lastDate": str(last["date_str"]),
        "lastNetOI": float(last["net_oi"]),
        "lastZ3Y": float(last["z3y"]) if pd.notna(last["z3y"]) else 0.0,
        "points": len(vals),
    }
    os.makedirs(VAL_DIR, exist_ok=True)
    with open(os.path.join(VAL_DIR, f"{out_id}.json"), "w", encoding="utf-8") as f:
        json.dump({"id": out_id, "meta": meta, "values": vals}, f, indent=2)
    return meta


def main():
    result = {"ok": True}
    try:
        result["finra"] = update_finra()
    except Exception as e:
        result["finra_error"] = str(e)

    try:
        result["cftc_es_am"] = fetch_cftc_contract(
            "cftc_contract_market_code=%2713874A%27",
            "CFTC_ES_AM_NET",
            "asset_mgr_positions_long",
            "asset_mgr_positions_short",
        )
    except Exception as e:
        result["cftc_es_error"] = str(e)

    try:
        result["cftc_nq_lev"] = fetch_cftc_contract(
            "cftc_contract_market_code%20in(%27209742%27,%2720974A%27)",
            "CFTC_NQ_LEV_NET",
            "lev_money_positions_long",
            "lev_money_positions_short",
        )
    except Exception as e:
        result["cftc_nq_error"] = str(e)

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
