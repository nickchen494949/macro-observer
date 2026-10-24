import json
for s in ['CL=F', 'NG=F', 'GC=F', 'HG=F', 'ZW=F', 'ZS=F']:
    j = json.load(open(f'data/yahoo/{s}.json'))
    print(s, j.get('updated'), j['values'][-4:])
for f in ['DCOILWTICO', 'DHHNGSP']:
    try:
        j = json.load(open(f'data/fred/{f}.json')); print(f, j['values'][-3:])
    except Exception as e: print(f, e)
j = json.load(open('data/valuation/BDI.json')); print('BDI', j['values'][-3:] if 'values' in j else str(j)[:200])
