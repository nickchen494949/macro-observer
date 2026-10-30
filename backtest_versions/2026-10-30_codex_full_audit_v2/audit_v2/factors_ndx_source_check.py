"""Verify cached Nasdaq membership assembly; this does not certify its upstream accuracy."""
import hashlib
import json
from pathlib import Path
import sys
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT/'research/sector_stock_momentum'
sys.path.insert(0, str(SRC))
from build_ndx_membership import tickers_as_of
from ndx_universe import symbol_map
from ndx_expand import cik_at, t2c_map

data = SRC/'data'
mm = pd.read_csv(data/'ndx_monthly_members.csv', parse_dates=['month_end'])
sp = pd.read_csv(data/'ndx_spells.csv', parse_dates=['start_date','end_date'])
diffs, spell_diffs = [], []
for t,g in mm.groupby('month_end'):
    expected = {x.replace('.', '-') for x in tickers_as_of(t.date())}
    actual = set(g.ticker)
    if actual != expected:
        diffs.append({'t':str(t),'missing':sorted(expected-actual),'extra':sorted(actual-expected)})
    active = set(sp.loc[(sp.start_date <= t) & (sp.end_date.isna() | (sp.end_date >= t)), 'ticker'])
    if active != actual:
        spell_diffs.append({'t':str(t),'missing':sorted(active-actual),'extra':sorted(actual-active)})
mapping = symbol_map()
mapped_counts = mm.assign(mapped=mm.ticker.map(lambda s:mapping.get(s,s))).dropna(subset=['mapped']).groupby('month_end').mapped.nunique()
skipped = sorted({t for t in mm.ticker if t in mapping and mapping[t] is None})
cm = t2c_map()
identity_conflicts = []
for t,g in mm.groupby('month_end'):
    for s in sorted({mapping.get(s,s) for s in g.ticker} - {None}):
        try:
            cik_at(cm.get(s,[]), t)
        except ValueError as exc:
            identity_conflicts.append(str(exc))
files = sorted((data/'nasdaq100_src').glob('*')) + [data/n for n in
 ['ndx_monthly_members.csv','ndx_spells.csv','ndx_cik_map.csv','ndx_symbol_map.csv','ndx_sectors.csv']]
out = {'assembly_status': 'PASS' if not(diffs or spell_diffs or identity_conflicts) else 'FAIL',
       'official_historical_membership_certified': False, 'historical_sector_labels_certified': False,
       'limitations':['Membership is a frozen third-party YAML reconstruction, not official Nasdaq constituent files.',
                      'Current metadata plus dated overrides cannot independently prove every historical industry label.',
                      'Explicitly skipped or identity-rejected names remain coverage gaps; do not replace with current survivors.'],
       'months': int(mm.month_end.nunique()), 'min_members': int(mm.groupby('month_end').size().min()),
       'max_members': int(mm.groupby('month_end').size().max()), 'duplicate_ticker_months':int(mm.duplicated(['month_end','ticker']).sum()),
       'min_mapped_members':int(mapped_counts.min()),'max_mapped_members':int(mapped_counts.max()),
       'membership_diffs':diffs,'spell_diffs':spell_diffs,'identity_conflicts':identity_conflicts,
       'skipped_symbols':skipped,
       'input_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()}}
(ROOT/'audit_v2/factors_ndx_source_check.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in out.items() if k!='input_hashes'},ensure_ascii=False,indent=2))
assert out['assembly_status']=='PASS' and out['duplicate_ticker_months']==0
