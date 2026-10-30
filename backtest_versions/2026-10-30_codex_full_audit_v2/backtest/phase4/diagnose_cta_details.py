import json
import os

assets = ['SPY', 'QQQ', 'IWM', 'IEF', 'USO', 'GLD']
nyse_cal_path = 'data/nyse_calendar.json'
with open(nyse_cal_path) as f:
    nyse_cal = set(json.load(f))

results = []

for asset in assets:
    path = f"data/yahoo/{asset}.json"
    if not os.path.exists(path):
        print(f"Missing {asset}")
        continue
        
    with open(path) as f:
        data = json.load(f)
        
    vals = data.get('values', [])
    dates = [v['date'] if isinstance(v, dict) else v[0] for v in vals]
    
    first_dt = dates[0] if dates else 'N/A'
    last_dt = dates[-1] if dates else 'N/A'
    
    # 2025 check
    dates_2025 = set(d for d in dates if d.startswith('2025'))
    nyse_2025 = set(d for d in nyse_cal if d.startswith('2025'))
    
    missing_2025 = sorted(list(nyse_2025 - dates_2025))
    missing_count = len(missing_2025)
    
    print(f"--- {asset} ---")
    print(f"First cached session: {first_dt}")
    print(f"Last cached session: {last_dt}")
    print(f"Expected NYSE sessions (2025): {len(nyse_2025)}")
    print(f"Missing session count (2025): {missing_count}")
    print(f"Exact missing dates: {missing_2025[:10]} ...")
    
    # Simulate alignToCalendar (<201 check)
    # The CTA needs 201 days BEFORE a given date. If the total length before a date is < 201, it fails.
    invalid_days = 0
    for cal_date in sorted(list(nyse_2025)):
        valid_history = [d for d in dates if d <= cal_date]
        if len(valid_history) < 201:
            invalid_days += 1
            
    print(f"Causes missing_data due to < 201? {'Yes' if invalid_days > 0 else 'No'}")
    print(f"Number of CTA invalid days attributable to this asset in 2025: {invalid_days}")
    print()
