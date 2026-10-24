import json
d = json.load(open('scratch/api_data.json'))
pm = json.load(open('scratch/pm.json'))
print('live session', pm['session'], 'active', pm['active'])
for sect in ('stocks', 'commodities'):
    groups = d[sect] if sect == 'commodities' else [i for g in d['stocks'] for i in g['items']]
    for i in groups:
        it = pm['items'].get(i.get('chartKey'))
        if not it: continue
        c1 = i.get('changes', {}).get('1d')
        flag = '' if c1 is not None and abs(c1 - it['pct']) < 0.06 else '  <-- MISMATCH'
        print('%-22s cur=%-11s 1d=%-6s | live=%-6s price=%-10s prev=%-10s %s%s' % (i['label'][:22], i.get('current'), c1, it['pct'], it['price'], it['prev'], it['kind'], flag))
