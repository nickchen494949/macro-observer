import json
import os

assets = ['SPY', 'QQQ', 'IWM', 'IEF', 'USO', 'GLD']
years = ['2025', '2026']

for asset in assets:
    path = f"data/yahoo/{asset}.json"
    if not os.path.exists(path):
        print(f"Missing {asset}")
        continue
        
    with open(path) as f:
        data = json.load(f)
        
    vals = data.get('values', [])
    
    for year in years:
        year_vals = [v for v in vals if (v['date'] if isinstance(v, dict) else v[0]).startswith(year)]
        if not year_vals:
            print(f"{asset} {year}: 0 dates")
        else:
            dates = [v['date'] if isinstance(v, dict) else v[0] for v in year_vals]
            print(f"{asset} {year}: {len(dates)} dates ({dates[0]} to {dates[-1]})")
