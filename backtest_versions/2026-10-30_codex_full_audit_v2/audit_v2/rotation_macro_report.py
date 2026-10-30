"""Build review handoff from actual artifacts, without approving writer work."""
import ast, hashlib, json, pathlib, re
import numpy as np
import pandas as pd

ROOT=pathlib.Path(__file__).resolve().parents[1]
OLD=ROOT.parents[1]/'outputs/backtest_strategy_table_20261030/work/data.json'
old=json.loads(OLD.read_text()); sources={x['id']:x['path'] for x in old['sources']}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def exists(p):return bool(p) and (ROOT/p).exists()
# Reprice only the benchmark on the new, actually rerun Ridge execution dates.
rf_dir=ROOT/'research/sector_rotation/results_v2'
if (rf_dir/'Ridge_Top1_monthly.csv').exists():
    ridge=pd.read_csv(rf_dir/'Ridge_Top1_monthly.csv')
    spy=pd.read_csv(ROOT/'research/sector_rotation/adj_prices/SPY.csv',index_col='date')['adj_close']
    bench=ridge[['date','entry_date','exit_date']].copy()
    bench['top_ret']=[spy.loc[x]/spy.loc[e]-1 for e,x in zip(bench['entry_date'],bench['exit_date'])]
    bench.to_csv(rf_dir/'SPY_Ridge_Top1_aligned_monthly.csv',index=False)
    summaries=[]
    for name,r in [('Ridge Top1',ridge['top_ret']),('SPY aligned Ridge',bench['top_ret'])]:
        wealth=(1+r).cumprod();summaries.append({'name':name,'cagr':wealth.iloc[-1]**(12/len(r))-1,'mdd':(wealth/wealth.cummax().clip(lower=1)-1).min(),'months':len(r)})
    pd.DataFrame(summaries).to_csv(rf_dir/'ridge_aligned_summary.csv',index=False)
index=[]
def add(**kw):
    base=dict(family='',name='',summary_path=None,ledger_path=None,frequency='',execution='',cost='',
              evidence_role='diagnostic',limitations=[],status='NOT_REVIEWED_BY_PARENT',source_certified=False)
    base.update(kw)
    for k in ['summary_path','ledger_path']:
        if exists(base[k]):base[k+'_sha256']=sha(ROOT/base[k])
    index.append(base)

for row in old['inventory']:
    family,name,key=row[:3];source=sources.get(row[-2],'')
    if not ('轮动' in family or 'QQQ择时' in family):continue
    common=dict(family=family,name=name,legacy_name=key,legacy_source=source,legacy_inventory_record=True)
    if family=='行业轮动信号组合':
        signal,hold,regime=key.split(' / ')
        role='portfolio_revised_history' if hold=='1M' and regime=='all' else 'diagnostic_conditional_or_overlapping'
        add(**common,summary_path='research/sector_rotation/backtest_results.csv',ledger_path=f'research/sector_rotation/detail_{signal}_{regime}_h{hold[0]}.csv',
            frequency='monthly' if hold=='1M' else 'monthly 3-month forward labels',execution='T+2 close to next T+2 close',cost='gross; no transaction costs',evidence_role=role,
            status='RERUN_AWAITING_PARENT_REVIEW',limitations=['historical PE vintages unverified','ETF price / sector-index PE is an earnings proxy','conditional/overlapping samples have no portfolio CAGR'])
    elif family=='行业轮动随机森林':
        add(**common,frequency='legacy monthly',evidence_role='superseded_unreproducible_spec',status='BLOCK_SPEC_MISSING',
            limitations=['Saved legacy six configurations include RF Classifier; current source has only RF Regressor/Ridge. Exact old implementation/spec unavailable. New runs are indexed separately.'])
    elif family=='行业轮动固定模型':
        namefile='Ridge_Top1_monthly.csv' if key=='strategy' else 'SPY_Ridge_Top1_aligned_monthly.csv'
        add(**common,summary_path='research/sector_rotation/results_v2/ridge_aligned_summary.csv',ledger_path='research/sector_rotation/results_v2/'+namefile,
            frequency='monthly',execution='T+2 close to next T+2 close',cost='gross; no transaction costs',evidence_role='portfolio_revised_history',status='RERUN_AWAITING_PARENT_REVIEW',
            limitations=['historical PE vintages unverified','benchmark must use this exact ledger window'])
    elif source.endswith('sep_falsification_test.py'):
        add(**common,summary_path='research/strategy_comparison/results_v2/sep_summary.csv',frequency='event driven',execution='next trading day close',cost='10 bp per trade',
            evidence_role='parameter_diagnostic',status='RERUN_AWAITING_PARENT_REVIEW',limitations=['20 inherited parameter combinations; not 20 independently designed strategies','official median source starts 2015-09-17; 2012 start rejected','see individual new rows'])
    else:
        add(**common,frequency='event driven / daily marks',evidence_role='blocked_entry',status='BLOCK_SOURCE_IDENTITY',
            limitations=['Entry requires verified direct Nasdaq-100 aggregate EPS identity/vintages; absent. SP500_EPS is wrong index for the claimed source. --revised-history cannot bypass. No new EPS modelling.'])

rf_dir=ROOT/'research/sector_rotation/results_v2'
summary=rf_dir/'model_summary.csv'
if summary.exists():
    for row in pd.read_csv(summary).to_dict('records'):
        label=row['label'];fn=(label.split()[0]+'_monthly.csv') if '(aligned' in label else label.replace(' ','_')+'_monthly.csv'
        add(family='行业轮动现行模型 v8',name=label,summary_path=str(summary.relative_to(ROOT)),ledger_path=str((rf_dir/fn).relative_to(ROOT)),
            frequency='monthly',execution='T+2 close to next T+2 close',cost='gross; no transaction costs',evidence_role='portfolio_revised_history',status='RERUN_AWAITING_PARENT_REVIEW',
            limitations=['historical PE vintages unverified','models launch at different dates; compare on common entry/exit dates','old Classifier results are not reproduced by these regressors'],
            actual_window={k:row.get(k) for k in ['first_signal','last_signal','first_entry','last_exit','months']})
common_summary=rf_dir/'model_common_period_summary.csv'
if common_summary.exists():
    for row in pd.read_csv(common_summary).to_dict('records'):
        label=row['label']
        add(family='行业轮动现行模型共同期间',name=label,summary_path=str(common_summary.relative_to(ROOT)),
            ledger_path=str((rf_dir/'common_monthly'/(label.replace(' ','_')+'_monthly.csv')).relative_to(ROOT)),
            frequency='monthly',execution='T+2 close to next T+2 close; exact shared holding windows',cost='gross; no transaction costs',
            evidence_role='portfolio_revised_history_common_period',status='RERUN_AWAITING_PARENT_REVIEW',
            actual_window={k:row.get(k) for k in ['first_signal','last_signal','first_entry','last_exit','months']},
            limitations=['historical PE vintages unverified','slice of already rerun native ledger, not new fitting or tuning','monthly drawdown hides within-month risk'])

sep_summary='research/strategy_comparison/results_v2/sep_summary.csv'
sep_run=ROOT/'audit_v2/rotation_macro_runs/strategy_comparison/sep_falsification_test/execution_gate.json'
if exists(sep_summary) and sep_run.exists() and json.loads(sep_run.read_text())['status']=='SUCCESS':
    for row in pd.read_csv(ROOT/sep_summary).to_dict('records'):
        p,r=row['pce'],row['rate'];name=f'SEP PCE>{p}, rate change>{r}'
        add(family='纯SEP既有参数检验',name=name,summary_path=sep_summary,ledger_path=f'research/strategy_comparison/results_v2/sep_pce{p}_rate{r}_daily.csv',
            frequency='event driven',execution='next trading day close after SEP meeting',cost='10 bp one way, initial purchase charged; prior-day DFF calendar-day cash yield assumption',
            evidence_role='portfolio_parameter_diagnostic',status='RERUN_AWAITING_PARENT_REVIEW',limitations=['2015-09-18 onward only; earlier PDFs contain ranges, not medians','initial state IN at start; no pre-source simulated signals','cash rate is an assumption, not realized fund yield','same historical data already examined; not new holdout'])
    add(family='纯SEP既有参数检验',name='QQQ buy and hold matched',ledger_path='research/strategy_comparison/results_v2/QQQ_buy_hold_daily.csv',
        frequency='buy and hold',execution='first sample close',cost='10 bp initial purchase',evidence_role='benchmark',status='RERUN_AWAITING_PARENT_REVIEW',limitations=['price-cache dividend adjustment provenance not independently certified'])

skip={'engine.py','audit_scope.py','source_gate.py','strategy_engine.py','audit_calendar.py'}
entries=[]
def entry_log(family,stem):
    special={'run_backtest':'rotation_macro_run_backtest.log','rf_backtest':'rotation_macro_rf_backtest.log',
             'rf_audit':'rotation_macro_rf_audit.log','sep_falsification_test':'rotation_macro_sep.log'}
    names=[special.get(stem,''),f'rotation_macro_revised_{family}_{stem}.log',f'rotation_macro_gates_{family}_{stem}.log']
    return next((f'audit_v2/{n}' for n in names if n and (ROOT/'audit_v2'/n).exists()),None)

specific={
 'run_backtest':['RM03','RM04','RM20'], 'rf_backtest':['RM05','RM14','RM21'],
 'rf_audit':['RM22'], 'direct_eps_test':['RM06'], 'single_feature_ic':['RM06'],
 'macro_shock_test':['RM06','RM11'], 'real_yield_confirmation':['RM11','RM18'],
 'dynamic_beta_test':['RM11'],'macro_event_study':['RM11'],
 'waterfall_autopsy_step3_rf':['RM11'],'waterfall_autopsy_step3_5_cagr':['RM11'],
 'fetch_sector_data':['RM17'],'waterfall_autopsy':['RM17'],
 'sep_falsification_test':['RM09','RM10'], 'episode_robustness':['RM12'],
 'hawkish_path_backtest_v2':['RM12'], 'final_validation':['RM12','RM13'],
 'pubdate_matched_perm':['RM12','RM13']}
for family in ['sector_rotation','strategy_comparison','hawkish_path']:
    for p in sorted((ROOT/'research'/family).glob('*.py')):
        if p.name in skip:continue
        rel=str(p.relative_to(ROOT));run_dir=ROOT/'audit_v2/rotation_macro_runs'/family/p.stem
        records=[]
        for fp in sorted(run_dir.glob('execution*.json')):
            record=json.loads(fp.read_text());records.append({'record':str(fp.relative_to(ROOT)),**record})
        revised=[x for x in records if '--revised-history' in x.get('args',[])]
        gate=[x for x in records if '--revised-history' not in x.get('args',[])]
        latest=(revised[-1] if revised else gate[-1] if gate else None)
        finding_ids=list(specific.get(p.stem,[]))
        if family=='sector_rotation' and p.stem not in ['fetch_sector_data','waterfall_autopsy']:
            finding_ids+=['RM01','RM02','RM15','RM16']
        if family=='hawkish_path':finding_ids+=['RM15','RM16']
        eps=family=='strategy_comparison' and p.stem!='sep_falsification_test'
        if eps:finding_ids+=['RM07','RM19']
        missing=(['Verified direct Nasdaq-100 aggregate EPS identity, source methodology, publication/vintage timestamps'] if eps else
                 ['Historical PE and macro vintages; source index/ETF price compatibility proof'] if family=='sector_rotation' else
                 ['Historical Kim-Wright releases and actual publication-day/time map'] if family=='hawkish_path' else
                 ['Pre-2015-09-17 official SEP medians unavailable; earlier periods excluded','Original QQQ total-return adjustment provenance is not independently certified'])
        if p.stem=='waterfall_autopsy':missing=['Actual implementation; inherited file is a template']
        if p.stem=='fetch_sector_data':missing=['Not a strategy; downloader disabled under frozen offline contract']
        log=entry_log(family,p.stem)
        outputs=list(latest.get('outputs',[])) if latest else []
        if p.stem=='run_backtest':outputs+=['research/sector_rotation/backtest_results.csv']+[str(x.relative_to(ROOT)) for x in sorted((ROOT/'research/sector_rotation').glob('detail_*_h*.csv'))]
        if p.stem=='rf_backtest':outputs+=[str(x.relative_to(ROOT)) for x in sorted(rf_dir.glob('*.csv'))]+[str(x.relative_to(ROOT)) for x in sorted((rf_dir/'common_monthly').glob('*.csv'))]
        if p.stem=='sep_falsification_test':outputs+=[sep_summary,'research/strategy_comparison/sep_parser_audit_v2.json']+[str(x.relative_to(ROOT)) for x in sorted((ROOT/'research/strategy_comparison/results_v2').glob('*_daily.csv'))]
        if p.stem=='hawkish_path_backtest_v2':outputs+=['research/hawkish_path/hawkish_path_v2_results.csv']
        entries.append({'entry':rel,'source_sha256':sha(p),'syntax':'PASS' if ast.parse(p.read_text()) else 'FAIL',
                        'code_review':'completed by writer; parent independent review required','execution_records':records,
                        'latest_execution_status':latest['status'] if latest else 'PENDING',
                        'disposition':'REJECTED_EARLY_STOP_AFTER_FAILED_GATES' if p.stem=='rf_audit' else ('BLOCK_SOURCE_IDENTITY' if eps else 'RERUN_REVISED_HISTORY_ONLY' if latest and latest['status']=='SUCCESS' else 'BLOCKED_NOT_EXECUTABLE'),
                        'finding_ids':finding_ids,'repairs_and_checks':'See the referenced finding records and actual check artifacts; no writer approval',
                        'check_artifacts':['audit_v2/rotation_macro_checks.json','audit_v2/rotation_macro_ledger_checks.json'] if not eps else ['audit_v2/rotation_macro_eps_identity_gates.json'],
                        'missing_data_or_scope':missing,'log':log,'log_sha256':sha(ROOT/log) if log else None,
                        'actual_command':['python3','audit_v2/rotation_macro_execute.py',rel,*latest.get('args',[])] if latest else None,
                        'outputs':[{'path':x,'sha256':sha(ROOT/x)} for x in dict.fromkeys(outputs) if exists(x)],
                        'source_certified':False,'review_dimensions':['source identity and vintages','signal/training timing','portfolio versus label windows','cost and cash assumptions','compounding and sample gaps','benchmarks and repeated historical testing']})
        if family=='sector_rotation' and p.name not in ['run_backtest.py','rf_backtest.py','fetch_sector_data.py','waterfall_autopsy.py']:
            add(family='行业轮动诊断研究',name=p.stem,summary_path='audit_v2/rotation_macro_rf_early_stop.json' if p.stem=='rf_audit' else latest['outputs'][0] if latest and latest.get('outputs') else log,
                frequency='research / monthly observations',evidence_role='diagnostic_not_portfolio',status='REJECTED_EARLY_STOP_AFTER_FAILED_GATES' if p.stem=='rf_audit' else latest['status'] if latest else 'BLOCKED',
                limitations=['current-vintage inputs, gross descriptive statistics','conditional samples and placebo results are not independent live validation','see execution log and entry-specific findings']+(['500-seed placebo interrupted; p-values unavailable; five failed gates force original rejection'] if p.stem=='rf_audit' else []),entry=rel)
        if family=='hawkish_path':
            add(family='鹰派路径信号研究',name=p.stem,summary_path='research/hawkish_path/hawkish_path_v2_results.csv' if p.stem=='hawkish_path_backtest_v2' else latest['outputs'][0] if latest and latest.get('outputs') else log,
                frequency='daily event observations',evidence_role='diagnostic_not_portfolio',status=latest['status'] if latest else 'RUNNING_OR_PENDING',
                limitations=['Kim-Wright current vintage, not historical releases','Tuesday release map is assumed, not source-proven','forward windows can overlap; calendar/random-date null is exploratory','no strategy wealth/CAGR'],entry=rel)

hawk='research/hawkish_path/hawkish_path_v2_results.csv'
for row in pd.read_csv(ROOT/hawk).to_dict('records'):
    add(family='鹰派路径条件统计',name=f"{row['Ticker']} / {row['Regime']}",summary_path=hawk,
        frequency='daily signal observations; overlapping forward horizons',execution='no portfolio trades',cost='gross forward price changes',
        evidence_role='diagnostic_not_portfolio',status='RERUN_AWAITING_PARENT_REVIEW',
        limitations=['not a tradable strategy or CAGR','current-vintage KW source; historical release timestamps unknown','overlapping windows and repeated exploratory analysis'])

for family,fn,ids,scope in [('sector_rotation','engine.py',['RM01','RM02','RM15'],'Actual RF/Ridge and diagnostic reruns plus synthetic missingness/ledger tests'),
                          ('strategy_comparison','strategy_engine.py',['RM08','RM09'],'Actual SEP parser path and source counterexamples; TQQQ simulator synthetic tests only, no full real-data caller run')]:
    rel=f'research/{family}/{fn}';entries.append({'entry':rel,'source_sha256':sha(ROOT/rel),'code_review':'writer reviewed; parent required',
        'entry_kind':'library','finding_ids':ids,'tested_scope':scope,'latest_execution_status':'LIBRARY_TESTED_WITH_LIMITS','source_certified':False,
        'check_artifacts':['audit_v2/rotation_macro_checks.json'],'missing_data_or_scope':['Full real TQQQ input/caller integration not provided'] if family=='strategy_comparison' else ['Historical PE vintages unknown']})

findings=[
 ('RM01','engine.py','Cross-sectional z-score changed missing features into zero when standard deviation was unavailable. Preserve missingness; strict universe now remains invalid.','FIXED_TESTED'),
 ('RM02','engine.py','Automatic cache refresh could change frozen inputs/network. All pricing reads now validate local adjusted-price schema; refresh blocked.','FIXED_TESTED'),
 ('RM03','run_backtest.py','Same-close execution and returns recomputed on filtered signal rows. Daily T+2 execution now required; use full price rows for forward windows.','FIXED_TESTED_RERUN'),
 ('RM04','run_backtest.py','Regime-filtered months and overlapping 3m forward returns cannot be compounded as continuous wealth. CAGR suppressed; end month inclusive.','FIXED_TESTED_RERUN'),
 ('RM05','rf_backtest.py','Annual breakdown used mean*12 even for partial years. Changed to actual compounded annual sample return and exported every ledger.','FIXED_RERUN'),
 ('RM06','direct_eps_test.py / single_feature_ic.py / macro_shock_test.py','CAGR after filtered missing months compresses time. Require contiguous monthly rows or leave CAGR undefined.','FIXED_TESTED_RERUN'),
 ('RM07','source_gate.py and 9 EPS entries','Retrospective flag was bypassing unknown EPS index identity. Unconditional source gate now rejects even the flag. SP500_EPS used in three entries is not Nasdaq-100 aggregate EPS.','FIXED_GATE_TESTED'),
 ('RM08','strategy_engine.py','Bankruptcy reset wealth to .001 and allowed recovery. Zero wealth now absorbs; initial buy cost charged, no missing-return zero-fill.','FIXED_UNIT_TESTED_LIBRARY_ONLY'),
 ('RM09','strategy_engine.py / sep_falsification_test.py','SEP range endpoints and wrong rotated-PDF extraction became year medians. Read rotated table layout and actual median columns; early range-only publications marked unavailable; start 2015-09-18.','FIXED_SOURCE_COUNTEREXAMPLES_RERUN'),
 ('RM10','sep_falsification_test.py','First return preceded sample, first cost omitted, exit/reentry uncharged, cash used same-day DFF and trading-day annual fraction. Use first-close initial buy, costs, prior published rate/calendar accrual.','FIXED_RERUN'),
 ('RM11','six macro diagnostic scripts','Hardcoded paths read original workspace rather than frozen copy. Paths now resolve under this copy.','FIXED_RERUN'),
 ('RM12','hawkish_path/audit_calendar.py','Inner join removed equity sessions, so 21/63/126 rows were not actual trading-day horizons. Use full exchange calendar with backward-only signal carry and no invented post-coverage signals.','FIXED_TESTED_RERUN'),
 ('RM13','final_validation.py / pubdate_matched_perm.py','Real and random samples used different complete-horizon counts; finite Monte Carlo could output p=0; label falsely called translation circular bootstrap. Complete 3/6m real samples, add-one p, truthful method label.','FIXED_RERUN_EXPLORATORY_ONLY'),
 ('RM14','rf_backtest_results.csv','Six stored legacy classifier/regressor configs are not the six current source configs. Exact superseded implementation missing.','BLOCK_SPEC_MISSING'),
 ('RM15','sector PE and macro sources','Current-vintage PE and ETF-price/index-PE mismatch cannot establish genuine forward EPS or point-in-time availability.','UNVERIFIED_SOURCE'),
 ('RM16','all exploratory significance studies','Labels, features, thresholds and episodes have been repeatedly inspected; randomization assumptions and multiple exploratory studies do not make a new blind test.','LIMITATION'),
 ('RM17','fetch_sector_data.py / waterfall_autopsy.py','Downloader is not a strategy; waterfall_autopsy.py is an unimplemented template. Safe explicit gates replace misleading success.','GATE_TESTED'),
 ('RM18','real_yield_confirmation.py','Compound long-short spread lacked capital/cost definition, and exhaustive basket p-value added an extra identity draw. Report arithmetic spread; exact enumeration counts each basket once.','FIXED_RERUN'),
 ('RM19','strategy_comparison_v1.py through v5.py','Legacy EPS-based engines also have cost and first-sample timing inconsistencies. They are not admitted as portfolio evidence; source identity blocks execution before new historical modelling.','UNRESOLVED_BEHIND_SOURCE_GATE'),
 ('RM20','run_backtest.py','Future-return inner join dropped unpriceable candidates before ranking. Rank formation-day scores first; common execution dates; selected missing price raises instead of replacement. Seven-ETF counterexample and full frozen rerun.','FIXED_TESTED_RERUN'),
 ('RM21','rf_backtest.py','Generic aligned labels hid 44-month benchmark versus 40-month full-universe models. Record per-row actual dates and months, preserve native ledgers, export separate shared-window comparison.','FIXED_RERUN'),
 ('RM22','rf_audit.py','Original first five of seven acceptance checks failed. Original thresholds require at least six passes, impossible even if both unfinished placebo checks pass. Parent stopped original 500-seed job; exit 1 KeyboardInterrupt preserved, no p-values invented.','REJECTED_EARLY_STOP_AFTER_FAILED_GATES')]
report={'status':'PARTIAL_AWAITING_PARENT_REVIEW','entries':entries,'findings':[dict(id=x[0],file=x[1],finding=x[2],disposition=x[3]) for x in findings],
        'strategy_index_count':len(index),'legacy_inventory_records_covered':sum(x.get('legacy_inventory_record',False) for x in index),
        'original_python_files':34,'libraries_exercised':['research/sector_rotation/engine.py','research/strategy_comparison/strategy_engine.py'],
        'acceptance':'Writer does not self-approve. All runnable portfolio paths rerun; RF audit rejected with explicit early termination. Source certification remains limited.',
        'no_work_running':True,'remaining_external_blockers':['Direct Nasdaq-100 aggregate EPS identity and historical vintages','Sector PE and macro historical vintages','Six superseded RF configuration implementations unavailable'],
        'rf_early_stop':'audit_v2/rotation_macro_rf_early_stop.json','unit_checks':'audit_v2/rotation_macro_checks.json','independent_repricing':'audit_v2/rotation_macro_ledger_checks.json',
        'flow':'Frozen CSV/JSON/PDF -> source and time checks -> counterexamples -> actual reruns/ledgers -> parent review -> common-period comparison; missing EPS identity remains blocked'}
(ROOT/'audit_v2/rotation_macro_strategy_index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2,allow_nan=False))
(ROOT/'audit_v2/rotation_macro_disposition.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('index',len(index),'legacy',report['legacy_inventory_records_covered'],'entries',len(entries))
