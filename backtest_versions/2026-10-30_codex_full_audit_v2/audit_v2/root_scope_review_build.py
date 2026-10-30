"""Read-only inventory of every sector-stock Python source and bounded audit evidence."""
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'research/sector_stock_momentum'
AUD = ROOT / 'audit_v2'
OWN = set('ml_features ml_pipeline explosive_factors explosive_v2 improve_v3 risk_report legacy_portfolio'.split())
FACTORS = set('eps_momentum composite3 mom30_roe sma200_overlay tech_only factor_screen factor_combo ndx_expand'.split())

def load(name, fallback=None):
    p = AUD / name
    return json.loads(p.read_text()) if p.exists() else fallback

RUNS = [r for n in ['root_runs.json', 'root_dependent_runs.json', 'root_final_execution_runs.json', 'root_closeout_runs.json'] for r in load(n, [])]
def evidence(*names):
    return [{'name': r['name'], 'exit': r.get('exit'), 'log': r.get('log'),
             'command': r.get('command'), 'seconds': r.get('seconds')}
            for r in RUNS if r.get('name') in names]

# These statements describe inspected code and bounded tests, not vendor/source certification.
DATA = {
 'build_fundamentals': ('derived_fundamental_builder', 'Functions covered by PIT tests; archive-to-entire-panel build not rerun in this read-only review.',
     ['First-report and field-specific availability are explicit; FY minus nine-month EPS and summed EPS TTM are approximations, since EPS is not additive.', 'CIK mappings include current SEC lists, names and manual exceptions; not all historical identities independently source-certified.'], ['fundamentals', 'fundamental_truncation']),
 'fundamentals_pit': ('point_in_time_accessor', 'Core accessor exercised in source-date, split-basis and full/truncated feature comparisons.',
     ['Uses cached SEC derivations, field availability and maximum-age gates; a passed truncation test proves time consistency on these caches, not raw filing accuracy.', 'Split records/CIK intervals are incomplete source evidence; common split basis is not an official index-level EPS series.'], ['fundamentals', 'fundamental_truncation']),
 'ml2_features': ('strategy_feature_builder', 'Independent TTM counterexamples and actual cached-data truncation checks passed at reviewed hash.',
     ['TTM CFO = preceding FY + current YTD - prior-year same-quarter YTD; current missing state invalidates prior valid value, and late component availability emits a later state.', 'Latest independent checks are in root_patch_review.json; root_cfo_truncation.json covers three cached cutoffs.'], ['fundamental_truncation']),
 'historical_sectors': ('historical_classification_helper', 'Read-only review; used by real cached strategy runs.',
     ['Reconstructs major 2016/2018/2023 GICS changes only. Other company-level sector changes are not fully reconstructed.', 'Some 2018 media classifications are fallback assumptions; cannot claim complete historical GICS certification.'], ['main', 'stock_pool', 'ndx_pool']),
 'ticker_aliases': ('identity_helper', 'Read-only review; exercised by cached price loading.',
     ['Same SEC CIK, membership adjacency and name evidence can support alias candidates but do not prove security/share-class continuity for every merger or spin-off.', 'Heuristics and manual exceptions remain conditional source evidence.'], ['main', 'stock_pool']),
 'ndx_universe': ('membership_price_union_helper', 'Cached union path exercised by pool audit and factor-agent NDX branch.',
     ['Historical membership comes from frozen third-party YAML plus symbol-map choices, not independently certified complete Nasdaq notices.', 'Excluded/unmapped symbols and missing price histories limit the usable union; S&P raw file wins source collisions.'], ['ndx_pool']),
 'build_ndx_membership': ('membership_builder', 'Static semantics reviewed; not rerun to rewrite frozen membership inputs.',
     ['Applies effective-date union/difference operations from cached annual YAML.', 'Embedded sample assertions are not complete verification of all historical additions/removals.'], []),
 'ndx_fundamentals': ('derived_fundamental_builder', 'Static review; not rerun to rewrite frozen source-derived inputs.',
     ['Uses build_fundamentals approximations and manually mapped CIKs.', 'Foreign 20-F/40-F issuers absent from 10-K/10-Q extracts retain missing factors; no complete NDX financial coverage certification.'], []),
 'build_gap_ledger': ('coverage_reporting_helper', 'Read-only review; report logic is not a complete source-gap certificate.',
     ['First vendor quote/startDate is used to infer recent listing; it is not independently verified IPO evidence.', 'Summary real_gap excludes some insufficient-history cases; percentages are conditional categories, not total unknown-data rate.'], []),
 'build_manifest': ('provenance_helper', 'Read-only review; hashes establish bytes and paths only.',
     ['A hash cannot certify prices, company identity, availability dates or investment accuracy.', 'Role/path metadata is descriptive and may lag newly added cache types.'], []),
 'convert_wiki_bulk': ('derived_price_builder', 'Static read-only review; top-level transformation not imported or run.',
     ['Writes derived WIKI parquet at module top level; not a strategy or an independent source-authentication test.', 'WIKI history freezes on 2018-03-27.'], []),
 'identity_check': ('identity_diagnostic', 'Read-only diagnostic review; not a performance strategy.',
     ['Cross-vendor correlation and SEC share-based market capitalization are diagnostic evidence, not definitive security continuity.', 'Insufficient overlaps or filings remain unverified; absence of a flag is not a positive identity certificate.'], []),
 'identity_screen_earnings': ('identity_diagnostic', 'Read-only diagnostic review; not independently rerun.',
     ['Earnings-window activity and volume ratios are heuristics for manual review, not legal issuer/security identifiers.', 'Fewer than eight events and data endpoint alignment limit evidence; no stock is certified solely by this screen.'], []),
 'smallcap_universe': ('universe_builder', 'Read-only review against WINNERS_SPEC 5a/5b; consumed by root holdout runner.',
     ['Defines available liquid non-S&P stocks by price >= $5 and median 63-day dollar volume >= $5m; not all U.S. stocks or historical market-cap-defined small caps.', 'WIKI provides dead names before 2018; post-2018 current listings omit many dead firms. Terminal stress on existing selected names cannot restore absent firms.', 'Correlation >= .9 on overlapping vendor returns is an identity heuristic; newly introduced/reused symbols remain a source risk.'], []),
 'smallcap_data_audit': ('price_quality_diagnostic', 'Root F0/F2 handling read-only reviewed; focused bad-print-boundary checks recorded in root_feature_gate.json.',
     ['Only nonpositive adjusted prices are automatically omitted. Large jumps with nearby split records remain unresolved unless magnitude/source evidence is sufficient.', 'F1/F3 strict removals use future reversal/run lengths; STRICT is an ex-post sensitivity diagnostic, not a tradable historical result.', 'Cross-vendor overlap quality does not certify non-overlapping securities.'], []),
}

CORE = {
 'backtest': ('core_backtest', 'Cached main/grid run and ledger/regression tests completed; next-session/manual fix independently verified, final re-execution tracked separately.',
     ['Historical sector/identity/input coverage remains conditional.', 'Same-close signals and execution are the original convention, not an independently executable next-open result.', 'Four cached manual resolutions remain source-dependent; two stock-merger values are successor close approximations.'], ['main', 'main_final', 'ledger', 'stock_regression'], ['RSC-02']),
 'portfolio_accounting': ('shared_portfolio_math', 'Self-financing fee solver, drift, cash and bankruptcy independently exercised through shared consumers.',
     ['Accounting tests certify modeled cash/fees for supplied returns, not execution quality or source data.'], ['ledger', 'ledger_original', 'stock_regression'], []),
 'winners_tracks': ('strategy_entry', 'Cached run completed; independent cash, terminal-interest and EAR tests passed. Daily-dependent variants can be explicitly blocked.',
     ['A monthly return does not prove its daily path. Volatility-target variants require a reconciled path and are unavailable where it fails.', 'Daily cash/borrowing carry is modeled; close marks reconcile only where the path check succeeds; missing held quotes are not filled.', 'Fixed historical candidates and post-hoc supplemental candidates must remain separately labeled.'], ['winners', 'winners_final', 'ledger', 'ledger_original'], []),
 'winners_holdout': ('strategy_entry', 'Source reviewed against frozen 5a-5e; actual run state is recorded from root_dependent_runs.json, not inferred from task creation.',
     ['Source universe has substantial post-2018 survivorship bias.', 'Strict F1/F3 removal is an ex-post diagnostic; observed historical replay is not a fresh untouched examination.', 'Price-only holdout deliberately suppresses survivor-linked fundamental availability per SPEC 5b.'], ['holdout', 'holdout_strict', 'daily_refresh'], []),
 'ml2_run': ('strategy_entry', 'Initial three fixes independently verified; final cached replay must use latest fixed hash. Generic delisted-entry matrix is additionally checked.',
     ['Unknown labels are excluded from fitting, while unknown future test/validation outcomes do not screen candidates.', 'All 12 model lines plus 5 benchmarks are retrospective comparisons; history has been repeatedly inspected.', 'True open marks are unavailable for some sources; fallback/terminal conventions and daily-risk unavailability must be visible.'], ['ml2', 'ml2_final', 'ml2_complete'], ['RSC-01', 'RSC-02', 'RSC-03', 'RSC-04', 'RSC-05', 'RSC-07']),
 'earnings_factor': ('factor_strategy_entry', 'Root patch independently tested; actual legacy chain rebuilt EAR panel and three monthly ledgers.',
     ['Rolling events isolate ticker, issuer and price segment; three-event minimum now checks actual oldest included event <=400 days.', 'Announcement dates/prices remain cached-source evidence; fixed EAR baskets have retrospectively selected development-period factors.'], [], []),
}

TESTS = {
 'test_codex_regressions': ('stock_regression', 'Six recorded regression checks passed; bounded counterexamples do not certify every strategy.'),
 'test_fundamentals_pit': ('fundamentals', 'Specific AMD availability and NVDA split-basis checks passed.'),
 'test_portfolio_ledger': ('ledger_original', 'Three recorded daily/tranche/stress checks passed.'),
 'pit_fundamentals_truncation_test': ('fundamental_truncation', 'Actual cached feature builds matched across three cutoffs, including ML2 history features.'),
 'pit_truncation_test': (None, 'Source reviewed; no current-run execution record identified in root registries. Do not inherit historical PASS as a fresh test.'),
 'determinism_test': (None, 'Source reviewed; no current-run seed-repeat execution record identified in root registries.'),
}

records = []
for p in sorted(SRC.glob('*.py')):
    code = p.read_text(); tree = ast.parse(code); n = p.stem
    row = {'file': str(p.relative_to(ROOT)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
           'ast_parse': 'PASS', 'functions_or_classes': [a.name for a in tree.body if isinstance(a, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))],
           'source_certification': 'UNVERIFIED', 'run_evidence': [], 'finding_ids': []}
    if n in OWN or n in FACTORS:
        row.update(owner='legacy_ml_writer' if n in OWN else 'factors_writer', role='delegated_scope',
                   disposition='See assigned branch evidence; this root-scope review does not self-certify delegated code.',
                   report='audit_v2/legacy_ml_disposition.json' if n in OWN else 'audit_v2/factors_report.json',
                   review_level='COVERAGE_POINTER_ONLY')
    elif n in CORE:
        role, disp, limits, runs, findings = CORE[n]
        row.update(owner='root', role=role, disposition=disp, limitations=limits,
                   run_evidence=evidence(*runs), finding_ids=findings, review_level='CODE_AND_BOUNDED_EXECUTION_EVIDENCE')
    elif n in DATA:
        role, disp, limits, runs = DATA[n]
        row.update(owner='root', role=role, disposition=disp, limitations=limits,
                   run_evidence=evidence(*runs), review_level='STATIC_REVIEW_AND_AVAILABLE_DEPENDENCY_EVIDENCE')
    elif n in TESTS:
        run, disp = TESTS[n]
        row.update(owner='root', role='test_entry', disposition=disp, run_evidence=evidence(run),
                   review_level='TEST_SOURCE_AND_EXECUTION_RECORD', source_certification='NOT_APPLICABLE')
    elif n.startswith('fetch_') or n == 'resolve_successors':
        row.update(owner='root', role='external_data_acquisition', review_level='STATIC_AUXILIARY_REVIEW_ONLY',
                   disposition='Auxiliary acquisition tool, not a strategy. No downloads or raw-cache rewrites were run in this audit branch.',
                   limitations=['API/website/parser compatibility and complete historical coverage not live-verified.',
                                'Cached bytes can be hashed; vendor accuracy, full corporate actions and historical identifier continuity remain unverified.'])
    else:
        raise AssertionError(f'Unclassified source file: {p}')
    records.append(row)

findings = [
 {'id':'RSC-01','severity':'P1','status':'FIX_VERIFIED_FINAL_REPLAY_TRACKED_SEPARATELY','classification':'VERIFIED_BY_COUNTEREXAMPLE',
  'files':['research/sector_stock_momentum/ml2_run.py'],
  'problem':'Source-gap/unresolved placeholder returns enter cross-sectional training ranks and refits as observed labels.',
  'evidence':'Original synthetic annual fold admitted 2 unresolved rows. After repair zero unknown labels reach training/refit and unknown test candidate is retained.',
  'required_action':'Exclude only unknown training labels; keep validation and test candidates feature-defined; filter unknown labels from IC; retrain final ML2.'},
 {'id':'RSC-02','severity':'P1','status':'FIX_VERIFIED_FINAL_REPLAY_TRACKED_SEPARATELY','classification':'VERIFIED_BY_COUNTEREXAMPLE_AND_CODE',
  'files':['research/sector_stock_momentum/backtest.py','research/sector_stock_momentum/ml2_run.py'],
  'problem':'Manual terminal return was anchored to formation close and returned unchanged for next-session execution. Lag-one entry also used forward-filled stale prices.',
  'evidence':'Formation close 100, actual next-session entry 110, payout 110: old return +10%, repaired actual next-close and next-open both return 0%.',
  'required_action':'Use actual execution-day quote, rebase known terminal wealth to actual entry; no real entry stays unresolved; rerun affected execution variants.'},
 {'id':'RSC-03','severity':'P2','status':'FIX_VERIFIED_FINAL_REPLAY_TRACKED_SEPARATELY','classification':'VERIFIED_CODE_PATH',
  'files':['research/sector_stock_momentum/ml2_run.py'],
  'problem':'DSR trial Sharpes and winner input use nominal net returns; shared deflated_sharpe expects excess returns.',
  'required_action':'Subtract date-matched rf for all trial Sharpes and winner DSR. Recompute statistics after final returns.'},
 {'id':'RSC-04','severity':'P2','status':'UNIMPLEMENTED_DIAGNOSTIC_AT_REVIEW','classification':'VERIFIED_SPEC_IMPLEMENTATION_GAP',
  'files':['research/sector_stock_momentum/ml2_run.py','research/sector_stock_momentum/ML2_SPEC.md'],
  'problem':'SPEC section 7 requests removing largest-contribution stock and best year as sensitivity diagnostics; no such computation is present in current run output path.',
  'required_action':'Either compute these diagnostics without candidate/parameter expansion or explicitly disclose their absence. Existing CAGR is not invalidated by absent diagnostics.'},
 {'id':'RSC-05','severity':'P2','status':'SOURCE_EXECUTION_LIMITATION','classification':'VERIFIED_CACHED_RESOLUTION_SEMANTICS',
  'files':['research/sector_stock_momentum/data/exit_resolutions.csv','research/sector_stock_momentum/ml2_run.py'],
  'problem':'ANDV and SCG manual stock-merger terminal values use successor month-end close approximations, not a fully observed successor next-session open path. Cash-payout rebasing alone does not prove exact open-to-open liquidation.',
  'required_action':'Preserve explicit terminal approximation label or obtain verified successor execution evidence; do not silently call all terminal returns exact open-to-open.'},
 {'id':'RSC-06','severity':'P2','status':'SOURCE_CERTIFICATION_GAP','classification':'VERIFIED_SCOPE_LIMITATION',
  'files':['research/sector_stock_momentum/smallcap_universe.py','research/sector_stock_momentum/historical_sectors.py','research/sector_stock_momentum/ticker_aliases.py'],
  'problem':'Available liquid non-S&P pool is incomplete, especially dead firms after 2018; sectors and security identities use partial reconstruction/heuristics.',
  'required_action':'Report coverage and survivor/identity limitations. Missing-terminal stress on present names cannot measure omitted-firm survivorship bias.'},
 {'id':'RSC-07','severity':'P1','status':'PENDING_ROOT_FIX','classification':'VERIFIED_BY_COUNTEREXAMPLE',
  'files':['research/sector_stock_momentum/ml2_run.py'],
  'problem':'Generic delisted-in-month fallback still used next-close entry even with an observed entry open.',
  'evidence':'Actual next-open 90, next-close 110, last trade 121: old +10% versus correct modeled terminal return +34.4444%.',
  'required_action':'Rebase known last-trade terminal wealth to actual entry open. Keep unresolved/source-gap status unknown. Final training must follow this fix.'},
]

counterexamples = load('root_scope_counterexamples.json')
matrix = next((x for x in (counterexamples or {}).get('checks', []) if x['name']=='open_price_status_availability_matrix'), {})
if matrix.get('status') == 'PASS':
    findings[-1]['status'] = 'FIX_VERIFIED_FINAL_REPLAY_TRACKED_SEPARATELY'
    findings[-1]['evidence'] += ' Repaired 5-status x 4-open-availability matrix passed independently.'

out = {'status':'PARTIAL_SOURCE_CERTIFICATION_AND_MISSING_DIAGNOSTICS; FINAL_REPLAY_STATUS_RECORDED_PER_ENTRY',
       'reviewer':'legacy_ml_writer (independent of root-owned code changes)',
       'generated_utc':datetime.now(timezone.utc).isoformat(),
       'scope':'All top-level Python files in R2 research/sector_stock_momentum; delegated files recorded as coverage pointers; root-owned files reviewed read-only.',
       'source_edits_by_this_review':[], 'network_or_data_acquisition':False,
       'coverage_counts':{'all_top_level_python':len(records),'delegated':sum(r['role']=='delegated_scope' for r in records),
                          'root_scope':sum(r['role']!='delegated_scope' for r in records),
                          'roles':dict(Counter(r['role'] for r in records))},
       'contract_and_specs':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
          [AUD/'CONTRACT.txt', SRC/'FROZEN_SPEC.md', SRC/'ML2_SPEC.md', SRC/'WINNERS_SPEC.md']},
       'independent_executed_checks':load('root_patch_review.json'),
       'independent_open_counterexamples':counterexamples,
       'independent_final_ml2_statistics':load('root_ml2_final_stat_review.json'),
       'root_observed_test_records':{'ledger':load('root_ledger_gate.json'),'features':load('root_feature_gate.json'),
                                     'cfo_cached_truncation':load('root_cfo_truncation.json'),
                                     'daily_missing_quotes':load('root_daily_gap_gate.json')},
       'execution_registry_note':'Exit 0 records prove that command completed at its stored hash. They do not close newly discovered bugs or prove latest pending rerun complete. Failed initial additional suite remains recorded; root_additional_retry.log separately shows five checks OK.',
       'findings':findings,'files':records,
       'not_claimed':['All raw data accurate or licensed for any future use','All downloader APIs currently work','All historical members/sectors/identities independently certified',
                      'All frozen diagnostics implemented','All daily risk paths reconstructible','Current historical replays are fresh prospective tests'],
       'excluded_from_this_bounded_inventory':'Shell scheduling wrappers and other research directories are handled by root-wide coverage; no dashboard/R1/original files touched.',
       'workflow':'frozen source/cache -> per-file code review + independent counterexamples -> actual run records -> pending root fixes and source gaps -> final matched-period comparison'}
(AUD/'root_scope_review.json').write_text(json.dumps(out, indent=2, ensure_ascii=False))
print(json.dumps(out['coverage_counts'], indent=2))
print('Wrote audit_v2/root_scope_review.json; all files explicitly classified.')
