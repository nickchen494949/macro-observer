from pathlib import Path
import json,pandas as pd
R=Path(__file__).resolve().parents[1];j=json.loads((R/'audit_v2/peak_price_alpaca_response.json').read_text());bars=j['result']['structuredContent']['bars'];rows=[]
for s,bb in bars.items():
 q=json.loads((R/f'research/sector_stock_momentum/data/raw/{s}.json').read_text());p=pd.Series(q['close'],index=pd.to_datetime(q['dates'])).resample('ME').last()
 for b in bb:
  t=pd.Timestamp(b['timestamp']).tz_convert('America/New_York').tz_localize(None).normalize()+pd.offsets.MonthEnd(0)
  if t>=pd.Timestamp('2026-06-01'):continue
  v=float(p.loc[t]);err=abs(v-b['close']);rows.append({'ticker':s,'month':str(t.date()),'cached_raw_close':v,'independent_sip_close':b['close'],'absolute_difference':err,'pass_cent_tolerance':err<=.011})
assert all(x['pass_cent_tolerance'] for x in rows)
(R/'audit_v2/peak_price_source_check.json').write_text(json.dumps({'status':'BOUNDED_SPOT_CHECK_PASS','checks':rows,'limitation':'9 month-end raw closes only; adjusted histories, all securities, membership and corporate actions not certified'},indent=2));print('PASS',len(rows),'month-end raw closes; maxdifference',max(x['absolute_difference'] for x in rows))
