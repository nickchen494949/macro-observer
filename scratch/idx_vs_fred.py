import json
pairs = [('_GSPC', 'SP500'), ('_DJI', 'DJIA'), ('_IXIC', 'NASDAQCOM')]
for y, f in pairs:
    ya = {d: v for d, v in json.load(open(f'data/yahoo/{y}.json'))['values'] if d >= '2025-10-01'}
    fr = {d: v for d, v in json.load(open(f'data/fred/{f}.json'))['values'] if d >= '2025-10-01' and v is not None}
    common = sorted(set(ya) & set(fr))
    bad = [(d, ya[d], fr[d]) for d in common if abs(ya[d] / fr[d] - 1) > 0.0005]
    print(y, 'common', len(common), 'mismatch', len(bad), bad[-8:])
