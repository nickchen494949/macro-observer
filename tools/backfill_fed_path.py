#!/usr/bin/env python3
import json, os, time, datetime, urllib.request, urllib.parse
from pathlib import Path

START_DATE = "2000-01-01"
DATA_DIR   = Path("/Users/happygolucky/projects/宏观观察器/data")
YAHOO_DIR  = DATA_DIR / "yahoo"
VAL_DIR    = DATA_DIR / "valuation"
SLEEP_SEC  = 1.5

MONTH_CODES = {1:"F",2:"G",3:"H",4:"J",5:"K",6:"M",7:"N",8:"Q",9:"U",10:"V",11:"X",12:"Z"}

def fetch_yahoo_history(symbol):
    cache_file = YAHOO_DIR / (symbol.replace("/","_") + ".json")
    if cache_file.exists():
        d = json.loads(cache_file.read_text())
        vals = d.get("values", [])
        if vals:
            print(f"  cache {symbol}: {len(vals)} obs {vals[0][0]}to{vals[-1][0]}")
            return vals
    start_ts = int(datetime.datetime.strptime(START_DATE, "%Y-%m-%d").timestamp())
    end_ts   = int(datetime.datetime.now().timestamp()) + 86400
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(symbol) +
        "?interval=1d&period1=" + str(start_ts) + "&period2=" + str(end_ts) + "&events=history"
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        closes = result["indicators"]["quote"][0]["close"]
        vals = []
        for ts, c in zip(timestamps, closes):
            if c is None: continue
            date_str = datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
            vals.append([date_str, round(c, 4)])
        if vals:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps({"id": symbol, "updated": datetime.datetime.utcnow().isoformat()+"Z", "values": vals}))
            print(f"  fetch {symbol}: {len(vals)} obs {vals[0][0]}to{vals[-1][0]}")
        else:
            print(f"  empty {symbol}")
        return vals
    except Exception as e:
        print(f"  FAIL {symbol}: {e}")
        return []

# 2000-2028 = 348 contracts
contracts = [(y, m, "ZQ" + MONTH_CODES[m] + str(y)[-2:] + ".CBT") for y in range(2000, 2029) for m in range(1, 13)]
print("Downloading " + str(len(contracts)) + " ZQ contracts (2000-2028)...")
price_db = {}
for i, (year, month, symbol) in enumerate(contracts):
    print("[" + str(i+1) + "/" + str(len(contracts)) + "] ", end="")
    vals = fetch_yahoo_history(symbol)
    if vals:
        price_db[symbol] = {v[0]: v[1] for v in vals}
    time.sleep(SLEEP_SEC)

print("\nGot data for " + str(len(price_db)) + " contracts")
print("Building path snapshots...")

all_dates = set()
for prices in price_db.values():
    all_dates.update(prices.keys())
all_dates = sorted(d for d in all_dates if START_DATE <= d <= datetime.date.today().isoformat())
print("Trading days: " + str(len(all_dates)) + " (" + all_dates[0] + " to " + all_dates[-1] + ")")

new_history = []
for date_str in all_dates:
    dt = datetime.date.fromisoformat(date_str)
    path = []
    for offset in range(18):
        tm = dt.month + offset
        ty = dt.year + (tm - 1) // 12
        tm = ((tm - 1) % 12) + 1
        sym = "ZQ" + MONTH_CODES[tm] + str(ty)[-2:] + ".CBT"
        prices = price_db.get(sym, {})
        price = prices.get(date_str)
        if price is None:
            for back in range(1, 6):
                d2 = (dt - datetime.timedelta(days=back)).isoformat()
                if d2 in prices:
                    price = prices[d2]
                    break
        if price and price > 0:
            path.append({"month": str(ty) + "-" + str(tm).zfill(2), "rate": round(100 - price, 4), "price": round(price, 4)})
    if len(path) >= 3:
        new_history.append([date_str, path])

print("Built " + str(len(new_history)) + " snapshots")
print("Merging with existing...")

hist_file = VAL_DIR / "FED_PATH_HISTORY.json"
existing = []
if hist_file.exists():
    d = json.loads(hist_file.read_text())
    existing = d.get("values", [])
    print("Existing: " + str(len(existing)) + " snapshots")

new_dates = {h[0] for h in new_history}
kept = [h for h in existing if h[0] not in new_dates]
merged = sorted(new_history + kept, key=lambda x: x[0])
print("Merged: " + str(len(merged)) + " snapshots (" + merged[0][0] + " to " + merged[-1][0] + ")")

VAL_DIR.mkdir(parents=True, exist_ok=True)
hist_file.write_text(json.dumps({"id": "FED_PATH_HISTORY", "updated": datetime.datetime.utcnow().isoformat()+"Z", "values": merged}))
cp_path = str(DATA_DIR / "yahoo")
print("DONE. Saved to " + str(hist_file))
print("Individual ZQ contract files saved to " + cp_path)
