import ast, importlib.util, json, pathlib, sys
import numpy as np
import pandas as pd

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'research/sector_rotation'))
import engine
passed=[]
def check(name, condition):
    assert condition, name
    passed.append(name)

z=engine._cross_section_z(pd.Series([np.nan,np.nan]))
check('all missing features stay missing',z.isna().all())
z=engine._cross_section_z(pd.Series([1.0,np.nan]))
check('one observed feature never repairs missing peers',z.iloc[0]==0 and np.isnan(z.iloc[1]))
for series in [[.1,np.nan,.2,.3], [.1,-1.1,.2,.3]]:
    try:engine.calc_metrics(series)
    except ValueError:passed.append('invalid ledger rejected '+str(series))
    else:raise AssertionError(series)
m=engine.calc_metrics([-.3,0,0,0]);check('initial capital participates in drawdown',abs(m['mdd']+.3)<1e-12)
try:engine.load_prices(force_refresh=True)
except RuntimeError:passed.append('network refresh prohibited')
else:raise AssertionError('refresh')

spec=importlib.util.spec_from_file_location('isolated_strategy_engine',ROOT/'research/strategy_comparison/strategy_engine.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
idx=pd.bdate_range('2020-01-01',periods=5)
zero=pd.Series(0.,index=idx);ones=pd.Series(1,index=idx)
ret=pd.Series([0,-.5,1.,1.,1.],index=idx)
r=module.run_backtest(idx,ret,zero,ret,zero,zero,zero,ones,use_overlay=False,use_sep=False)
check('bankruptcy does not resurrect',r['equity'].iloc[1:].eq(0).all())
check('initial leverage purchase costs charged',abs(r['equity'].iloc[0]-(1-3*.0025))<1e-12)
check('total loss drawdown reaches 100%',r['mdd']==-1)
try:module.run_backtest(idx,ret,zero,ret,zero,zero,zero,ones.shift(1,freq='B'),use_overlay=False)
except ValueError:passed.append('mismatched signal dates rejected')
else:raise AssertionError('misaligned signal')
raw=module.parse_sep_pdfs(str(ROOT/'data/fomc_sep'))
bydate={x['date']:x for x in raw}
check('2012 published ranges never become medians',bydate['2012-01-25']['source']=='unavailable_median')
check('rotated 2016 PDF median columns match source',bydate['2016-03-16']['pce_by_year']=={2016:1.6,2017:1.8,2018:2.0})
check('2018 PDF federal funds columns match source',bydate['2018-12-19']['rate_by_year']=={2018:2.4,2019:2.9,2020:3.1,2021:3.1})
check('modern compressed PDF text parses',bydate['2019-03-20']['pce_by_year']=={2019:2.0,2020:2.0,2021:2.0})
check('conditional calendar gaps return undefined CAGR',np.isnan(engine.contiguous_cagr([.1,.1],['2020-01','2020-03'])))
sys.path.insert(0,str(ROOT/'research/hawkish_path'))
from audit_calendar import align_equity_calendar
prices=pd.DataFrame({'date':pd.bdate_range('2020-01-01',periods=5),'close':[100,110,120,130,140]})
signals=pd.DataFrame({'date':prices['date'].iloc[[0,2,3]],'signal':[1,2,3]})
aligned=align_equity_calendar(signals,prices)
check('macro holiday never removes an equity session',len(aligned)==len(prices) and aligned.iloc[1]['signal']==1)
check('no signals invented beyond source coverage',np.isnan(aligned.iloc[-1]['signal']))

# Loading function definitions only avoids executing any historical model.
p=ROOT/'research/sector_rotation/run_backtest.py';tree=ast.parse(p.read_text())
needed={'backtest','_nw_t'}
code=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in needed],type_ignores=[])
from scipy import stats
scope={'pd':pd,'np':np,'stats':stats,'SECTOR_TICKERS':list('ABCDEF'),'TOP_N':3,'DEFAULT_START':'2020-01','DEFAULT_END':'2020-12'}
exec(compile(code,str(p),'exec'),scope)
dates=pd.date_range('2019-12-31','2020-07-31',freq='ME');bd=pd.bdate_range('2019-12-01','2020-12-31')
prices={t:pd.DataFrame({'close':np.linspace(100,150,len(bd))},index=bd) for t in 'ABCDEF'}
sig=pd.DataFrame([{'date':d,'ticker':t,'score':i,'close':100} for d in dates for i,t in enumerate('ABCDEF')])
reg=pd.DataFrame({'date':dates,'rising':[0,1]*4})
r=scope['backtest'](sig,'score',reg,holding=3,daily_prices=prices)
check('overlapping 3m labels are not compounded',np.isnan(r['top3_cagr']))
r=scope['backtest'](sig,'score',reg,regime_filter='rising',daily_prices=prices)
check('conditional months not compressed into CAGR',np.isnan(r['top3_cagr']))
r=scope['backtest'](sig,'score',reg,end='2020-06',daily_prices=prices)
check('end month is inclusive',r['df']['date'].max()==pd.Timestamp('2020-06-30'))
check('execution uses later prices not signal close',r['df']['top3'].gt(0).all())
scope['SECTOR_TICKERS']=list('ABCDEFG')
dt=pd.Timestamp('2020-01-31');cal=pd.to_datetime(['2020-01-31','2020-02-03','2020-02-04','2020-03-02','2020-03-03'])
px={t:pd.DataFrame({'close':[100,101,102,103,104]},index=cal) for t in 'ABCDEFG'}
ss=pd.DataFrame({'date':[dt]*7,'ticker':list('ABCDEFG'),'score':range(7)})
rr=pd.DataFrame({'date':[dt],'rising':[0]})
full=scope['backtest'](ss,'score',rr,daily_prices=px)
check('formation picks fixed before future pricing',full['df']['top_names'].iloc[0]=='G,F,E')
px['G']=px['G'].iloc[:3]
try:scope['backtest'](ss,'score',rr,daily_prices=px)
except ValueError as e:check('selected future missing price never causes replacement','Selected holdings cannot be priced' in str(e))
else:raise AssertionError('Future missing G silently replaced')
result={'status':'PASS','checks':passed}
(ROOT/'audit_v2/rotation_macro_checks.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
