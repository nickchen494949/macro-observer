from pathlib import Path
import sys,json,hashlib,os
import pandas as pd,numpy as np
R=Path(__file__).resolve().parents[1];H=R/'research/sector_stock_momentum';sys.path.insert(0,str(H))
import backtest as bt,winners_tracks as wt,winners_holdout as wh
bt.RES=str(R/'audit_v2/root_price_diagnostics');checks=[]
# Main daily metric only: monthly selections/returns are already rerun under final execution code.
p=H/'results/monthly_SPEC.csv';d=pd.read_csv(p,index_col='month',parse_dates=['month','formation']);before=hashlib.sha256(p.read_bytes()).hexdigest()
daily,*_=bt.load_prices()
try:
 nav=bt.daily_nav(d,daily);n=pd.concat([pd.Series([1.]),nav.reset_index(drop=True)]);dd=float((n/n.cummax()-1).min());status='observed gross closes, no missing holding-day quotes'
except ValueError as e:dd=None;status=str(e)
f=H/'results/summary.json';j=json.loads(f.read_text());j['meta']['spec_daily_maxDD_gross']=dd;j['meta']['spec_daily_maxDD_status']=status;f.write_text(json.dumps(j,indent=1))
checks.append({'scope':'main daily summary','monthly_sha256_unchanged':before==hashlib.sha256(p.read_bytes()).hexdigest(),'status':status})
# Existing holdout rules do not use voltarget; refresh only daily risk metadata from original ledgers.
wt.PERIODS={'PRIMARY 2010-01..2018-02':wh.PRIMARY,'PRIMARY from 2013 (T2 starts 2013)':('2013-01-31',wh.PRIMARY[1]),'SECONDARY 2018-03..2026-09 (survivorship-biased)':wh.SECONDARY}
for strict in [False,True]:
 os.environ['STRICT']='1' if strict else '0';tag='_STRICT' if strict else '';form=pd.date_range('2009-12-31','2026-08-31',freq='ME')
 A,P,U,mom,src=wh.load(form);S={'px':bt.Prices(A,P,0),'daily':A,'rf':bt.load_rf(pd.date_range('2009-01-31','2026-10-31',freq='ME'))}
 sp=H/'results/winners_holdout'/f'summary{tag}.csv';old=pd.read_csv(sp);out=[]
 for (name,scenario,listing),g in old.groupby(['strategy','scenario','list'],sort=False):
  assert 'voltarget' not in name and '+all' not in name
  safe=''.join(c if c.isalnum() else '_' for c in f'{name} {scenario}');p=sp.parent/f'monthly_{safe}{tag}.csv';h=hashlib.sha256(p.read_bytes()).hexdigest()
  df=pd.read_csv(p,index_col='month',parse_dates=['month']);df['weights']=df.weights.fillna('').astype(str)
  rows=wt.stats_block(S,df,name)
  for rec in rows:
   rec['scenario']=scenario;rec['list']=listing
   before_row=g[g.period==rec['period']].iloc[0]
   for key in ['CAGR','Sharpe','vol','maxDD_month_end']:
    assert np.isclose(rec[key],before_row[key],equal_nan=True,rtol=1e-10,atol=1e-10),(name,key)
   out.append(rec)
  checks.append({'scope':f'{name} / {scenario}{tag}','monthly_sha256_unchanged':h==hashlib.sha256(p.read_bytes()).hexdigest(),'daily_status':rows[0]['daily_nav_status']})
 pd.DataFrame(out).to_csv(sp,index=False)
(R/'audit_v2/root_daily_refresh.json').write_text(json.dumps({'status':'PASS','checks':checks},indent=2));print('PASS',len(checks),'monthly ledgers unchanged; daily metrics refreshed')
