from pathlib import Path
import json,hashlib,datetime,collections,ast,shutil
R=Path(__file__).resolve().parents[1];A=R/'audit_v2';ROOT=R.parents[1];OUT=ROOT/'outputs/backtest_full_audit_v2_20261030';W=OUT/'work'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,j):p.write_text(json.dumps(j,ensure_ascii=False,indent=2,allow_nan=False))
d=read(W/'data.json');assert len(d['inventory'])==340 and len(d['grid'])==96 and len(d['signals'])==91
assert not any('PENDING_FINAL' in str(x.get('audit_status','')) for x in d['records'])
for s in d['sources']:
 if s['sha256']:assert sha(R/s['path'])==s['sha256'],s['path']
for r in read(A/'root_closeout_runs.json')+read(A/'root_selection_checks.json'):assert r['exit']==0,r['name']
for x in ['root_factors_review.json','rotation_cross_review.json','legacy_cross_review.json','root_execution_gate.json','root_daily_gap_gate.json','root_ml2_final_stat_review.json']:
 assert 'PASS' in read(A/x)['status'],x
assert read(W/'workbook_verification.json')['status']=='PASS'
assert sha(OUT/'全部回测审核与同期比较_Codex_v2.xlsx')==read(W/'workbook_verification.json')['sha256']
for c in read(A/'root_cfo_truncation.json')['checks']:assert c['pass']
assert read(A/'root_cfo_truncation.json')['source_sha256']==sha(R/'research/sector_stock_momentum/ml2_features.py')
ml2=next(x for x in read(A/'root_closeout_runs.json') if x['name']=='ml2_complete')
for n in ['backtest.py','ml2_run.py','ml2_features.py','winners_tracks.py','portfolio_accounting.py']:assert ml2['source_hashes'][n]==sha(R/'research/sector_stock_momentum'/n),n
con=read(A/'ml2_concentration_checks.json');assert con['strategies']==17 and con['verified_months']==2397
for p,h in con['outputs_sha256'].items():assert sha(A/p)==h
write(A/'final_strategy_register.json',d['records'])
changed=[]
for x in read(A/'baseline.json')['baseline_files']:
 p=R/x['path'];h=sha(p) if p.is_file() else None
 if h!=x['sha256']:changed.append({'path':x['path'],'before':x['sha256'],'after':h})
write(A/'changed_files_v2.json',changed)
oldcounts=dict(collections.Counter(r[4] for r in d['inventory']))
review={'status':'AUDIT_COVERAGE_COMPLETE_WITH_EXPLICIT_BLOCKS','auditor':'Codex audited and modified','review_date':'2026-10-30','original_catalog':340,'catalog_status_counts':oldcounts,'counts':d['counts'],
 'acceptance':{'all_catalog_records_dispositioned':True,'unchanged_original_and_parent_required':True,'current_usable_ledgers_recomputed':372,'monthly_ledger_checks':645,'all_comparisons_share_reported_dates':True,'execution_and_cost_differences_disclosed':True,'all_monthly_rebalance':False,'all_strategies_pass':False,'historical_source_certification':False,'prospective_trading_skill_established':False},
 'late_review_closures':{'RSC-04':'Implemented and independently rerun audit_v2/ml2_concentration_diagnostic.py: 17 frozen lines, 2397 original month reconciliations; same cash yield; no reselection.', 'price_truncation_test':'6 cutoffs x 4 configurations, zero pick differences; root_selection_checks.json','determinism_test':'3 hash seeds x 4 configurations, identical picks; root_selection_checks.json','legacy_test_fixture':'Existing timing regression fixture now supplies required outcome status; all original 6 assertions pass. Earlier failed log retained.','daily_risk':'Observed holding-day quote required; no forward-filled or endpoint-rescaled daily NAV. Missing path blocks dependent variants.'},
 'root_macro_coverage':{'backtest.js / backtest_v2.js':'Reviewed wrappers delegate to canonical v3; v3 cached replay and regression suite executed.','backtest_v3.js':'Current-vintage replay allowed only with explicit flag; normal source gate blocks missing historical vintages.','backtest/validate_modules.js / validate_composite.js':'Obsolete incompatible schema blocked with exit2; helper rank-tie/missing-return defects fixed. Supported Phase3/4/5/6 researchers were actually run.','backtest/build_historical_snapshots.js':'Static reviewed fixed-lag approximation; source release vintages unavailable, not certified PIT, not silently promoted to real-time evidence.','macro_engine.js / dashboard':'Original untouched; v2 only consumes copied/frozen backtest inputs.'},
 'source_limitations':['S&P / NDX history and sector/issuer continuity not fully independently certified.','4 manual exit records: two stock-merger terminal values retain explicit close-price approximation.','Non-SP stock pool is not complete historical total market; post-2018 survivorship bias remains.','QQQ aggregate EPS index identity/vintages missing; nine entrypoints safely blocked.','Monthly same-close and open fallback assumptions remain; daily source gaps cannot be reconstructed.','Historical samples have been repeatedly viewed; successful reruns do not create blind out-of-sample evidence.'],
 'new_external_check':'Alpaca SIP spot check: MU/SNDK/SPY 2026 March-May raw month-end closes, 9/9 exact match. Only new audit evidence, not a changed model input.',
 'git_scope':'Only task code, reports and bounded evidence artifacts; cached multi-gigabyte source snapshots remain local, original/dashboard automatic edits excluded.'}
write(A/'FINAL_REVIEW.json',review)
lines=['Codex audited and modified — FULL AUDIT v2','日期：2026-10-30','',
 '结论：审核覆盖完成，但不是全部策略合格。修复和可执行重跑已完成；不能验证的项明确阻塞，不把旧成绩当新结果。','',
 '原目录340条：201条重跑并核算；34条重跑但股票池/价格有缺口；90条阻塞；11条条件统计；4条旧结果退役。',
 '另外120条补充记录、96组原参数、91项信号研究均有表。372个唯一账本，645项月历/收益/费用核对。','',
 '股票同期：2023-01至2026-09，45个月。另有2015-01至2026-09，141个月长表；执行与费用按原规则分组。',
 '策略 | 同期年化 | 月末最大回撤 | 2023-2025年化 | 2026前9月累计']
for r in d['headline']:lines.append(f'{r[0]} | {r[1]:.1%} | {r[2]:.1%} | {r[3]:.1%} | {r[4]:.1%}')
lines += ['', '怎么看：同收盘科技三因子Top1是本次历史最高；未证明最可靠。SPY买入持有是最简单、最容易独立核验的基准。',
 'ML2在相同次日成交口径下，纯动量Top1胜过模型冠军；2015起模型冠军C-lgbm Top1年化33.39%，其中SNDK贡献约92.6%的净利润。去掉它且同权重留现金后年化约16.44%。',
 '行业轮动：完全相同40个持有区间（2023-04-04至2026-08-04），QQQ年化28.58%、SPY22.49%、最好现行RF模型17.86%，均未扣交易成本。',
 'SEP：20组既有参数与买入持有另表，2015-09-18起事件交易；不是每月换仓。早期PDF区间不能当中位数预测。','',
 '不是全部monthly rebalance：多数股票组合每月检查/调仓；T1每月开新批次、分批持有六个月；SEP事件触发；ETF基准买入持有；信号研究没有可投资组合。','',
 '股票池：标普历史池通常498只可用（484-505），适合大盘股研究，但659个股票×月份有硬缺口；纳指额外增加中位21只。非标普实际月度可选880-1734只，中位1279；数量多不代表完整历史小中盘池。','',
 '做了哪些修正：']
for row in d['fixes']:lines.append(f'- {row[0]}：{row[1]}')
lines += ['', '验证：18项因子反例、15项旧ML反例、23项轮动反例与独立交叉复核；股票价6个截断日、3个随机哈希种子均未改变已有选股；财务特征3个时点截断通过。',
 '旧附加回归和旧ML2测试夹具曾失败，修复后的日志另存；旧失败不删除。RF500次placebo实际早停，原前5接受门均失败，剩2门全部通过也达不到原6/7要求，未伪造结果。',
 '所有数据真实性没有整体认证。当前结果都是已看过历史的重放，不是新盲测；月末回撤可能低估月中风险。',
 '原始输入未修改；原目录Claude audited为用户指定历史归属标签，本次不替Claude审计背书。父版保留不变；v2单独修改，dashboard不改。','',
 '输入 → 全入口审核与修复 → 真实重跑/独立核算完成 → 同期比较完成 → 源数据缺口明确保留。','',
 '工作簿：'+str(OUT/'全部回测审核与同期比较_Codex_v2.xlsx'),
 '主审结论：audit_v2/FINAL_REVIEW.json','逐条记录：audit_v2/final_strategy_register.json','文件指纹：audit_v2/final_manifest_v2.json','与父版差异：audit_v2/changed_files_v2.json',
 '本轮audit_v2是有效入口；继承的audit/、旧PASS/README、未列入新索引的旧CSV均不能作为当前重跑证据。']
(A/'FINAL_REPORT.txt').write_text('\n'.join(lines)+'\n');shutil.copy2(A/'FINAL_REPORT.txt',OUT/'审计说明_人话版.txt')
(R/'README.txt').write_text('Codex audited and modified — full audit v2\n2026-10-30：全部回测目录审核处置完成，可执行分支修复和重跑完成；部分数据/规则缺证阻塞，不等于全部合格。\n\n先读 audit_v2/FINAL_REPORT.txt\n审计结论 audit_v2/FINAL_REVIEW.json\n完整策略 audit_v2/final_strategy_register.json\n版本证据 audit_v2/final_manifest_v2.json\n差异记录 audit_v2/changed_files_v2.json\n\n父版2026-10-30_codex_audited_modified封存不变；最初原目录保留Claude audited用户指定归属标签。\n只修改独立回测副本，dashboard未改。继承旧audit/与未在新索引列出的结果不是本轮通过证据。\n')
v=read(R/'VERSION.json');v.update(label='Codex audited and modified — full audit v2',status='AUDIT_COVERAGE_COMPLETE_WITH_EXPLICIT_BLOCKS',parent_label='Codex audited and modified (v1)',original_label='Claude audited (user-assigned attribution)',report='audit_v2/FINAL_REPORT.txt',stock_pool_report='audit_v2/FINAL_REPORT.txt',changed_files='audit_v2/changed_files_v2.json',final_manifest='audit_v2/final_manifest_v2.json',certification='Implementation/replay review complete; historical data and prospective skill not fully certified',completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());write(R/'VERSION.json',v)
p=A/'CONTRACT.txt';txt=p.read_text().replace('当前版本：Codex full audit v2，进行中。','当前版本：Codex full audit v2，审计覆盖完成，含明确阻塞项。').replace('当前：副本和源码基线已建立；正在分支审核。','当前：副本、审核修复、可执行重跑、独立复核、同期比较已完成；缺证项不作通过。');p.write_text(txt)
print('Final review/report generated:',d['counts'])
