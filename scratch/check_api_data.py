import json
d = json.load(open('scratch/api_data.json'))
print('keys:', list(d.keys())[:40])
print('updated:', d.get('updated'), 'yahooLoaded', d.get('yahooLoaded'))
for g in d['stocks']:
    for i in g['items']:
        if i['label'] in ('S&P 500', 'Dow Jones', 'Nasdaq', 'XLK 科技股', 'VIX'):
            print(g.get('group'), i['label'], 'current', i.get('current'), '1d', i.get('changes', {}).get('1d'), 'lastObs', i.get('lastObsDate'))
# store view
for k in ('commodities',):
    for i in d[k][:4]:
        print(k, i['label'], i.get('current'), i.get('changes', {}).get('1d'), i.get('lastDate') or i.get('lastObsDate'))
