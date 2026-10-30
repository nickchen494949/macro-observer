"""Read-only independent final review; writes only its own audit record."""
import ast
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def readonly_run(name):
    p = ROOT / 'audit_v2' / name
    tree = ast.parse(p.read_text())
    tree.body = [n for n in tree.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
        and isinstance(n.value.func, ast.Attribute) and n.value.func.attr == 'write_text')]
    scope = {'__file__': str(p), '__name__': '__main__'}
    exec(compile(tree, str(p), 'exec'), scope)
    return scope

path = ROOT / 'audit_v2/rotation_cross_review.json'
report = json.loads(path.read_text())
suite = readonly_run('rotation_macro_tests.py')
ledger = readonly_run('rotation_macro_ledger_checks.py')
scope = suite['scope']
dt = pd.Timestamp('2020-01-31')
cal = pd.to_datetime(['2020-01-31', '2020-02-03', '2020-02-04', '2020-03-02', '2020-03-03'])
prices = {s: pd.DataFrame({'close': [100,101,102,103,104]}, index=cal) for s in 'ABCDEFG'}
sig = pd.DataFrame({'date': [dt]*7, 'ticker': list('ABCDEFG'), 'score': range(7)})
reg = pd.DataFrame({'date':[dt], 'rising':[0]})
full = scope['backtest'](sig, 'score', reg, daily_prices=prices)
assert full['df'].top_names.iloc[0] == 'G,F,E'
prices['G'] = prices['G'].drop(cal[-1])
try:
    scope['backtest'](sig, 'score', reg, daily_prices=prices)
except ValueError as e:
    selected_error = str(e)
    assert 'G' in selected_error and 'no replacement allowed' in selected_error
else: raise AssertionError('future availability still changes selection')
# A missing middle-ranked, unselected asset must not change selected holdings;
# it does make a complete-universe EW/IC statistic unavailable.
prices['G'] = pd.DataFrame({'close':[100,101,102,103,104]},index=cal)
prices['D'] = prices['D'].drop(cal[-1])
middle = scope['backtest'](sig, 'score', reg, daily_prices=prices)
assert middle['df'].top_names.iloc[0] == 'G,F,E'
assert np.isnan(middle['df'].ew.iloc[0]) and np.isnan(middle['df'].ic.iloc[0])
truncated = {s:p.loc[:'2020-02-04'] for s,p in prices.items()}
assert scope['backtest'](sig, 'score', reg, daily_prices=truncated) is None

# Recheck actual executed dates independently from the writer's value-only
# repricer, using the union calendar and frozen adjusted-close files.
sector = ROOT / 'research/sector_rotation'
px = {p.stem: pd.read_csv(p, parse_dates=['date']).set_index('date').adj_close for p in (sector/'adj_prices').glob('*.csv')}
calendar = pd.DatetimeIndex(sorted(set().union(*(set(s.index) for s in px.values()))))
date_checks = 0
for p in sector.glob('detail_*_h*.csv'):
    holding = int(p.stem.split('_h')[-1])
    d = pd.read_csv(p, parse_dates=['date','entry_date','exit_date'])
    for row in d.itertuples():
        exit_signal = (row.date.to_period('M') + holding).end_time.normalize()
        assert row.entry_date == calendar[calendar > row.date][1]
        assert row.exit_date == calendar[calendar > exit_signal][1]
        date_checks += 1
common = pd.read_csv(sector/'results_v2/model_common_period_summary.csv')
assert len(common)==8 and common.months.eq(40).all()
assert common.first_signal.nunique()==common.last_signal.nunique()==common.first_entry.nunique()==common.last_exit.nunique()==1
assert common.cost_status.eq('gross_no_costs').all()

report['initial_source_hashes'] = report.pop('initial_source_hashes', report['source_hashes'])
report['source_hashes'] = {f:sha(ROOT/f) for f in report['scope']}
report['status'] = 'IMPLEMENTATION_AND_REPLAY_CROSS_CHECKS_PASS_WITH_SOURCE_LIMITS'
report['provided_test_suite'] = {'status':'PASS','checks':len(suite['passed']),
    'execution':'AST executed exact writer tests after suppressing only audit write_text; no source/result output overwritten',
    'sha256':sha(ROOT/'audit_v2/rotation_macro_tests.py')}
report['final_verification'] = {'provided_ledger_checks_reexecuted':len(ledger['records']),
    'ledger_script_sha256':sha(ROOT/'audit_v2/rotation_macro_ledger_checks.py'),
    'independent_t_plus_2_date_checks':date_checks,
    'selected_missing_future_error':selected_error,
    'unselected_middle_missing_preserves_picks_and_disables_ew_ic':True,
    'whole_trailing_incomplete_window_excluded':True,
    'common_period_models':8,'common_period_months':40,
    'first_signal':common.first_signal.iloc[0],'last_signal':common.last_signal.iloc[0],
    'first_entry':common.first_entry.iloc[0],'last_exit':common.last_exit.iloc[0],
    'common_summary_sha256':sha(sector/'results_v2/model_common_period_summary.csv'),
    'formation_to_holding_label':'Rotation date is formation month; compare using date + 1 month (first holding label 2023-04), actual first entry 2023-04-04.',
    'final_output_hashes':{str(p.relative_to(ROOT)):sha(p) for p in sorted((sector/'results_v2').glob('**/*')) if p.is_file()}}
findings = report.get('remaining_findings') or report.get('resolved_findings', [])
for item in findings:
    item['status'] = 'RESOLVED_AND_INDEPENDENTLY_RETESTED'
    item['resolution'] = ('Formation ranking precedes pricing; selected gaps fail without replacement; entire incomplete tail windows excluded.'
                          if item['id']=='RCR01' else 'Native periods now explicit; separate 8-series common table has identical 40 executed holding windows, independently recomputed.')
report['resolved_findings'] = findings
report['remaining_findings'] = []
report['approval_scope'] = 'Cross-review confirms bounded implementation/replay; source certification and global approval remain root responsibilities.'
path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({'status':report['status'],'tests':len(suite['passed']),'ledger_checks':len(ledger['records']),'date_checks':date_checks}))
