from pathlib import Path
import json,hashlib,math,collections,re
import numpy as np,pandas as pd
W=Path(__file__).resolve().parent;OUT=W.parent;ROOT=W.parents[2]
R=ROOT/'backtest_versions/2026-10-30_codex_full_audit_v2';H=R/'research/sector_stock_momentum'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def safe(n):return ''.join(c if c.isalnum() else '_' for c in n)
old=read(ROOT/'outputs/backtest_strategy_table_20261030/work/data.json');oldsrc={s['id']:s['path'] for s in old['sources']}
indices=['root_stock_strategy_index.json','legacy_ml_strategy_index.json','factors_strategy_index.json','rotation_macro_strategy_index.json']
records=[]
for f in indices:
 for x in read(R/'audit_v2'/f):records.append({**x,'index_file':'audit_v2/'+f})
# Writer pending states are superseded only by executed independent reviews.
review_for={'factors_strategy_index.json':'root_factors_review.json','legacy_ml_strategy_index.json':'legacy_cross_review.json','rotation_macro_strategy_index.json':'rotation_cross_review.json'}
for x in records:
 f=Path(x['index_file']).name
 if f in review_for:
  review=read(R/'audit_v2'/review_for[f]);assert 'PASS' in review['status'],review_for[f]
  for key in ['audit_status','status','run_status']:
   v=str(x.get(key,''))
   if 'PENDING_INDEPENDENT_REVIEW' in v or 'AWAITING_PARENT_REVIEW' in v or 'pending independent review' in v:
    x['author_'+key]=v;x[key]='REVIEWED_WITH_SOURCE_LIMITS'
# Match original catalog by exact names and source, never by return similarity.
matched={};used=set();mapping=[]
family={'机器学习第一版':'legacy_ml','爆发股 V1':'explosive_v1','爆发股 V2':'explosive_v2','爆发股 V3':'explosive_v3','财报反应 EAR':'earnings_reaction_extension','EPS与动量':'eps_momentum','三因子组合':'composite3','动量+ROE':'mom30_roe','200日均线风控':'sma200_overlay','科技股策略':'tech_only','标普与纳指股票池扩展':'ndx_expand','因子组合':'factor_combo'}
for n,row in enumerate(old['inventory'],1):
 fam,display,name,_,_,_,_,_,_,sid,_=row;src=oldsrc[sid]
 matches=[i for i,x in enumerate(records) if x.get('legacy_source_path',x.get('legacy_source'))==src and x.get('legacy_name')==name]
 if not matches:matches=[i for i,x in enumerate(records) if x['name']==name and x.get('family')==family.get(fam)]
 if not matches:matches=[i for i,x in enumerate(records) if x.get('summary_path')==src and x['name']==name]
 if not matches and fam=='因子组合（额外保存账本）':matches=[i for i,x in enumerate(records) if x.get('ledger_path')==src]
 if not matches and fam=='因子组合（额外保存账本）':
  records.append({'family':fam,'name':name,'status':'AUDITED_NOT_SELECTED_BY_CORRECTED_FROZEN_SEARCH','frequency':'monthly','ledger_path':None,'limitations':['旧交互搜索账本已被修正后的既定搜索结果替代；不沿用旧成绩。'],'index_file':'audit_v2/factors_report.json','legacy_source':src,'legacy_name':name});matches=[len(records)-1]
 if len(matches)!=1:raise AssertionError(('catalog mapping must be unique',n,fam,name,src,matches))
 i=matches[0];used.add(i);matched[n]=i
 mapping.append({'id':f'O{n:03d}','family':fam,'display_name':display,'original_name':name,'legacy_source':src,'record_index':i})
checks=[];monthlies=[];sources={};ledger_cache={}
def source(path):
 if path and path not in sources:
  p=R/path
  sources[path]={'path':path,'sha256':sha(p) if p.is_file() else None}
 return path

def stats(s):
 a=np.array(s,float)
 if not len(a) or not np.isfinite(a).all() or (a < -1-1e-12).any():raise AssertionError(('invalid return series',len(a)))
 w=np.cumprod(1+a);peak=np.maximum.accumulate(np.r_[1.,w])[1:]
 dd=np.divide(w,peak,out=np.ones_like(w),where=peak!=0)-1
 return {'cagr':float(w[-1]**(12/len(a))-1),'dd':float(dd.min()),'total':float(w[-1]-1),'n':len(a)}

def load_ledger(x):
 path=x.get('ledger_path')
 if not path:return None
 if path in ledger_cache:return ledger_cache[path]
 p=R/path;assert p.is_file(),path
 d=pd.read_csv(p);source(path)
 if 'equity' in d:
  dates=pd.to_datetime(d['date']);eq=d.equity.to_numpy(float);assert np.isfinite(eq).all() and (eq>=0).all()
  peak=np.maximum.accumulate(np.r_[1.,eq])[1:];dd=float((np.divide(eq,peak,out=np.ones_like(eq),where=peak!=0)-1).min())
  years=(dates.iloc[-1]-dates.iloc[0]).days/365.25
  out={'kind':'daily','data':d,'cagr':float(eq[-1]**(1/years)-1),'dd':dd,'n':len(d),'first':str(dates.iloc[0].date()),'last':str(dates.iloc[-1].date())}
 else:
  datecol=x.get('date_column') or ('month' if 'month' in d else 'date' if 'date' in d else d.columns[0]);dates=pd.to_datetime(d[datecol]);rotation='sector_rotation/' in path
  if rotation:dates=dates+pd.offsets.MonthEnd(1)
  col=next((c for c in [x.get('return_column'),'net','top_ret','top3','ret'] if c and c in d),None)
  if col is None:raise AssertionError(('unknown ledger return',path,d.columns.tolist()))
  s=pd.Series(pd.to_numeric(d[col]).values,index=pd.DatetimeIndex(dates),name='return')
  continuous=s.index.equals(pd.date_range(s.index.min(),s.index.max(),freq='ME')) and not s.index.has_duplicates
  diagnostic= 'diagnostic' in x.get('evidence_role','') and x.get('evidence_role')!='portfolio_parameter_diagnostic'
  if not rotation:assert continuous,(path,'missing or duplicate months')
  valid_cagr=continuous and not diagnostic
  out={'kind':'rotation' if rotation else 'monthly','data':d,'s':s,'first':str(s.index[0].date()),'last':str(s.index[-1].date()),'n':len(s),'valid_cagr':valid_cagr}
  if valid_cagr:out.update(stats(s))
  if 'capital_after_costs' in d and 'gross' in d and 'net' in d:
   diff=np.abs(d.net-((d.capital_after_costs*(1+d.gross)).clip(lower=0)-1))
   if 'bankrupt' in d:
    # Absorbed zero capital emits zero subsequent returns by convention.
    diff=diff.where(~((d.capital_after_costs==0)&(d.net==0)),0)
   assert diff.max()<1e-9,(path,'cost reconciliation',diff.max())
   checks.append({'path':path,'check':'self financing net = invested capital x gross growth - 1','max_error':float(diff.max())})
  if valid_cagr:checks.append({'path':path,'check':'finite returns, >= -100%, continuous unique holding months','months':len(s)})
 ledger_cache[path]=out;return out

def status(x,l):
 s=str(x.get('status',x.get('audit_status',x.get('run_status',''))))
 if 'BLOCK' in s or 'blocked' in s or 'MISSING' in s or 'PENDING' in s:return '已审核：阻塞／不能采用'
 if 'NOT_SELECTED' in s or 'SUPERSEDED' in s or 'superseded' in x.get('evidence_role',''):return '已审核：旧结果退役'
 if 'holdout' in x.get('family','').lower() or '非标普' in x.get('family',''):return '已重跑：股票池／价格缺口，不能认证'
 if l and l['kind']=='daily':return '已重跑：既有参数的历史重放'
 if l and l.get('valid_cagr',True):return '已重跑并核算；历史数据未完全认证'
 return '已审核：信号／条件统计，不是组合收益'

def frequency(x):
 s=x.get('frequency','')
 if 'event' in s:return '事件触发'
 if 'buy' in s.lower():return '买入持有；按月观察'
 if '6' in s or 'six' in s or 'tranche' in s or 'hold6m' in x.get('name',''):return '每月开新仓；分批持有6个月'
 if 'monthly' in s:return '每月检查／调仓'
 return s or '不适用'

allrows=[];same=[];long=[];extra=[];native=[];period_metrics={}
for i,x in enumerate(records):
 x['audit_id']=f'A{i+1:03d}';l=load_ledger(x);x['final_status']=status(x,l)
 source(x.get('summary_path'));source(x.get('index_file'))
 limitations='；'.join(x.get('limitations',[]));reason=x.get('reason','')
 vals=[x['audit_id'],x['family'],x['name'],x['final_status'],frequency(x),l['first'] if l else None,l['last'] if l else None,l.get('n') if l else None,l.get('cagr') if l else None,l.get('dd') if l else None,'日度' if l and l['kind']=='daily' else '持有期末／月末',x.get('cost',''),x.get('execution',''),x.get('ledger_path'),reason+' '+limitations]
 native.append(vals)
 if i not in used:extra.append(vals)
 if l and l['kind']=='monthly':
  for start,end,name in [('2023-01-31','2026-09-30','same'),('2015-01-31','2026-09-30','long')]:
   valid_start=x.get('valid_comparison_start')
   if valid_start and pd.Timestamp(start)<pd.Timestamp(valid_start):continue
   # Fixed factor sets were selected through 2022, including NDX extensions.
   if name=='long' and ('fixed-factor' in x.get('evidence_role','') or (x['family']=='ndx_expand' and x['name'].startswith('C '))):continue
   if (1+l['s'].loc[l['s'].index < pd.Timestamp(start)]).prod()<=0:continue # zero capital cannot restart at comparison boundary
   expected=pd.date_range(start,end,freq='ME');s=l['s'].reindex(expected)
   if s.isna().any():continue
   m=stats(s);period_metrics[(i,name)]=m
   blocked='不能' in x['final_status'] or '退役' in x['final_status']
   group='数据有缺口：仅诊断' if blocked else '次日开盘／收盘回退' if x['family'] in ['root_ml2','ml2','机器学习第二版 ML2'] else '次日收盘' if 'next-day' in x['name'] else '月末收盘'
   if 'gross' in x.get('cost','').lower():group+='／毛收益基准'
   row=[x['audit_id'],x['family'],x['name'],m['cagr'],m['dd'],m['total'],m['n'],group,frequency(x),x.get('cost',''),x.get('execution',''),x['final_status'],x.get('ledger_path')]
   row.extend([stats(s.loc[:'2025-12-31'])['cagr'],float((1+s.loc['2026-01-31':]).prod()-1)])
   (same if name=='same' else long).append(row)
   if name=='same':monthlies.extend([[x['audit_id'],str(t.date()),float(v),group] for t,v in s.items()])
for a in [same,long]:a.sort(key=lambda r:(r[7],-r[3]))
for m in mapping:
 x=records[m['record_index']];l=load_ledger(x);c=period_metrics.get((m['record_index'],'same'),{})
 allrows.append([m['id'],m['family'],m['display_name'],m['original_name'],x['final_status'],frequency(x),c.get('cagr'),c.get('dd'),l.get('first') if l else None,l.get('last') if l else None,l.get('cagr') if l else None,l.get('dd') if l else None,x['audit_id'],x.get('ledger_path'),x.get('reason','')+'；'+'；'.join(x.get('limitations',[]))])
assert len(allrows)==340
# All 96 frozen main parameter configurations, with their real ledgers.
grid=[]
for row in pd.read_csv(H/'results/grid_is_oos.csv').to_dict('records'):
 path='research/sector_stock_momentum/results/'+row['monthly_ledger'];l=load_ledger({'ledger_path':path});m=stats(l['s'].loc['2023-01-31':'2026-09-30']);assert m['n']==45
 grid.append([int(row['look']),int(row['n_sec']),int(row['n_stk']),row['score'],int(row['distinct_id']),m['cagr'],m['dd'],row['SEL_CAGR'],row['OOS_CAGR'],row['OOS_maxDD'],path])
assert len(grid)==96
# Signal research keeps its own units; no invented portfolio CAGR.
signals=[]
def sig(fam,name,verdict,metric,value,n,p,note,path):signals.append([fam,name,verdict,metric,value,n,p,note,source(path)])
macro=read(R/'audit/macro_replay.json')
for fam,group in macro['commonSampleComparisons'].items():
 for name,v in group.items():sig('宏观预警 / '+fam,name,'修订历史重放；非实时验证','命中事件数',len(v['hits']),v['coverage']['knownMonths'],None,f"漏报{len(v['misses'])}；误报段{len(v['falseAlarms'])}；不可用事件{len(v['unavailableEvents'])}",'audit/macro_replay.json')
for row in pd.read_csv(R/'research/hawkish_path/hawkish_path_v2_results.csv').to_dict('records'):
 sig('鹰派路径',row['Ticker']+' / '+row['Regime'],'已重跑；条件研究','不适用CAGR',None,None,None,'重叠未来收益区间，非可直接复利组合','research/hawkish_path/hawkish_path_v2_results.csv')
p='test/phase3_validation/output/07_verdict.json'
for n,v in read(R/p).items():sig('资金流Phase3',n,'未获支持','NOT_SUPPORTED',None,None,None,'预设预测检验未通过',p)
p='test/phase4_composite_validation/output/05_composite_verdict.json';v=read(R/p);sig('资金流Phase4',v['signal'],'未获支持','NOT_SUPPORTED',None,None,None,'主要5日预测检验未通过',p)
p='test/phase5_exploratory/output/phase5_ic_results.json'
for n,v in read(R/p).items():sig('资金流Phase5',n,'未证明稳定预测力','排名相关IC',v['spearman_rho'],v['N'],v['hac_p'],'探索结果',p)
p='test/phase5_exploratory/output/phase5B_pension_diagnostic.json';v=read(R/p)
for n,val in v['baseline_tests'].items():sig('资金流Phase5B',n,'探索结果','排名相关IC',val,v['pension_details']['N'],v['pension_details']['hac_p'] if n=='A_Pension_Alone' else None,'仅信号活跃日诊断',p)
for k in ['vc','rp']:
 p=f'test/phase6_construct_audit/{k}_benchmark_validation_results.json';v=read(R/p);sig('机制对照Phase6',v['model'],v['verdict'],'日收益相关',v['dailyPearsonCorrelation'],v['observations'],None,'机制相似不等于预测盈利',p)
p='research/sector_stock_momentum/results/factor_screen/screen_table.csv'
for row in pd.read_csv(R/p).to_dict('records'):
 sig('单因子 / '+row['group'],row['factor'],str(row.get('verdict',row.get('status','见原始表'))),'平均排名相关IC',row.get('IC_mean'),row.get('months'),row.get('RW_p'), '47项多重检验；没有一项达到原规则有用标准',p)
assert len(signals)==len(old['signals']),(len(signals),len(old['signals']))
# Separate cohorts: exact T+2 shared windows; SEP event-driven wealth curves.
rotation=[r for r in native if r[1]=='行业轮动现行模型共同期间'];rotation.sort(key=lambda r:-r[8])
sep=[r for r in native if r[1]=='纯SEP既有参数检验'];sep.sort(key=lambda r:-r[8])
notes=[['审计结论','全目录逐项处置；代码修复与运行完成不等于全部策略合格，更不等于所有原始历史资料认证。'],['版本','Codex audited and modified — full audit v2。旧版只保留历史标签 Claude audited（用户指定归属，不是本次替Claude背书）。'],['比较期间','股票主表统一2023-01至2026-09，45个月；长表2015-01至2026-09，141个月。不同成交时点、毛净收益分别标明。'],['是否全月调仓','不是。多数股票策略每月检查/换仓；T1分批持有6个月；SEP按事件交易；ETF基准为买入持有；信号研究没有组合调仓。'],['最大回撤','股票主表是月末/持有期末观察，可能漏掉月中更大损失。SEP单列真实日度回撤。无法核对日度路径的不编造。'],['频繁筛选','同一历史反复用于研究；最高回报不证明最可靠，也不是新的盲测。96格仅旧参数搜索，不新增策略。'],['非标普池','有价格不等于有完整历史股票池；2018后幸存者偏差、拆股/身份缺口尚在。成绩列为诊断，不能获封最佳。'],['无法重跑','QQQ EPS指数来源不符；旧RF含classifier但原实现缺失；某些波动率目标缺真实日度路径。已审核阻塞，不沿用旧收益。'],['RF早停','原前5项接受门全部失败，剩2项即使通过也不足6/7。500次placebo真实中止；没有宣称完成或制造p值。'],['公式口径','月度CAGR=累计财富^(12/月数)-1；回撤以初始本金1纳入历史高点；净收益用账本真实费用和现金处理。'],['证据','每条账本在来源表有SHA256；所有结果来自v2当前运行索引，不以文件存在当作已重跑。'],['工作流','冻结输入 → 全入口审核 → 修复与反例 → 真实重跑和核算 → 同期比较 → 保留数据不足项。']]
counts={'old_catalog':len(allrows),'supplementary':len(extra),'all_records':len(records),'same45':len(same),'long141':len(long),'grid':len(grid),'signals':len(signals),'unique_ledgers':len(ledger_cache),'ledger_checks':len(checks),'status':dict(collections.Counter(x['final_status'] for x in records))}
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(float,np.floating)):return float(x) if math.isfinite(x) else None
 return x

concentration=[]
cp='audit_v2/ml2_concentration_summary.csv'
for q in pd.read_csv(R/cp).to_dict('records'):
 concentration.append([q['strategy'],q['base_cagr'],q['largest_contributor'],q['largest_stock_share_of_net_profit'],q['without_largest_stock_cagr'],q['best_year'],q['without_best_year_sample_geometric_rate'],q['base_monthly_mdd']])
source(cp);source('audit_v2/ml2_concentration_checks.json');source('audit_v2/peak_price_source_check.json')
pools=[['标普500历史池',484,505,498,'够研究标普大盘股','870个历史代码；659个股票×月份有价格/身份硬缺口，涉及33个代码；完整历史尚未认证。'],['纳指100历史池',95,104,101,'补充仍偏大盘股','加进标普后每月多13—35只，中位21只；内部名单一致不等于每次历史变更都获官方证明。'],['非标普实际可选池',880,1734,1279,'不能代表完整美股市场','共6183条可用价格；未限定真实市值；2018后缺失退市股、幸存者偏差、拆股/身份问题。STRICT也只是事后诊断。']]
fixes=[
 ['资金费用','费用在买入前支付；按真实换手计费；现金月份不丢；本金归零后不能复活。','root_ledger_gate.json / legacy_ml_gate.json'],
 ['财务时序','用各字段真正公开日；晚报旧季度不覆盖新季度；新季度缺值不沿用旧值。','root_feature_gate.json / factors_gate.json'],
 ['现金流因子','把年度CFO/NI改回原规范TTM口径；迟到组成项在真实公开前仍不可用。','root_cfo_truncation.json'],
 ['机器学习标签','未知退出收益不当训练真值；测试候选仍保留；标签在调参决策前必须已发生。','root_execution_gate.json / root_scope_counterexamples.json'],
 ['次日成交','不使用陈旧收盘价假装买入；退出对价和最后成交价按实际开盘/收盘成本重新计算。','root_scope_counterexamples.json'],
 ['收益统计','Deflated Sharpe使用同期无风险利率后的超额收益；所有12模型和5对照均列出。','root_ml2_final_stat_review.json'],
 ['日度风险','不把缺价填平、不把月底差额摊进每天；无法重建的日风险标不可得。','root_daily_gap_gate.json / legacy_cross_review.json'],
 ['非标普价格','取消没有拆股证据的自动价格缩放；异常价格保留标记，不能伪装修好了。','root_scope_review.json'],
 ['行业轮动','按形成日先选；选中资产未来缺价不能偷偷换第二名；使用真实T+2交易日。','rotation_cross_review.json'],
 ['共同窗口','行业模型40月与原44月基准分开；当前比较统一到40个实际持有区间。','rotation_cross_review.json'],
 ['SEP解析','早期区间上下限不能当预测年份；旋转PDF列位修正；可靠中位数从2015起。','rotation_macro_disposition.json'],
 ['停用旧结果','旧RF缺原实现、QQQ EPS指数来源不对、日线依赖不成立，明确阻塞；不借旧收益充数。','catalog_coverage.json'],
 ['集中度','17条ML2原账本2397个月重新核对；补最大贡献股/月份、留现金与剔除最好年诊断。','ml2_concentration_checks.json'],
 ['异常高收益抽查','MU/SNDK/SPY的2026年3—5月共9个原始月末收盘，与独立SIP来源一致；仅有限抽查。','peak_price_source_check.json']]
for row in fixes:row[2]='audit_v2/'+row[2]
labels={m['record_index']:m['display_name'] for m in mapping}
family_labels={m['record_index']:m['family'] for m in mapping}
for rows in [same,long,native,extra]:
 for row in rows:
  i=int(row[0][1:])-1
  row[1]=family_labels.get(i,row[1])
headline=[]
for fam,name,label,judgment in [
 ('tech_only','tech: three-factor score top-1','科技股三因子，只买1只','本次同收盘历史最高；高度集中，未获前瞻验证'),
 ('sma200_overlay','pure momentum top-1 + SMA200','纯动量1只＋200日均线','规则较简单，但单股集中；回撤仍很大'),
 ('root_main','NO SECTOR FILTER: top-1 stock','纯动量，只买1只','历史收益高，不代表最可信'),
 ('root_main','SPEC','最强行业里买最强1只','截至2025年化仅约6.4%；2026影响很大'),
 ('root_main','Ref: top-10, no sector filter','纯动量，分散买10只','集中风险较低；仍是历史回放'),
 ('root_main','Bench: SPY','标普500 ETF（SPY）','最简单、最容易核验的比较基准'),
 ('root_ml2','C-lgbm Top1','ML2：价格＋财务历史，买1只','次日成交；长期模型冠军，但贡献集中'),
 ('root_ml2','BENCH momentum Top1','ML2同口径纯动量1只','同期开盘口径胜过上述ML模型')]:
 i=next(i for i,x in enumerate(records) if x['family']==fam and x['name']==name);row=next(r for r in same if r[0]==records[i]['audit_id'])
 headline.append([label,row[3],row[4],row[13],row[14],row[7],judgment])

out=clean({'counts':counts,'same':same,'long':long,'inventory':allrows,'native':native,'extra':extra,'grid':grid,'signals':signals,'rotation':rotation,'sep':sep,'monthly45':monthlies,'notes':notes,'sources':list(sources.values()),'checks':checks,'mapping':mapping,'records':records,'concentration':concentration,'pools':pools,'fixes':fixes,'headline':headline})
(W/'data.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False))
(R/'audit_v2/catalog_coverage.json').write_text(json.dumps(clean({'counts':counts,'mapping':mapping}),ensure_ascii=False,indent=2))
(R/'audit_v2/all_ledger_verification.json').write_text(json.dumps(clean({'checks':checks,'status':'PASS','unique_ledgers':len(ledger_cache)}),indent=2))
print(json.dumps(counts,ensure_ascii=False,indent=2))
for rows in [same,rotation,sep]:
 print('PREVIEW',sorted(rows,key=lambda r:-(r[3] if rows is same else r[8]))[:5])
