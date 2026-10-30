"""Index only existing candidates with actually generated ledgers."""
import hashlib, json
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'research/sector_stock_momentum'
ML, EX = SRC / 'results/ml', SRC / 'results/explosive'
rows = []
def add(family, name, summary, ledger, fixed=False, gross=False, extra=None):
    assert ledger.is_file(), ledger
    d = pd.read_csv(ledger)
    date_column = 'month' if 'month' in d else d.columns[0]
    d['month'] = pd.to_datetime(d[date_column])
    rec = {'family': family, 'name': name, 'summary_path': str(summary.relative_to(ROOT)),
           'ledger_path': str(ledger.relative_to(ROOT)), 'date_column': date_column,
           'sha256': hashlib.sha256(ledger.read_bytes()).hexdigest(),
           'frequency': 'buy-and-hold; monthly return observations' if gross else 'monthly target rebalance',
           'execution': 'formation month-end close to next month-end close; idealised same-close signal execution',
           'cost': 'gross, no transaction costs' if gross else '0.10% per side on actual drifted turnover; paid before investing',
           'evidence_role': ('development factor fit before 2023; retrospective temporal test from 2023' if fixed
                             else 'retrospective cached-data rerun; not a new untouched test'),
           'valid_comparison_start': '2023-01-31' if fixed else str(d.month.min().date()),
           'first_month': str(d.month.min().date()), 'last_month': str(d.month.max().date()), 'months': len(d),
           'limitations': ['Historical membership, industry classifications, SEC input identity and delisting source completeness not independently certified',
                           'Same-close execution is idealised; not next-open executable proof',
                           'Monthly drawdown can miss within-month losses; see risk_report daily availability'],
           'run_status': 'completed, writer checks pending independent review'}
    if fixed:
        rec['limitations'].append('Do not rank pre-2023 returns as if the fixed factor set was selected before those years')
    if 'unresolved_outcomes' in d:
        rec['unresolved_outcomes'] = int(d.unresolved_outcomes.sum())
    if extra:
        rec.update(extra)
    rows.append(rec)
chosen = json.loads((ML / 'selection.json').read_text())
for model in ['mom', 'composite', 'ridge', 'lgbm_s', 'lgbm_m', 'lgbm_rank']:
    for rule in ['top1', 'top1_sma200', 'top5', 'top20']:
        add('legacy_ml', f'{model} / {rule}', ML / 'holdout.json', ML / f'holdout_{model}_{rule}.csv',
            extra={'development_ledger_path': str((ML / f'dev_{model}_{rule}.csv').relative_to(ROOT)),
                   'development_summary_path': str((ML / 'selection.json').relative_to(ROOT)),
                   'chosen_by_development_only': model == chosen['chosen_model'] and rule == chosen['chosen_rule'],
                   'annual_training': True})
for family, filename, prefix, truncate in [('explosive_v1', 'composite_portfolios.csv', 'v1_', None),
                                           ('explosive_v2', 'v2_portfolios.csv', 'v2_', None),
                                           ('explosive_v3', 'v3_summary.csv', 'v3_', 60)]:
    summary = EX / filename
    for name in pd.read_csv(summary).strategy.unique():
        safe = ''.join(c if c.isalnum() else '_' for c in name)
        if truncate:
            safe = safe[:truncate]
        fixed = (family in ('explosive_v1', 'explosive_v2') and name not in ('SPY', 'XLK')) or '[fixed]' in name
        add(family, name, summary, EX / f'{prefix}{safe}.csv', fixed=fixed, gross=name in ('SPY', 'XLK'))
for name in pd.read_csv(EX / 'ear_portfolios.csv').strategy.unique():
    tag = name.removeprefix('tech top-5 inv-vol, ')
    safe = ''.join(c if c.isalnum() else '_' for c in tag)
    add('earnings_reaction_extension', name, EX / 'ear_portfolios.csv', EX / f'ear_monthly_{safe}.csv', fixed=True)
(ROOT / 'audit_v2/legacy_ml_strategy_index.json').write_text(json.dumps(rows, indent=2, ensure_ascii=False))
print(json.dumps({'strategies': len(rows), 'by_family': pd.Series([r['family'] for r in rows]).value_counts().to_dict()}))
