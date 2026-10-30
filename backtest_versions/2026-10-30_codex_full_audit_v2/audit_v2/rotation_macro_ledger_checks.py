"""Independent repricing of saved holdings/wealth; no backtest imports."""
import hashlib,json,pathlib
import numpy as np
import pandas as pd
ROOT=pathlib.Path(__file__).resolve().parents[1]
records=[]
def savecheck(name,error,count):
    assert error<1e-10,(name,error)
    records.append({'name':name,'max_abs_error':float(error),'rows':int(count),'passed':True})
prices={p.stem:pd.read_csv(p,index_col='date')['adj_close'] for p in (ROOT/'research/sector_rotation/adj_prices').glob('*.csv')}
for p in (ROOT/'research/sector_rotation/results_v2').glob('**/*_monthly.csv'):
    d=pd.read_csv(p);expected=[]
    for row in d.to_dict('records'):
        if 'picks' in row:
            picks=row['picks'].split(',')
            ret=0 if picks==['CASH'] else np.mean([prices[t].loc[row['exit_date']]/prices[t].loc[row['entry_date']]-1 for t in picks])
        else:
            ticker=p.stem.split('_')[0]
            ret=prices[ticker].loc[row['exit_date']]/prices[ticker].loc[row['entry_date']]-1
        expected.append(ret)
    savecheck(str(p.relative_to(ROOT)),np.max(np.abs(d['top_ret']-expected)),len(d))

rfdir=ROOT/'research/sector_rotation/results_v2'
windows=[]
for row in pd.read_csv(rfdir/'model_common_period_summary.csv').to_dict('records'):
    d=pd.read_csv(rfdir/'common_monthly'/(row['label'].replace(' ','_')+'_monthly.csv'))
    wealth=(1+d['top_ret']).cumprod()
    savecheck('common summary '+row['label']+':CAGR',abs(wealth.iloc[-1]**(12/len(d))-1-row['cagr']),len(d))
    savecheck('common summary '+row['label']+':MDD',abs((wealth/wealth.cummax().clip(lower=1)-1).min()-row['mdd']),len(d))
    assert len(d)==row['months']==40
    assert pd.Timestamp(row['first_entry'])==pd.Timestamp(d['entry_date'].iloc[0])
    assert pd.Timestamp(row['last_exit'])==pd.Timestamp(d['exit_date'].iloc[-1])
    windows.append(d[['date','entry_date','exit_date']].to_csv(index=False))
assert len(set(windows))==1,'Common summary windows differ'

for p in (ROOT/'research/sector_rotation').glob('detail_*_h*.csv'):
    d=pd.read_csv(p)
    if not {'entry_date','exit_date'}.issubset(d.columns):continue
    for col,pickcol in [('top3','top_names'),('bot3','bot_names')]:
        expected=[np.mean([prices[t].loc[row['exit_date']]/prices[t].loc[row['entry_date']]-1 for t in row[pickcol].split(',')]) for row in d.to_dict('records')]
        savecheck(str(p.relative_to(ROOT))+':'+col,np.max(np.abs(d[col]-expected)),len(d))

static=ROOT/'research/strategy_comparison/static_data'
def pairs(p):
    obj=json.loads(p.read_text());return obj.get('values',obj) if isinstance(obj,dict) else obj
qqq=pd.Series({pd.Timestamp(d):float(v) for d,v in pairs(static/'QQQ.json')}).sort_index()
dff=pd.Series({pd.Timestamp(d)+pd.Timedelta(days=1):float(v)/100 for d,v in pairs(static/'DFF.json')}).sort_index()
sep=json.loads((ROOT/'research/strategy_comparison/sep_parser_audit_v2.json').read_text())
summary=pd.read_csv(ROOT/'research/strategy_comparison/results_v2/sep_summary.csv')
for config in summary.to_dict('records'):
    pce,rate=config['pce'],config['rate'];p=ROOT/f'research/strategy_comparison/results_v2/sep_pce{pce}_rate{rate}_daily.csv';d=pd.read_csv(p,parse_dates=['date'])
    exits=set();enters=set();state=True
    for current,prior in zip(sep[1:],sep[:-1]):
        year=str(current['target_year'])
        cp=current['pce_by_year'].get(year);cr=current['rate_by_year'].get(year)
        pp=prior['pce_by_year'].get(year);pr=prior['rate_by_year'].get(year)
        if any(v is None for v in [cp,cr,pp,pr]):continue
        event=None
        if state and cr-pr>rate and cp>pce and cp>pp:state=False;event=exits
        elif not state and cr<=pr:state=True;event=enters
        if event is not None:
            candidates=qqq.index[qqq.index>pd.Timestamp(current['date'])]
            if len(candidates):event.add(candidates[0])
    wealth=.999;state=True;expected=[]
    for i,date in enumerate(d['date']):
        if i:
            prev=d['date'].iloc[i-1]
            if state:wealth*=qqq.loc[date]/qqq.loc[prev]
            else:wealth*=1+dff.loc[:date].iloc[-1]*(date-prev).days/365
        if state and date in exits:state=False;wealth*=.999
        elif not state and date in enters:state=True;wealth*=.999
        expected.append(wealth)
    savecheck(str(p.relative_to(ROOT)),np.max(np.abs(d['equity']-expected)),len(d))
    cagr=wealth**(252/(len(d)-1))-1
    savecheck(p.name+':CAGR',abs(cagr-config['cagr']),len(d))

result={'status':'PASS','checked_ledgers_and_metrics':len(records),'checks':records}
(ROOT/'audit_v2/rotation_macro_ledger_checks.json').write_text(json.dumps(result,indent=2))
print(result['status'],len(records))
