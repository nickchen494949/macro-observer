"""Minimal counterexamples for v2 shared portfolio fixes, independent expected values."""
import sys,json
from pathlib import Path
import numpy as np
import pandas as pd
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'research/sector_stock_momentum'))
import backtest as bt
import winners_tracks as wt
class PX:
 def ret(self,t,s,res): return (.1,'ok')
forms=pd.date_range('2020-01-31',periods=3,freq='ME')
S={'px':PX(),'res':{},'rf':pd.Series(.01,index=forms+pd.offsets.MonthEnd(1))}
keep=bt.COST_PER_SIDE;bt.COST_PER_SIDE=.001
r=wt.run_weights(S,{forms[0]:{'A':1},forms[1]:{},forms[2]:{}})
assert np.isclose(r.net.iloc[0],1.1/1.001-1)
assert np.isclose(r.net.iloc[1],.999*1.01-1)
assert np.isclose(r.net.iloc[2],.01) and r.turnover.iloc[2]==0
assert r.exposure.tolist()==[1,0,0]
try:wt.run_weights(S,{forms[0]:{},forms[2]:{}});raise AssertionError('missing month allowed')
except ValueError:pass
# Known carry adds to a real flat-price path and reconciles; an unexplained endpoint never does.
dates=pd.bdate_range('2020-01-01','2020-04-30');S['daily']=pd.DataFrame({'A':100.},index=dates)
c=wt.run_weights(S,{t:{} for t in forms});nav=wt.daily_nav(S,c)
assert np.isclose(nav.iloc[-1],1.01**3)
bad=c.copy();bad.iloc[0,bad.columns.get_loc('net')]=.02
try:wt.daily_nav(S,bad);raise AssertionError('invented endpoint accepted')
except ValueError:pass
# A known exit at month end must not receive a whole month of interest on its proceeds.
class ExitPX:
 def ret(self,t,s,res):return (0.,'resolved')
bt.COST_PER_SIDE=0;S['px']=ExitPX()
tr=wt.tranche_ledger(S,{forms[0]:{'A':1},forms[1]:{}},hold=1)
assert np.isclose(tr.net.iloc[0],0) and np.isclose(tr.net.iloc[1],.01)
# Leverage wipeout cannot revive or charge later trades.
class LossPX:
 def ret(self,t,s,res):return (-.8,'ok')
S['px']=LossPX();L=wt.run_weights(S,{t:{'A':1} for t in forms},{t:1.5 for t in forms})
assert L.net.tolist()==[-1,0,0] and L.turnover.iloc[1:].eq(0).all()
bt.COST_PER_SIDE=keep
out={'status':'PASS','checks':['self_financing_entry','exit_to_cash','empty_month_interest','cash_no_churn','missing_month_rejected','known_carry_daily_path','residual_not_smoothed','exit_cash_no_early_interest','bankruptcy_absorbing']}
(R/'audit_v2/root_ledger_gate.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
