import json
d = json.load(open('scratch/api_data.json'))
pm = json.load(open('scratch/pm.json'))
print('keys ok:', all(k in d for k in ('rates', 'commodities', 'stocks', 'macroState', 'diagnostics')))
print('live: active', pm['active'], 'session', pm['session'], 'n', len(pm['items']), 'err', pm['error'])
for g in d['stocks']:
    for i in g['items']:
        c = i.get('changes', {})
        it = pm['items'].get(i.get('chartKey'), {})
        print('%-26s cur=%-11s 1d=%-6s live=%s %s' % (i['label'], i.get('current'), c.get('1d'), it.get('pct'), it.get('kind', '')))
for i in d['commodities']:
    print('%-26s cur=%-11s 1d=%s' % (i['label'], i.get('current'), i.get('changes', {}).get('1d')))
