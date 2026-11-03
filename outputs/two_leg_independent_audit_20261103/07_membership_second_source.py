"""07 — second-source membership check of every SPY-leg pick against Wikipedia's S&P 500 change log (wiki_changes.csv),
and every QQQ-leg pick against the Wikipedia-vs-YAML Nasdaq-100 comparison (u_wiki_vs_yaml_monthly.csv)."""
import os, sys
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ind_engine as IE
L = pd.read_csv(os.path.join(HERE, 'ind_ledger_G1_SPY_2e.csv'), index_col=0, parse_dates=True)
W = pd.read_csv(os.path.join(IE.D, 'wiki_changes.csv'))
W['date'] = pd.to_datetime(W['date'], errors='coerce')
ev = []
for r in W.itertuples():
    if isinstance(r.added_ticker, str): ev.append((r.added_ticker.replace('.', '-'), r.date, 'add'))
    if isinstance(r.removed_ticker, str): ev.append((r.removed_ticker.replace('.', '-'), r.date, 'remove'))
E = pd.DataFrame(ev, columns=['ticker', 'date', 'type']).dropna().sort_values('date')
rows = []
for t, r in L.iterrows():
    tk = r['spy_pick'].replace('.', '-')
    e = E[E.ticker == tk]
    before = e[e.date <= t]
    status = 'no_wiki_event(long-standing member)' if e.empty else ('member' if (len(before) and before.iloc[-1]['type'] == 'add') else
             ('member(added before wiki log coverage)' if before.empty and e.iloc[0]['type'] == 'remove' else
              'NOT_MEMBER_per_wiki'))
    if before.empty and len(e) and e.iloc[0]['type'] == 'add':
        status = 'NOT_MEMBER_per_wiki (added later)'
    rows.append((t.date(), tk, status, ';'.join(f"{d.date()}:{ty}" for d, ty in zip(e.date, e.type))))
S = pd.DataFrame(rows, columns=['t', 'spy_pick', 'wiki_status', 'wiki_events'])
S.to_csv(os.path.join(HERE, '07_spy_pick_membership_wiki.csv'), index=False)
print(S['wiki_status'].value_counts().to_string())
print(S[S.wiki_status.str.startswith('NOT')].to_string(index=False))
# NDX: Wikipedia monthly roster comparison produced by the earlier clean-room audit
p = os.path.join(IE.ROOT, 'outputs/qqq_mom_top3_claude_audit_20261103/u_wiki_vs_yaml_monthly.csv')
if os.path.exists(p):
    U = pd.read_csv(p); print('\nwiki_vs_yaml file columns:', U.columns.tolist()[:8], len(U))
