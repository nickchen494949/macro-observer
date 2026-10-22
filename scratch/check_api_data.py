import json
d = json.load(open('scratch/api_data.json'))
print('updated:', d.get('updated'), 'keys ok:', all(k in d for k in ('rates', 'commodities', 'stocks', 'macroState', 'diagnostics')))
for g in d['stocks']:
    for i in g['items']:
        c = i.get('changes', {})
        print('%-24s cur=%-12s 1d=%-7s 1w=%s' % (i['label'], i.get('current'), c.get('1d'), c.get('1w')))
