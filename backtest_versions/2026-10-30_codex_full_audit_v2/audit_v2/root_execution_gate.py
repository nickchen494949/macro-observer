from pathlib import Path
import sys,json,hashlib
import pandas as pd,numpy as np
R=Path(__file__).resolve().parents[1]; H=R/'research/sector_stock_momentum';sys.path.insert(0,str(H))
import backtest as bt,ml2_run as m
bt.SEG_D=bt.SEG_M=None
idx=pd.bdate_range('2020-01-31','2020-03-03');t=pd.Timestamp('2020-01-31')
d=pd.DataFrame({'SPY':100.,'A':np.nan},index=idx);d.loc[t,'A']=100;d.loc['2020-02-03','A']=105
P=d.resample('ME').last();P.loc[t,'A']=100
res={(t,'A'):.10};p=bt.Prices(d,P,1)
assert np.isclose(p.ret(t,'A',res)[0],110/105-1)
assert bt.Prices(d,P,0).ret(t,'A',res)==(.10,'resolved_manual')
O=d.copy();O.loc['2020-02-03','A']=110
assert np.isclose(m.OpenPrices(d,P,O).ret(t,'A',res)[0],0)
d.loc['2020-02-03','A']=110
d.loc['2020-02-14','A']=121
P0=P.copy();P0.loc[pd.Timestamp('2020-02-29'),'A']=np.nan
O.loc['2020-02-03','A']=90
assert np.isclose(m.OpenPrices(d,P0,O).ret(t,'A',{})[0],121/90-1)
d.loc['2020-02-14','A']=np.nan
d.loc['2020-02-03','A']=np.nan
assert bt.Prices(d,P,1).ret(t,'A',res)==(0.,'unresolved')
assert pd.isna(bt.Prices(d,P,1).E.at[t,'A'])
X=pd.DataFrame({'ret_oo':[.1,0.,0.,np.nan], 'status_oo':['ok','unresolved','source_gap','ok']})
assert m.known_training_label(X).tolist()==[True,False,False,False]
try:m.model_fit_predict('ridge',{'alpha':1},X,X,[])
except ValueError as e:assert 'unknown terminal' in str(e)
else:raise AssertionError('unknown labels accepted')
# Unknown validation/test rows must remain selectable; only training masks change.
rows=[]
for t0 in pd.date_range('2011-01-31','2015-12-31',freq='ME'):
 for sym,st in [('A','ok'),('B','unresolved')]:rows.append({'t':t0,'ticker':sym,'mom_rank':1,'ret_oo':.1 if sym=='A' else 0.,'status_oo':st})
D=pd.DataFrame(rows);seen=[]
def fakefit(kind,params,tr,te,cols):
 assert m.known_training_label(tr).all()
 seen.append(set(te.ticker));return np.ones(len(te))
original=(m.model_fit_predict,m.net_cagr,m.TEST_YEARS,m.GRID)
m.model_fit_predict=fakefit;m.net_cagr=lambda S,W:.1;m.TEST_YEARS=[2015];m.GRID={'ridge':[{'alpha':1}]}
class PX:sess=pd.bdate_range('2010-01-01','2017-01-01')
try:
 out,_=m.walk_forward(D,{'px':PX()},'ridge',[],1)
 assert all(v=={'A','B'} for v in seen)
 assert out[(out.holding_year==2015)&(out.ticker=='B')].score.notna().all()
finally:m.model_fit_predict,m.net_cagr,m.TEST_YEARS,m.GRID=original
checks=['manual close return rebased to actual delayed entry','formation-close unchanged','manual open return rebased to actual entry','last trade terminal value rebased to actual open','no entry quote stays unresolved','no stale execution quote','unknown labels excluded','fit rejects unknown labels','validation candidates preserve unknown outcomes','test candidates preserve unknown outcomes']
j={'status':'PASS','checks':checks,'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [H/'backtest.py',H/'ml2_run.py']}}
(R/'audit_v2/root_execution_gate.json').write_text(json.dumps(j,indent=2));print('PASS',checks)
