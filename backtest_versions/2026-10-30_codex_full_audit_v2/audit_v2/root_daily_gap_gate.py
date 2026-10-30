from pathlib import Path
import sys,json
import numpy as np,pandas as pd
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'research/sector_stock_momentum'))
import backtest as bt,winners_tracks as w
idx=pd.to_datetime(['2020-01-31','2020-02-03','2020-02-28']);d=pd.DataFrame({'A':[100.,np.nan,110.],'SPY':[100.,100.,100.]},index=idx)
df=pd.DataFrame({'formation':[idx[0]],'picks':['A'],'weights':['1.0'],'exposure':[1.],'gross':[.1],'net':[.1],'capital_after_costs':[1.]},index=pd.to_datetime(['2020-02-29']))
for fn in [lambda:bt.daily_nav(df,d),lambda:w.daily_nav({'daily':d,'rf':pd.Series(0.,index=df.index)},df)]:
 try:fn()
 except ValueError as e:assert 'missing observed' in str(e)
 else:raise AssertionError('invented flat path accepted')
(R/'audit_v2/root_daily_gap_gate.json').write_text(json.dumps({'status':'PASS','checks':['main missing midmonth close rejected','winners missing midmonth close rejected']}));print('PASS')
