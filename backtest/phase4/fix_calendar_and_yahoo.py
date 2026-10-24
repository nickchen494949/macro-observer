import json

# Fix Yahoo data
assets = ['SPY', 'QQQ', 'IWM', 'IEF', 'USO', 'GLD']
for asset in assets:
    path = f"data/yahoo/{asset}.json"
    with open(path) as f:
        data = json.load(f)
    
    vals = data['values']
    # Filter out 2025-01-09
    new_vals = [v for v in vals if (v['date'] if isinstance(v, dict) else v[0]) != '2025-01-09']
    
    if len(new_vals) < len(vals):
        data['values'] = new_vals
        with open(path, 'w') as f:
            json.dump(data, f, separators=(',', ':'))
        print(f"Removed 2025-01-09 from {asset}")

# Fix nyse_calendar.json
with open('data/nyse_calendar.json') as f:
    cal = json.load(f)

if '2025-01-09' in cal:
    cal.remove('2025-01-09')
    with open('data/nyse_calendar.json', 'w') as f:
        json.dump(cal, f)
    print("Removed 2025-01-09 from nyse_calendar.json")

# Audit 2025
holidays_2025 = ['2025-01-01', '2025-01-09', '2025-01-20', '2025-02-17', '2025-04-18', '2025-05-26', '2025-06-19', '2025-07-04', '2025-09-01', '2025-11-27', '2025-12-25']

for h in holidays_2025:
    if h in cal:
        print(f"WARNING: Holiday {h} is still in calendar!")
        cal.remove(h)
        with open('data/nyse_calendar.json', 'w') as f:
            json.dump(cal, f)
        print(f"Removed {h} from nyse_calendar.json")

print("Done fixing calendar and Yahoo data")
