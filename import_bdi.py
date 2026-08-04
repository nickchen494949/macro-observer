#!/usr/bin/env python3
"""
Import Baltic Dry Index CSV from Investing.com into the macro dashboard.

Usage:
  1. Download CSV from https://www.investing.com/indices/baltic-dry-historical-data
     (set date range to MAX, click Download)
  2. Move the downloaded file to this folder (Desktop/宏观观察器/)
  3. Run: python3 import_bdi.py <filename.csv>
     Or just: python3 import_bdi.py   (auto-detects Baltic*.csv in current dir)
"""
import csv, json, os, sys, glob
from datetime import datetime

out_dir = os.path.join(os.path.dirname(__file__), 'data', 'valuation')
os.makedirs(out_dir, exist_ok=True)

# Auto-detect input file
if len(sys.argv) > 1:
    fpath = sys.argv[1]
else:
    candidates = glob.glob('Baltic*.csv') + glob.glob('baltic*.csv') + glob.glob('*Baltic*Dry*.csv')
    if not candidates:
        print('❌ No Baltic*.csv found. Pass filename as argument.')
        sys.exit(1)
    fpath = candidates[0]
    print(f'📄 Auto-detected: {fpath}')

values = []
with open(fpath, encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    headers = reader.fieldnames
    print('Columns:', headers)
    for row in reader:
        # Investing.com columns: Date, Price, Open, High, Low, Change %
        date_raw = row.get('Date','').strip()
        price_raw = row.get('Price','').strip().replace(',','')
        if not date_raw or not price_raw or price_raw == '-':
            continue
        try:
            # Investing.com date format: "Jul 18, 2025" or "07/18/2025"
            for fmt in ('%b %d, %Y', '%m/%d/%Y', '%Y-%m-%d'):
                try:
                    dt = datetime.strptime(date_raw, fmt)
                    break
                except: pass
            else:
                print(f'  ⚠️  Could not parse date: {date_raw}')
                continue
            values.append([dt.strftime('%Y-%m-%d'), float(price_raw)])
        except Exception as e:
            print(f'  ⚠️  Skipped row {row}: {e}')

values.sort(key=lambda x: x[0])
# Filter to 1973+
values = [v for v in values if v[0] >= '1973-01-01']

print(f'✅ Parsed {len(values)} BDI data points')
print(f'   Range: {values[0][0]} → {values[-1]}')

out = {
    'id': 'BDI',
    'source': 'investing.com',
    'updated': datetime.utcnow().isoformat() + 'Z',
    'values': values
}
out_path = os.path.join(out_dir, 'BDI.json')
with open(out_path, 'w') as f:
    json.dump(out, f)

print(f'💾 Saved to {out_path}')
print()
print('Now restart the server and add BDI to COMMODITY_ROWS in server.js')
