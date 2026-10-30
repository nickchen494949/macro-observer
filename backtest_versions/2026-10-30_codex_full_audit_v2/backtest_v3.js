#!/usr/bin/env node
/**
 * 🔭 Backtest V3 — Event-based scoring + Baseline comparison
 *
 * Changes from V2:
 * 1. Score by ALERT EVENTS, not individual months
 *    - Consecutive red/yellow months = 1 alert
 *    - Measure: did it hit an event? how early? how long did alert last?
 * 2. Compare against single-indicator baselines
 * 3. No threshold tuning — use current production thresholds
 */

const fs = require('fs');
const path = require('path');
const { evaluateDiagnostics } = require('./macro_engine');

const FRED_DIR = path.join(__dirname, 'data', 'fred');

// ============================================
// GROUND TRUTH EVENTS (with names)
// ============================================
const EVENTS = {
  recession: [
    { name: 'GFC', start: '2007-12-01', end: '2009-06-01' },
    { name: 'COVID', start: '2020-02-01', end: '2020-04-01' },
  ],
  inflation: [
    { name: 'Post-COVID Inflation', start: '2021-04-01', end: '2026-12-01' },
  ],
  credit: [
    { name: 'GFC Credit Crisis', start: '2008-09-01', end: '2009-06-01' },
    { name: 'COVID Credit', start: '2020-03-01', end: '2020-05-01' },
    { name: 'SVB', start: '2023-03-01', end: '2023-04-01' },
  ],
};

// ============================================
// DATA (same transforms as V2, condensed)
// ============================================
function loadAllFred(dir = FRED_DIR, requirePit = false) {
  const store = {};
  for (const f of fs.readdirSync(dir).filter(f => f.endsWith('.json')).sort()) {
    const d = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));
    if (!d.id || (!Array.isArray(d.values) && !Array.isArray(d.records))) continue; // metadata files
    if (requirePit && (d.schemaVersion !== 'pit-observations-v1' || !Array.isArray(d.records) || !d.source)) {
      throw new Error(`PIT source/version records missing: ${f}`);
    }
    const values = d.records || d.values;
    if (!d.records && values.some((x,i)=>i && x[0]<=values[i-1][0])) throw new Error(`Unsorted/duplicate observation dates: ${f}`);
    for (const x of values) {
      if (Array.isArray(x)) {
        if (!/^\d{4}-\d{2}-\d{2}$/.test(x[0]) || !Number.isFinite(x[1])) throw new Error(`Invalid observation: ${f}`);
      } else if (!/^\d{4}-\d{2}-\d{2}$/.test(x.observationDate) || !Number.isFinite(x.value)
                 || !Number.isFinite(Date.parse(x.availableAt)) || Date.parse(x.availableAt) < Date.parse(x.observationDate)) {
        throw new Error(`Invalid vintage record: ${f}`);
      }
    }
    store[d.id] = values;
  }
  return store;
}

function valuesAsOf(values, asOf) {
  if (!values.length || Array.isArray(values[0])) return values.filter(x => x[0] <= asOf);
  const latest = new Map(), cutoff = Date.parse(asOf + 'T23:59:59.999Z');
  for (const x of values) {
    if (x.observationDate > asOf || Date.parse(x.availableAt) > cutoff) continue;
    const prev = latest.get(x.observationDate);
    if (!prev || Date.parse(prev.availableAt) < Date.parse(x.availableAt)) latest.set(x.observationDate, x);
  }
  return [...latest.values()].map(x => [x.observationDate, x.value]).sort((a,b) => a[0].localeCompare(b[0]));
}
function getLatestValue(values, asOf) {
  const v = valuesAsOf(values, asOf);
  if (!v.length) return { value: null, date: null };
  const [date, value] = v[v.length - 1];
  return { value, date };
}
function computeYoY(values, asOf) {
  const v = valuesAsOf(values, asOf), last = v.at(-1);
  if (!last) return {value: null, date: null};
  const target = new Date(last[0] + 'T00:00:00Z'); target.setUTCFullYear(target.getUTCFullYear() - 1);
  // A nearby value is not a year-ago value: require the same calendar month one year earlier.
  const month = target.toISOString().slice(0, 7);
  const prior = v.filter(x => x[0].slice(0, 7) === month).at(-1);
  return { value: prior && prior[1] !== 0 ? (last[1] / prior[1] - 1) * 100 : null, date: last[0] };
}
function computeMoMAbs(values, asOf) {
  let latest = null, latestDate = null, prev = null;
  for (const [date, val] of valuesAsOf(values, asOf)) { prev = latest; latest = val; latestDate = date; }
  if (latest !== null && prev !== null) return { value: latest - prev, date: latestDate };
  return { value: null, date: latestDate };
}
function computeMoMPct(values, asOf) {
  let latest = null, latestDate = null, prev = null;
  for (const [date, val] of valuesAsOf(values, asOf)) { prev = latest; latest = val; latestDate = date; }
  if (latest !== null && prev !== null && prev !== 0) return { value: ((latest / prev) - 1) * 100, date: latestDate };
  return { value: null, date: latestDate };
}
function computeAnnualizedNM(values, asOf, nMonths) {
  let candidates = [];
  for (const [date, val] of valuesAsOf(values, asOf)) { candidates.push([date, val]); }
  if (candidates.length < nMonths + 1) return { value: null, date: null };
  const end = candidates[candidates.length - 1], start = candidates[candidates.length - 1 - nMonths];
  if (start[1] === 0) return { value: null, date: end[0] };
  return { value: (Math.pow(end[1] / start[1], 12 / nMonths) - 1) * 100, date: end[0] };
}

const INDICATOR_MAP = [
  { id: 'initial_claims', series: 'ICSA', transform: 'div1000', label: 'Initial Claims' },
  { id: 'continuing_claims', series: 'CCSA', transform: 'div1000', label: 'Continuing Claims' },
  { id: 'agg_weekly_hours_yoy', series: 'AWHAE', transform: 'yoy', label: 'Agg Weekly Hours (YoY)' },
  { id: 'mfg_pns_avg_weekly_hrs', series: 'AWHMAN', transform: 'raw', label: 'Mfg Avg Weekly Hrs' },
  { id: 'real_income_yoy', series: 'CES0500000017', transform: 'yoy', label: 'Nominal aggregate weekly payrolls YoY (income proxy)' },
  { id: 'real_pce_mom', series: 'DPCERAM1M225NBEA', transform: 'raw', label: 'Real PCE (MoM)' },
  { id: 'retail_sales_control_mom', series: 'MARTSMPCSM44X72USS', transform: 'raw', label: 'Headline retail/food services MoM (proxy, not control group)' },
  { id: 'industrial_production_yoy', series: 'INDPRO', transform: 'yoy', label: 'Industrial Production (YoY)' },
  { id: 'core_capex_orders_yoy_nsa', series: 'NEWORDER', transform: 'yoy', label: 'Core Capex Orders (YoY)' },
  { id: 'consumer_sentiment', series: 'UMCSENT', transform: 'raw', label: 'Consumer Sentiment' },
  { id: 'atlanta_fed_gdpnow', series: 'GDPNOW', transform: 'raw', label: 'GDPNow' },
  { id: 'private_payrolls_mom', series: 'USPRIV', transform: 'mom_abs_k', label: 'Private Payrolls (MoM)' },
  { id: 'nfp_mom', series: 'PAYEMS', transform: 'mom_abs_k', label: 'Nonfarm Payrolls (MoM)' },
  { id: 'quits_rate', series: 'JTSQUR', transform: 'raw', label: 'Quits Rate' },
  { id: 'sahm_rule', series: 'SAHMREALTIME', transform: 'raw', label: 'Sahm Rule' },
  { id: 'unemployment', series: 'UNRATE', transform: 'raw', label: 'Unemployment' },
  { id: 'core_pce_yoy', series: 'PCEPILFE', transform: 'yoy', label: 'Core PCE (YoY)' },
  { id: 'core_pce_1m_ann', series: 'PCEPILFE', transform: 'ann_1m', label: 'Core PCE 1M Ann' },
  { id: 'core_pce_3m_ann', series: 'PCEPILFE', transform: 'ann_3m', label: 'Core PCE 3M Ann' },
  { id: 'core_pce_6m_ann', series: 'PCEPILFE', transform: 'ann_6m', label: 'Core PCE 6M Ann' },
  { id: 'median_cpi_1m_ann', series: 'MEDCPIM158SFRBCLE', transform: 'raw', label: 'Median CPI 1M Ann' },
  { id: 'median_cpi_yoy', series: 'MEDCPIM159SFRBCLE', transform: 'raw', label: 'Median CPI YoY' },
  { id: 'trimmed_cpi_1m_ann', series: 'TRMMEANCPIM158SFRBCLE', transform: 'raw', label: '16% Trimmed CPI 1M Ann' },
  { id: 'trimmed_cpi_yoy', series: 'TRMMEANCPIM159SFRBCLE', transform: 'raw', label: '16% Trimmed CPI YoY' },
  { id: 'import_prices_yoy', series: 'IR', transform: 'yoy', label: 'Import Prices (YoY)' },
  { id: 'ppi_final_demand_yoy', series: 'PPIFIS', transform: 'yoy', label: 'PPI Final Demand (YoY)' },
  { id: 'cpi_core_goods_yoy', series: 'CUSR0000SACL1E', transform: 'yoy', label: 'CPI Core Goods (YoY)' },
  { id: 'cpi_housing_yoy', series: 'CUSR0000SAH1', transform: 'yoy', label: 'CPI Housing (YoY)' },
  { id: 'avg_hourly_wage_yoy', series: 'CES0500000003', transform: 'yoy', label: 'Avg Hourly Wage (YoY)' },
  { id: 'unit_labor_cost_yoy', series: 'ULCNFB', transform: 'yoy', label: 'Unit Labor Cost (YoY)' },
  { id: '10y_breakeven_inflation', series: 'T10YIE', transform: 'raw', label: '10Y Breakeven Inflation' },
  { id: '5y5y_inflation_forward', series: 'T5YIFR', transform: 'raw', label: '5Y5Y Inflation Forward' },
  { id: 'sloos_ci_standards', series: 'DRTSCILM', transform: 'raw', label: 'SLOOS C&I Standards' },
  { id: 'sloos_small_biz_standards', series: 'DRTSCIS', transform: 'raw', label: 'SLOOS Small Biz Standards' },
  { id: 'sloos_ci_demand', series: 'DRSDCILM', transform: 'raw', label: 'SLOOS C&I Demand' },
  { id: '-_hy-ig', series: '_HY_IG_SPREAD', transform: 'raw', label: 'HY-IG Spread' },
  { id: 'ci_loans_yoy', series: 'BUSLOANS', transform: 'yoy', label: 'C&I Loans (YoY)' },
  { id: 'consumer_loans_yoy', series: 'CONSUMER', transform: 'yoy', label: 'Consumer Loans (YoY)' },
  { id: 'chicago_fed_nfci', series: 'NFCI', transform: 'raw', label: 'Chicago Fed NFCI' },
  { id: 'cc_delinquency_rate', series: 'DRCCLACBS', transform: 'raw', label: 'CC Delinquency Rate' },
  { id: 'mortgage_delinquency_rate', series: 'DRSFRMACBS', transform: 'raw', label: 'Mortgage Delinquency Rate' },
  { id: 'charge_offs', series: 'CORCCACBS', transform: 'raw', label: 'Charge-Off Rate' },
  { id: '10y_acm_term_premium_model_est', series: 'THREEFYTP10', transform: 'raw', label: '10Y ACM Term Premium' },
  { id: 'tip_yield_10y_tips', series: 'DFII10', transform: 'raw', label: '10Y TIPS Yield' },
  { id: 'federal_interest_exp_gdp', series: '_INTEREST_GDP', transform: 'raw', label: 'Fed Interest/GDP' },
  { id: 'federal_interest_exp_receipts', series: '_INTEREST_RECEIPTS', transform: 'raw', label: 'Fed Interest/Receipts' },
  { id: 'sofr-iorb', series: '_SOFR_IORB', transform: 'raw', label: 'SOFR-IORB Spread' },
  { id: 'bank_reserves', series: 'WRESBAL', transform: 'div1000', label: 'Bank Reserves ($T)' },
  { id: 'rrp_overnight', series: 'RRPONTSYD', transform: 'raw', label: 'RRP Overnight ($B)' },
  { id: 'tga_balance', series: 'WTREGEN', transform: 'div1000', label: 'TGA Balance ($B)' },
  { id: '10y', series: 'DGS10', transform: 'raw', label: '10Y Yield' },
  { id: '03m-10y_spread', series: 'T10Y3M', transform: 'raw_bp', label: '3M-10Y Spread' },
];

function buildIndicatorsAsOf(asOf, fredStore) {
  const results = [];
  const hyL = getLatestValue(fredStore['BAMLH0A0HYM2']||[], asOf);
  const igL = getLatestValue(fredStore['BAMLC0A0CM']||[], asOf);
  let hyIg = (hyL.value !== null && igL.value !== null) ? (hyL.value - igL.value) * 100 : null;
  const sofrL = getLatestValue(fredStore['SOFR']||[], asOf);
  const iorbL = getLatestValue(fredStore['IORB']||[], asOf);
  let sofrIorb = (sofrL.value !== null && iorbL.value !== null) ? (sofrL.value - iorbL.value) * 100 : null;
  const intL = getLatestValue(fredStore['A091RC1Q027SBEA']||[], asOf);
  const gdpL = getLatestValue(fredStore['GDP']||[], asOf);
  const recL = getLatestValue(fredStore['W006RC1Q027SBEA']||[], asOf);
  let intGdp = (intL.value && gdpL.value) ? (intL.value/gdpL.value)*100 : null;
  let intRec = (intL.value && recL.value) ? (intL.value/recL.value)*100 : null;

  for (const ind of INDICATOR_MAP) {
    let current = null, lastObsDate = null;
    if (ind.series === '_HY_IG_SPREAD') { current = hyIg; lastObsDate = hyL.date; }
    else if (ind.series === '_SOFR_IORB') { current = sofrIorb; lastObsDate = sofrL.date; }
    else if (ind.series === '_INTEREST_GDP') { current = intGdp; lastObsDate = intL.date; }
    else if (ind.series === '_INTEREST_RECEIPTS') { current = intRec; lastObsDate = intL.date; }
    else {
      const vals = fredStore[ind.series]; if (!vals || !vals.length) continue;
      switch(ind.transform) {
        case 'yoy': { const r = computeYoY(vals, asOf); current = r.value; lastObsDate = r.date; break; }
        case 'mom_abs_k': { const r = computeMoMAbs(vals, asOf); current = r.value; lastObsDate = r.date; break; }
        case 'mom_pct': { const r = computeMoMPct(vals, asOf); current = r.value; lastObsDate = r.date; break; }
        case 'ann_1m': { const r = computeAnnualizedNM(vals, asOf, 1); current = r.value; lastObsDate = r.date; break; }
        case 'ann_3m': { const r = computeAnnualizedNM(vals, asOf, 3); current = r.value; lastObsDate = r.date; break; }
        case 'ann_6m': { const r = computeAnnualizedNM(vals, asOf, 6); current = r.value; lastObsDate = r.date; break; }
        case 'div1000': { const r = getLatestValue(vals, asOf); current = r.value !== null ? r.value/1000 : null; lastObsDate = r.date; break; }
        case 'raw_bp': { const r = getLatestValue(vals, asOf); current = r.value !== null ? r.value*100 : null; lastObsDate = r.date; break; }
        default: { const r = getLatestValue(vals, asOf); current = r.value; lastObsDate = r.date; break; }
      }
    }
    results.push({ id: ind.id, label: ind.label, current, lastObsDate, daysSinceObs: lastObsDate ? Math.round((new Date(asOf)-new Date(lastObsDate))/86400000) : 0 });
  }
  return results;
}

// ============================================
// EVENT-BASED SCORING
// ============================================
function extractAlerts(dates, signalFn) {
  const alerts = [], signals = dates.map((d,i) => signalFn(i));
  let start = null;
  for (let i = 0; i <= dates.length; i++) {
    const on = i < dates.length && signals[i] === true;
    if (on && start === null) start = i;
    if (!on && start !== null) {
      alerts.push({startIdx:start, endIdx:i-1, startDate:dates[start], endDate:dates[i-1], duration:i-start});
      start = null;
    }
  }
  alerts.signals = signals;
  return alerts;
}
function monthDiff(a, b) {
  return (Number(b.slice(0,4)) - Number(a.slice(0,4))) * 12 + Number(b.slice(5,7)) - Number(a.slice(5,7));
}
function scoreAlerts(alerts, events, allDates) {
  const result = {hits:[], misses:[], falseAlarms:[], unavailableEvents:[], overlappingAlerts:[]};
  const known = allDates.filter((d,i) => !alerts.signals || typeof alerts.signals[i] === 'boolean');
  const inWindow = (d,e) => d <= e.end && monthDiff(d,e.start) <= 6;
  const used = new Set();
  for (const ev of events) {
    const window = allDates.filter(d => inWindow(d,ev));
    if (!window.length || window.some(d => !known.includes(d))) {
      result.unavailableEvents.push({event:ev.name, reason:'incomplete observations in event/lead window'});
      continue;
    }
    const candidates = alerts.map((al,i) => ({al,i})).filter(({al,i}) => !used.has(i) && inWindow(al.startDate,ev));
    candidates.sort((a,b) => a.al.startDate.localeCompare(b.al.startDate));
    if (candidates.length) {
      const {al,i} = candidates[0]; used.add(i);
      result.hits.push({event:ev.name,eventStart:ev.start,alertStart:al.startDate,leadMonths:monthDiff(al.startDate,ev.start),alertDuration:al.duration});
    } else result.misses.push({event:ev.name,eventStart:ev.start});
  }
  for (let i=0;i<alerts.length;i++) {
    if (used.has(i)) continue;
    const al=alerts[i];
    if (allDates.some(d => d>=al.startDate && d<=al.endDate && events.some(e=>inWindow(d,e)))) result.overlappingAlerts.push(al);
    else result.falseAlarms.push(al);
  }
  const on = allDates.filter((d,i) => alerts.signals ? alerts.signals[i] === true : alerts.some(a=>d>=a.startDate&&d<=a.endDate));
  const outside = known.filter(d=>!events.some(e=>inWindow(d,e)));
  result.coverage={knownMonths:known.length,totalMonths:allDates.length,alertMonths:on.length,
    alertTimeShare:known.length ? on.length/known.length : null,
    outsideEventFalseAlarmMonths:on.filter(d=>outside.includes(d)).length,
    outsideEventFalseAlarmRate:outside.length ? on.filter(d=>outside.includes(d)).length/outside.length : null};
  result.rule='One onset per event, each alert used once; onset must be no earlier than 6 months before event. Unknown coverage is not a miss.';
  return result;
}

// ============================================
// BASELINES
// ============================================
function baselineSignal(fredStore, allDates, seriesId, transform, threshold, direction) {
  // direction: 'above' = signal when value > threshold, 'below' = value < threshold
  return (idx) => {
    const asOf = allDates[idx];
    const vals = fredStore[seriesId];
    if (!vals) return null;
    let val;
    if (transform === 'yoy') val = computeYoY(vals, asOf).value;
    else if (transform === 'ann_3m') val = computeAnnualizedNM(vals, asOf, 3).value;
    else if (transform === 'ann_6m') val = computeAnnualizedNM(vals, asOf, 6).value;
    else if (transform === 'raw_bp') { const r = getLatestValue(vals, asOf); val = r.value !== null ? r.value * 100 : null; }
    else if (transform === 'div1000') { const r = getLatestValue(vals, asOf); val = r.value === null ? null : r.value / 1000; }
    else val = getLatestValue(vals, asOf).value;
    if (val === null) return null;
    return direction === 'above' ? val > threshold : val < threshold;
  };
}

function baselineSpreadSignal(fredStore, allDates, seriesA, seriesB, threshold, direction) {
  return (idx) => {
    const asOf = allDates[idx];
    const vA = getLatestValue(fredStore[seriesA]||[], asOf).value;
    const vB = getLatestValue(fredStore[seriesB]||[], asOf).value;
    if (vA === null || vB === null) return null;
    const spread = (vA - vB) * 100; // bp
    return direction === 'above' ? spread > threshold : spread < threshold;
  };
}

// ============================================
// MAIN
// ============================================
function main(argv = process.argv.slice(2)) {
  const retrospective = argv.includes('--revised-history');
  const vintageArg = argv.find(x=>x.startsWith('--vintage-dir='));
  if (!retrospective && !vintageArg) throw new Error('BLOCK: no historical publication/vintage records. Supply --vintage-dir=PATH, or explicitly choose --revised-history for a retrospective replay only.');
  const store = loadAllFred(vintageArg ? vintageArg.split('=').slice(1).join('=') : FRED_DIR, !retrospective);
  const dates=[];
  for(let y=2006;y<=2026;y++) for(let m=1;m<=(y===2026?6:12);m++) dates.push(new Date(Date.UTC(y,m,0)).toISOString().slice(0,10));
  const hist=dates.map(d=>evaluateDiagnostics(buildIndicatorsAsOf(d,store))); // exceptions must fail the run
  const signal=(name,threshold)=>(i)=>{
    const x=hist[i]?.[name]?.stages?.[0]?.score;
    return Number.isFinite(x) ? x>=threshold : null;
  };
  const groups={
    recession:[['Engine',signal('recession',.5)],['Claims > 250k',baselineSignal(store,dates,'ICSA','div1000',250,'above')],
      ['Yield curve < 0bp',baselineSignal(store,dates,'T10Y3M','raw_bp',0,'below')],['Sahm >= 0.50',baselineSignal(store,dates,'SAHMREALTIME','raw',.5,'above')],
      ['NFCI > 0',baselineSignal(store,dates,'NFCI','raw',0,'above')]],
    inflation:[['Engine',signal('inflation',.7)],['Core PCE > 3%',baselineSignal(store,dates,'PCEPILFE','yoy',3,'above')],
      ['Core PCE 3M ann > 3.5%',baselineSignal(store,dates,'PCEPILFE','ann_3m',3.5,'above')],
      ['Core PCE 6M ann > 3%',baselineSignal(store,dates,'PCEPILFE','ann_6m',3,'above')],
      ['PPI YoY > 3%',baselineSignal(store,dates,'PPIFIS','yoy',3,'above')],
      ['10Y breakeven > 2.5%',baselineSignal(store,dates,'T10YIE','raw',2.5,'above')]],
    credit:[['Engine',signal('credit',.5)],['HY-IG > 400bp',baselineSpreadSignal(store,dates,'BAMLH0A0HYM2','BAMLC0A0CM',400,'above')],['NFCI > 0.5',baselineSignal(store,dates,'NFCI','raw',.5,'above')],
      ['SLOOS C&I > 20%',baselineSignal(store,dates,'DRTSCILM','raw',20,'above')]]
  };
  const out={version:'Codex audited and modified',mode:retrospective?'REVISED_HISTORY_NOT_POINT_IN_TIME':'SOURCE_DECLARED_VINTAGE_RECORDS',
    inputProvenanceVerified: false, predictiveSkillValidated:false, first:dates[0],last:dates.at(-1),months:dates.length,
    limitations:['Event definitions are inherited research labels, not independently certified ground truth.','Headline retail and nominal payrolls are explicitly labelled proxies.'],standalone:{},commonSampleComparisons:{}};
  for(const [group,models] of Object.entries(groups)) {
    out.standalone[group]=scoreAlerts(extractAlerts(dates,models[0][1]),EVENTS[group],dates);
    const matrix=models.map(([n,f])=>dates.map((d,i)=>f(i)));
    out.commonSampleComparisons[group]={};
    models.forEach(([name],j)=>{
      const f=i=>matrix.every(row=>typeof row[i]==='boolean')?matrix[j][i]:null;
      out.commonSampleComparisons[group][name]=scoreAlerts(extractAlerts(dates,f),EVENTS[group],dates);
    });
  }
  const dest=path.join(__dirname,'audit','macro_replay.json');fs.mkdirSync(path.dirname(dest),{recursive:true});
  fs.writeFileSync(dest,JSON.stringify(out,null,2));
  console.log(JSON.stringify({mode:out.mode,months:out.months,output:dest,commonSampleComparisons:out.commonSampleComparisons},null,2));
  return out;
}
module.exports={main,loadAllFred,valuesAsOf,getLatestValue,computeYoY,computeMoMAbs,computeMoMPct,computeAnnualizedNM,
  buildIndicatorsAsOf,extractAlerts,scoreAlerts,monthDiff,baselineSignal,baselineSpreadSignal,INDICATOR_MAP,EVENTS};
if(require.main===module) {try {main();} catch(e) {console.error(e.stack);process.exitCode=2;}}
