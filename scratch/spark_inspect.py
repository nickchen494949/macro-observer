import json
d = json.load(open('scratch/spark_test.json'))
print(type(d), list(d.keys())[:10])
for k, v in d.items():
    if isinstance(v, dict):
        print(k, {kk: (vv if not isinstance(vv, list) else f'list[{len(vv)}] last={vv[-1] if vv else None}') for kk, vv in v.items()})
