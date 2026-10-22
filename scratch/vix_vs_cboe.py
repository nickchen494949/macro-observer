import json, csv, datetime
cb = {}
for r in csv.DictReader(open('scratch/VIX_History.csv')):
    m, d, y = r['DATE'].split('/')
    cb[f'{y}-{int(m):02d}-{int(d):02d}'] = float(r['CLOSE'])
ya = json.load(open('data/yahoo/_VIX.json'))['values']
bad = [(d, v, cb[d]) for d, v in ya if d in cb and abs(v - cb[d]) > 0.015]
print('overlap', sum(1 for d, _ in ya if d in cb), 'mismatch', len(bad))
by_year = {}
for d, v, c in bad: by_year[d[:4]] = by_year.get(d[:4], 0) + 1
print(by_year)
for b in bad[-25:]: print(b)
