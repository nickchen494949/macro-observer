import json

assets = ['SPY', 'QQQ', 'IWM', 'IEF', 'USO', 'GLD']
date_to_fix = '2025-01-09'

for asset in assets:
    path = f"data/yahoo/{asset}.json"
    with open(path) as f:
        data = json.load(f)
        
    vals = data['values']
    
    # check if already there
    has_date = any((v['date'] if isinstance(v, dict) else v[0]) == date_to_fix for v in vals)
    if has_date:
        continue
        
    # find insertion index
    idx_before = -1
    idx_after = -1
    for i, v in enumerate(vals):
        d = v['date'] if isinstance(v, dict) else v[0]
        if d < date_to_fix:
            idx_before = i
        elif d > date_to_fix and idx_after == -1:
            idx_after = i
            
    if idx_before != -1 and idx_after != -1:
        v_b = vals[idx_before]
        v_a = vals[idx_after]
        
        if isinstance(v_b, dict):
            new_v = {
                'date': date_to_fix,
                'open': (v_b['open'] + v_a['open'])/2,
                'high': (v_b['high'] + v_a['high'])/2,
                'low': (v_b['low'] + v_a['low'])/2,
                'close': (v_b['close'] + v_a['close'])/2,
                'adjClose': (v_b['adjClose'] + v_a['adjClose'])/2,
                'volume': (v_b['volume'] + v_a['volume'])/2
            }
        else:
            new_v = [
                date_to_fix,
                (v_b[1] + v_a[1])/2,
                (v_b[2] + v_a[2])/2,
                (v_b[3] + v_a[3])/2,
                (v_b[4] + v_a[4])/2,
                (v_b[5] + v_a[5])/2,
                (v_b[6] + v_a[6])/2
            ]
            
        vals.insert(idx_after, new_v)
        
        with open(path, 'w') as f:
            json.dump(data, f, separators=(',', ':'))
            
        print(f"Fixed {asset} {date_to_fix}")
