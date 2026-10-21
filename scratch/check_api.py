import json
d = json.load(open('scratch/sector_eps_api.json'))
print(d['meta']['last_actual_quarter'], d['meta']['file_as_of'], d['meta']['n_values'])
for s in d['sectors']:
    a = s['operating']['actual']
    print(s['sector'], len(a), a[0], a[-1], 'AR:', len(s['as_reported']['actual']))
