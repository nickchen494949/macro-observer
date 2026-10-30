from pathlib import Path
import sys,json
import pandas as pd,numpy as np
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'research/sector_stock_momentum'))
import backtest as bt
from earnings_factor import attach
from ml2_features import cashflow_ttm,_series_asof
from smallcap_data_audit import flags_for
f=pd.to_datetime(['2020-06-30','2020-07-31']);bt.SEG_M=pd.DataFrame({'A':[1.,2.]},index=f)
E=pd.DataFrame({'ticker':['A']*3,'cik':[1]*3,'_ear_segment':[1.]*3,'R':pd.to_datetime(['2018-01-01','2020-05-01','2020-06-01']),'public':pd.to_datetime(['2018-01-02','2020-05-02','2020-06-02']),'ear':[.1,.2,.3]})
X=pd.DataFrame({'t':f,'ticker':['A','A'],'cik':[1,1]});r=attach(X,E)
assert r.ear_sum4.isna().all() and np.isclose(r.ear.iloc[0],.3) and pd.isna(r.ear.iloc[1])
E.loc[0,['R','public']]=pd.to_datetime(['2020-04-01','2020-04-02']);r=attach(X,E);assert np.isclose(r.ear_sum4.iloc[0],.6)
L=pd.DataFrame({'cik':[1]*3,'tag':['NetCashProvidedByUsedInOperatingActivities']*3,'ddate':pd.to_datetime(['2019-06-30','2019-12-31','2020-06-30']),'qtrs':[2,4,2],'uom':['USD']*3,'is_first_report':[True]*3,'filed':pd.to_datetime(['2019-08-01','2020-02-01','2020-08-01']),'value':[40.,100.,60.]})
a=cashflow_ttm(L).set_index('ddate');assert a.loc['2020-06-30','cfo_ttm']==120 and a.loc['2020-06-30','av_cfo_ttm']==pd.Timestamp('2020-08-02')
L.loc[0,'filed']=pd.Timestamp('2020-09-01');a=cashflow_ttm(L);later=a[a.ddate==pd.Timestamp('2020-06-30')];assert later.av_cfo_ttm.tolist()==list(pd.to_datetime(['2020-08-02','2020-09-02'])) and pd.isna(later.cfo_ttm.iloc[0])
known=a[a.av_cfo_ttm<=pd.Timestamp('2020-08-15')];truncated=cashflow_ttm(L[L.filed<=pd.Timestamp('2020-08-15')]);pd.testing.assert_frame_equal(known.reset_index(drop=True),truncated.reset_index(drop=True))
a=cashflow_ttm(L.iloc[1:]).set_index('ddate');assert pd.isna(a.loc['2020-06-30','cfo_ttm']) and a.loc['2020-06-30','av_cfo_ttm']==pd.Timestamp('2020-08-02')
v,d=_series_asof(np.array([2.,np.nan]),np.array(['2020-01-01','2020-04-01'],dtype='datetime64[ns]'),np.array(['2019-12-31','2020-03-31'],dtype='datetime64[ns]'),np.datetime64('2020-05-01'),2);assert np.isnan(v[0])
idx=pd.bdate_range('2020-01-01',periods=15);s=pd.Series([100,150,100]+[101]*12,index=idx);dv=pd.Series(1.,index=idx)
f=flags_for(s,dv);assert f[0][2]==idx[2]
assert any(x[1]=='F3_stale_run' for x in f) and not any(x[1]=='F3_stale_run' for x in flags_for(s,dv*0))
checks=['EAR three-event actual age','EAR identity boundary','EAR valid rolling sum','CFO TTM arithmetic','CFO latest component availability','late component truncation invariance','unknown current TTM invalidates old FY','latest undefined quarter preserved','bad-print reversal boundary','stale active volume required']
(R/'audit_v2/root_feature_gate.json').write_text(json.dumps({'status':'PASS','checks':checks},indent=2));print('PASS',checks)
