#!/usr/bin/env node
/**
 * 🔭 Full Historical Backtest — macro_engine.js
 * 
 * Walk-forward test: at each month-end from 2006-01 to 2026-06,
 * reconstruct all indicator values as-of that date,
 * run evaluateDiagnostics(), and record what the engine would have said.
 * 
 * Then compare against known NBER recession dates, inflation regimes,
 * credit events, and liquidity crises.
 */

const fs = require('fs');
const path = require('path');
const { evaluateDiagnostics } = require('./macro_engine');

const FRED_DIR = path.join(__dirname, 'data', 'fred');
const YAHOO_DIR = path.join(__dirname, 'data', 'yahoo');
const VALUATION_DIR = path.join(__dirname, 'data', 'valuation');

// ============================================
// GROUND TRUTH EVENTS
// ============================================
const NBER_RECESSIONS = [
  // [start, end]
  ['2007-12-01', '2009-06-01'],
  ['2020-02-01', '2020-04-01'],
];

const INFLATION_REGIMES = [
  // periods where Core PCE YoY > 3%
  ['2021-04-01', '2026-12-01'], // post-COVID inflation
];

const CREDIT_STRESS_EVENTS = [
  // HY-IG > 500bp or NFCI > 0.5
  ['2008-09-01', '2009-06-01'], // GFC
  ['2020-03-01', '2020-05-01'], // COVID
];

const LIQUIDITY_EVENTS = [
  ['2019-09-01', '2019-10-01'], // Repo crisis
  ['2023-03-01', '2023-04-01'], // SVB
];

// ============================================
// DATA LOADING
// ============================================
function loadAllFred() {
  const store = {};
  for (const f of fs.readdirSync(FRED_DIR).filter(f => f.endsWith('.json'))) {
    try {
      const d = JSON.parse(fs.readFileSync(path.join(FRED_DIR, f)));
      store[d.id] = d.values; // [[date, value], ...]
    } catch(e) {}
  }
  return store;
}

function loadValuation() {
  const store = {};
  if (!fs.existsSync(VALUATION_DIR)) return store;
  for (const f of fs.readdirSync(VALUATION_DIR).filter(f => f.endsWith('.json'))) {
    try {
      const d = JSON.parse(fs.readFileSync(path.join(VALUATION_DIR, f)));
      if (d.values) store[d.id || f.replace('.json','')] = d.values;
    } catch(e) {}
  }
  return store;
}

// ============================================
// TRANSFORMS (same as server.js)
// ============================================
function computeYoY(values, asOf) {
  // Find the latest value on or before asOf
  let latest = null, latestDate = null;
  let yearAgo = null;
  const targetYearAgo = new Date(asOf);
  targetYearAgo.setFullYear(targetYearAgo.getFullYear() - 1);
  const yStr = targetYearAgo.toISOString().split('T')[0];
  
  for (const [date, val] of values) {
    if (date > asOf) break;
    latest = val; latestDate = date;
  }
  // find value closest to 1 year before latestDate
  if (latestDate) {
    const t = new Date(latestDate);
    t.setFullYear(t.getFullYear() - 1);
    const tStr = t.toISOString().split('T')[0];
    let bestDist = Infinity;
    for (const [date, val] of values) {
      const dist = Math.abs(new Date(date) - t);
      if (dist < bestDist) { bestDist = dist; yearAgo = val; }
      if (date > latestDate) break;
    }
  }
  if (latest !== null && yearAgo !== null && yearAgo !== 0) {
    return { value: ((latest / yearAgo) - 1) * 100, date: latestDate };
  }
  return { value: null, date: latestDate };
}

function computeMoMAbs(values, asOf) {
  let latest = null, latestDate = null, prev = null;
  for (const [date, val] of values) {
    if (date > asOf) break;
    prev = latest;
    latest = val; latestDate = date;
  }
  if (latest !== null && prev !== null) {
    return { value: latest - prev, date: latestDate };
  }
  return { value: null, date: latestDate };
}

function computeMoMPct(values, asOf) {
  let latest = null, latestDate = null, prev = null;
  for (const [date, val] of values) {
    if (date > asOf) break;
    prev = latest;
    latest = val; latestDate = date;
  }
  if (latest !== null && prev !== null && prev !== 0) {
    return { value: ((latest / prev) - 1) * 100, date: latestDate };
  }
  return { value: null, date: latestDate };
}

function getLatestValue(values, asOf) {
  let latest = null, latestDate = null;
  for (const [date, val] of values) {
    if (date > asOf) break;
    latest = val; latestDate = date;
  }
  return { value: latest, date: latestDate };
}

function computeAnnualizedNM(values, asOf, nMonths) {
  // Get last N months of index data, compute annualized rate
  let candidates = [];
  for (const [date, val] of values) {
    if (date > asOf) break;
    candidates.push([date, val]);
  }
  if (candidates.length < nMonths + 1) return { value: null, date: null };
  const end = candidates[candidates.length - 1];
  const start = candidates[candidates.length - 1 - nMonths];
  if (start[1] === 0) return { value: null, date: end[0] };
  const ratio = end[1] / start[1];
  const ann = (Math.pow(ratio, 12 / nMonths) - 1) * 100;
  return { value: ann, date: end[0] };
}

// ============================================
// INDICATOR BUILDER (as-of a given date)
// ============================================

// Map of indicator ID -> how to compute it from raw FRED series
const INDICATOR_MAP = [
  // === RECESSION ===
  { id: 'initial_claims', series: 'ICSA', transform: 'raw', label: 'Initial Claims' },
  { id: 'continuing_claims', series: 'CCSA', transform: 'raw', label: 'Continuing Claims' },
  { id: 'agg_weekly_hours_yoy', series: 'AWHAE', transform: 'yoy', label: 'Agg Weekly Hours (YoY)' },
  { id: 'mfg_pns_avg_weekly_hrs', series: 'AWHMAN', transform: 'raw', label: 'Mfg Avg Weekly Hrs' },
  { id: 'real_income_yoy', series: 'CES0500000017', transform: 'yoy', label: 'Agg Weekly Payrolls (YoY)' },
  { id: 'real_pce_mom', series: 'DPCERAM1M225NBEA', transform: 'raw', label: 'Real PCE (MoM)' },
  { id: 'retail_sales_control_mom', series: 'MARTSMPCSM44X72USS', transform: 'mom_pct', label: 'Retail Sales Control (MoM)' },
  { id: 'industrial_production_yoy', series: 'INDPRO', transform: 'yoy', label: 'Industrial Production (YoY)' },
  { id: 'core_capex_orders_yoy_nsa', series: 'NEWORDER', transform: 'yoy', label: 'Core Capex Orders (YoY)' },
  { id: 'consumer_sentiment', series: 'UMCSENT', transform: 'raw', label: 'Consumer Sentiment' },
  { id: 'atlanta_fed_gdpnow', series: 'GDPNOW', transform: 'raw', label: 'GDPNow' },
  { id: 'private_payrolls_mom', series: 'USPRIV', transform: 'mom_abs_k', label: 'Private Payrolls (MoM)' },
  { id: 'nfp_mom', series: 'PAYEMS', transform: 'mom_abs_k', label: 'Nonfarm Payrolls (MoM)' },
  { id: 'quits_rate', series: 'JTSQUR', transform: 'raw', label: 'Quits Rate' },
  { id: 'sahm_rule', series: 'SAHMREALTIME', transform: 'raw', label: 'Sahm Rule' },
  { id: 'unemployment', series: 'UNRATE', transform: 'raw', label: 'Unemployment' },
  
  // === INFLATION ===
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
  
  // === CREDIT ===
  { id: 'sloos_ci_standards', series: 'DRTSCILM', transform: 'raw', label: 'SLOOS C&I Standards' },
  { id: 'sloos_small_biz_standards', series: 'DRTSCIS', transform: 'raw', label: 'SLOOS Small Biz Standards' },
  { id: 'sloos_ci_demand', series: 'DRSDCILM', transform: 'raw', label: 'SLOOS C&I Demand' },
  { id: '-_hy-ig', series: '_HY_IG_SPREAD', transform: 'raw', label: 'HY-IG Spread' }, // computed
  { id: 'ci_loans_yoy', series: 'BUSLOANS', transform: 'yoy', label: 'C&I Loans (YoY)' },
  { id: 'consumer_loans_yoy', series: 'CONSUMER', transform: 'yoy', label: 'Consumer Loans (YoY)' },
  { id: 'chicago_fed_nfci', series: 'NFCI', transform: 'raw', label: 'Chicago Fed NFCI' },
  { id: 'cc_delinquency_rate', series: 'DRCCLACBS', transform: 'raw', label: 'CC Delinquency Rate' },
  { id: 'mortgage_delinquency_rate', series: 'DRSFRMACBS', transform: 'raw', label: 'Mortgage Delinquency Rate' },
  { id: 'charge_offs', series: 'CORCCACBS', transform: 'raw', label: 'Charge-Off Rate' },
  
  // === LONG-END ===
  { id: '10y_acm_term_premium_model_est', series: 'THREEFYTP10', transform: 'raw', label: '10Y ACM Term Premium' },
  { id: 'tip_yield_10y_tips', series: 'DFII10', transform: 'raw', label: '10Y TIPS Yield' },
  { id: 'federal_interest_exp_gdp', series: '_INTEREST_GDP', transform: 'raw', label: 'Fed Interest/GDP' }, // computed
  { id: 'federal_interest_exp_receipts', series: '_INTEREST_RECEIPTS', transform: 'raw', label: 'Fed Interest/Receipts' }, // computed
  
  // === LIQUIDITY ===
  { id: 'sofr-iorb', series: '_SOFR_IORB', transform: 'raw', label: 'SOFR-IORB Spread' }, // computed
  { id: 'bank_reserves', series: 'WRESBAL', transform: 'div1000', label: 'Bank Reserves ($T)' },
  { id: 'rrp_overnight', series: 'RRPONTSYD', transform: 'raw', label: 'RRP Overnight ($B)' },
  { id: 'tga_balance', series: 'WTREGEN', transform: 'div1000', label: 'TGA Balance ($B)' },
  
  // === RATES (for curve_steepness) ===
  { id: '10y', series: 'DGS10', transform: 'raw', label: '10Y Yield' },
  { id: '03m-10y_spread', series: 'T10Y3M', transform: 'raw_bp', label: '3M-10Y Spread' },
];

function buildIndicatorsAsOf(asOf, fredStore) {
  const results = [];
  
  // Pre-compute HY-IG spread
  const hyVals = fredStore['BAMLH0A0HYM2'] || [];
  const igVals = fredStore['BAMLC0A0CM'] || [];
  const hyLatest = getLatestValue(hyVals, asOf);
  const igLatest = getLatestValue(igVals, asOf);
  let hyIgSpread = null;
  if (hyLatest.value !== null && igLatest.value !== null) {
    hyIgSpread = (hyLatest.value - igLatest.value) * 100; // bp
  }
  
  // Pre-compute SOFR-IORB
  const sofrVals = fredStore['SOFR'] || [];
  const iorbVals = fredStore['IORB'] || [];
  const sofrLatest = getLatestValue(sofrVals, asOf);
  const iorbLatest = getLatestValue(iorbVals, asOf);
  let sofrIorb = null;
  if (sofrLatest.value !== null && iorbLatest.value !== null) {
    sofrIorb = (sofrLatest.value - iorbLatest.value) * 100; // bp
  }
  
  // Pre-compute Interest/GDP and Interest/Receipts
  const intVals = fredStore['A091RC1Q027SBEA'] || [];
  const gdpVals = fredStore['GDP'] || [];
  const recVals = fredStore['W006RC1Q027SBEA'] || [];
  const intLatest = getLatestValue(intVals, asOf);
  const gdpLatest = getLatestValue(gdpVals, asOf);
  const recLatest = getLatestValue(recVals, asOf);
  let intGdp = null, intRec = null;
  if (intLatest.value !== null && gdpLatest.value !== null && gdpLatest.value !== 0) {
    intGdp = (intLatest.value / gdpLatest.value) * 100;
  }
  if (intLatest.value !== null && recLatest.value !== null && recLatest.value !== 0) {
    intRec = (intLatest.value / recLatest.value) * 100;
  }
  
  for (const ind of INDICATOR_MAP) {
    let current = null, lastObsDate = null;
    
    // Handle computed series
    if (ind.series === '_HY_IG_SPREAD') {
      current = hyIgSpread;
      lastObsDate = hyLatest.date;
    } else if (ind.series === '_SOFR_IORB') {
      current = sofrIorb;
      lastObsDate = sofrLatest.date;
    } else if (ind.series === '_INTEREST_GDP') {
      current = intGdp;
      lastObsDate = intLatest.date;
    } else if (ind.series === '_INTEREST_RECEIPTS') {
      current = intRec;
      lastObsDate = intLatest.date;
    } else {
      const vals = fredStore[ind.series];
      if (!vals || vals.length === 0) continue;
      
      switch(ind.transform) {
        case 'yoy': {
          const r = computeYoY(vals, asOf);
          current = r.value; lastObsDate = r.date;
          break;
        }
        case 'mom_abs_k': {
          const r = computeMoMAbs(vals, asOf);
          current = r.value; lastObsDate = r.date;
          break;
        }
        case 'mom_pct': {
          const r = computeMoMPct(vals, asOf);
          current = r.value; lastObsDate = r.date;
          break;
        }
        case 'ann_1m': {
          const r = computeAnnualizedNM(vals, asOf, 1);
          current = r.value; lastObsDate = r.date;
          break;
        }
        case 'ann_3m': {
          const r = computeAnnualizedNM(vals, asOf, 3);
          current = r.value; lastObsDate = r.date;
          break;
        }
        case 'ann_6m': {
          const r = computeAnnualizedNM(vals, asOf, 6);
          current = r.value; lastObsDate = r.date;
          break;
        }
        case 'div1000': {
          const r = getLatestValue(vals, asOf);
          current = r.value !== null ? r.value / 1000 : null;
          lastObsDate = r.date;
          break;
        }
        case 'raw_bp': {
          const r = getLatestValue(vals, asOf);
          current = r.value !== null ? r.value * 100 : null;
          lastObsDate = r.date;
          break;
        }
        default: { // 'raw'
          const r = getLatestValue(vals, asOf);
          current = r.value; lastObsDate = r.date;
          break;
        }
      }
    }
    
    const daysSinceObs = lastObsDate ? Math.round((new Date(asOf) - new Date(lastObsDate)) / 86400000) : null;
    
    results.push({
      id: ind.id,
      label: ind.label,
      current,
      lastObsDate,
      daysSinceObs: daysSinceObs || 0,
    });
  }
  
  return results;
}

// ============================================
// GROUND TRUTH LOOKUP
// ============================================
function isInRange(date, ranges) {
  for (const [start, end] of ranges) {
    if (date >= start && date <= end) return true;
  }
  return false;
}

function getGroundTruth(dateStr) {
  return {
    inRecession: isInRange(dateStr, NBER_RECESSIONS),
    inflationHigh: isInRange(dateStr, INFLATION_REGIMES),
    creditStress: isInRange(dateStr, CREDIT_STRESS_EVENTS),
    liquidityStress: isInRange(dateStr, LIQUIDITY_EVENTS),
  };
}

// ============================================
// MAIN
// ============================================
function main() {
  console.log('📊 Loading data...');
  const fredStore = loadAllFred();
  console.log(`  FRED: ${Object.keys(fredStore).length} series loaded`);

  // Generate monthly test dates from 2006-01 to 2026-06
  const testDates = [];
  for (let y = 2006; y <= 2026; y++) {
    const maxM = (y === 2026) ? 6 : 12;
    for (let m = 1; m <= maxM; m++) {
      const d = new Date(y, m, 0); // last day of month
      testDates.push(d.toISOString().split('T')[0]);
    }
  }
  
  console.log(`  Testing ${testDates.length} monthly snapshots: ${testDates[0]} to ${testDates[testDates.length-1]}`);
  console.log('');

  const csvRows = ['date,gt_recession,gt_inflation,gt_credit,gt_liquidity,rec_pressure,rec_transmission,rec_damage,inf_level,inf_direction,inf_transmission,cre_pressure,cre_transmission,cre_damage,le_pressure,le_transmission,le_damage,liq_pressure,liq_transmission,liq_damage,stag_divergence,stag_constraint,stag_risk,val_pressure,val_transmission,val_damage'];
  
  // Track signal performance
  let stats = {
    recession: { tp: 0, fp: 0, tn: 0, fn: 0, leadMonths: [] },
    inflation: { tp: 0, fp: 0, tn: 0, fn: 0, leadMonths: [] },
    credit:    { tp: 0, fp: 0, tn: 0, fn: 0, leadMonths: [] },
  };

  for (const dateStr of testDates) {
    const indicators = buildIndicatorsAsOf(dateStr, fredStore);
    let diag;
    try {
      diag = evaluateDiagnostics(indicators);
    } catch(e) {
      console.error(`  ❌ ${dateStr}: ${e.message}`);
      continue;
    }
    
    const gt = getGroundTruth(dateStr);
    
    // Extract stage statuses (convert to numeric: green=0, yellow=1, red=2, unknown=-1)
    const statusNum = (s) => s === 'red' ? 2 : s === 'yellow' ? 1 : s === 'green' ? 0 : -1;
    
    const rec = diag.recession.stages.map(s => statusNum(s.status));
    const inf = diag.inflation.stages.map(s => statusNum(s.status));
    const cre = diag.credit.stages.map(s => statusNum(s.status));
    const le = diag.longEnd.stages.map(s => statusNum(s.status));
    const liq = diag.liquidity.stages.map(s => statusNum(s.status));
    const stag = diag.stagflation.stages.map(s => statusNum(s.status));
    const val = diag.valuation.stages.map(s => statusNum(s.status));
    
    csvRows.push([
      dateStr,
      gt.inRecession ? 1 : 0,
      gt.inflationHigh ? 1 : 0,
      gt.creditStress ? 1 : 0,
      gt.liquidityStress ? 1 : 0,
      ...rec, ...inf, ...cre, ...le, ...liq, ...stag, ...val
    ].join(','));
    
    // Recession signal: Pressure >= yellow (1)
    const recSignal = rec[0] >= 1; // Pressure is yellow or red
    if (recSignal && gt.inRecession) stats.recession.tp++;
    else if (recSignal && !gt.inRecession) stats.recession.fp++;
    else if (!recSignal && gt.inRecession) stats.recession.fn++;
    else stats.recession.tn++;
    
    // Inflation signal: Level >= red (2)
    const infSignal = inf[0] >= 2;
    if (infSignal && gt.inflationHigh) stats.inflation.tp++;
    else if (infSignal && !gt.inflationHigh) stats.inflation.fp++;
    else if (!infSignal && gt.inflationHigh) stats.inflation.fn++;
    else stats.inflation.tn++;
    
    // Credit signal: Pressure >= yellow (1)
    const creSignal = cre[0] >= 1;
    if (creSignal && gt.creditStress) stats.credit.tp++;
    else if (creSignal && !gt.creditStress) stats.credit.fp++;
    else if (!creSignal && gt.creditStress) stats.credit.fn++;
    else stats.credit.tn++;
  }
  
  // Write CSV
  const csvPath = path.join(__dirname, 'backtest_results.csv');
  fs.writeFileSync(csvPath, csvRows.join('\n'));
  console.log(`\n📁 CSV saved to: ${csvPath}`);
  
  // ============================================
  // SUMMARY REPORT
  // ============================================
  console.log('\n' + '='.repeat(70));
  console.log('📊 BACKTEST RESULTS — Full History (2006–2026)');
  console.log('='.repeat(70));
  
  for (const [name, s] of Object.entries(stats)) {
    const precision = s.tp + s.fp > 0 ? (s.tp / (s.tp + s.fp) * 100).toFixed(1) : 'N/A';
    const recall = s.tp + s.fn > 0 ? (s.tp / (s.tp + s.fn) * 100).toFixed(1) : 'N/A';
    const accuracy = ((s.tp + s.tn) / (s.tp + s.fp + s.tn + s.fn) * 100).toFixed(1);
    console.log(`\n  ${name.toUpperCase()}`);
    console.log(`    TP=${s.tp}  FP=${s.fp}  TN=${s.tn}  FN=${s.fn}`);
    console.log(`    Precision: ${precision}%  Recall: ${recall}%  Accuracy: ${accuracy}%`);
  }
  
  // ============================================
  // KEY EPISODES DETAIL
  // ============================================
  console.log('\n' + '='.repeat(70));
  console.log('🔍 KEY EPISODE ANALYSIS');
  console.log('='.repeat(70));
  
  const episodes = [
    { name: 'Pre-GFC (2007-06 to 2007-12)', dates: ['2007-06-30','2007-07-31','2007-08-31','2007-09-30','2007-10-31','2007-11-30','2007-12-31'] },
    { name: 'GFC Peak (2008-09 to 2009-03)', dates: ['2008-09-30','2008-10-31','2008-11-30','2008-12-31','2009-01-31','2009-02-28','2009-03-31'] },
    { name: 'COVID Crash (2020-01 to 2020-04)', dates: ['2020-01-31','2020-02-29','2020-03-31','2020-04-30'] },
    { name: 'Inflation Surge (2021-03 to 2022-06)', dates: ['2021-03-31','2021-06-30','2021-09-30','2021-12-31','2022-03-31','2022-06-30'] },
    { name: 'SVB Crisis (2023-02 to 2023-04)', dates: ['2023-02-28','2023-03-31','2023-04-30'] },
    { name: 'Current (2026-01 to 2026-06)', dates: ['2026-01-31','2026-03-31','2026-06-30'] },
  ];
  
  for (const ep of episodes) {
    console.log(`\n  📌 ${ep.name}`);
    for (const dateStr of ep.dates) {
      const indicators = buildIndicatorsAsOf(dateStr, fredStore);
      let diag;
      try {
        diag = evaluateDiagnostics(indicators);
      } catch(e) { continue; }
      
      const sLabel = (s) => s === 'red' ? '🔴' : s === 'yellow' ? '🟡' : s === 'green' ? '🟢' : '⚪';
      const gt = getGroundTruth(dateStr);
      const gtStr = [gt.inRecession ? 'REC' : '', gt.inflationHigh ? 'INF' : '', gt.creditStress ? 'CRE' : ''].filter(Boolean).join('+') || '—';
      
      const r = diag.recession.stages;
      const i = diag.inflation.stages;
      const c = diag.credit.stages;
      
      console.log(`    ${dateStr}  GT:[${gtStr}]  Rec: ${sLabel(r[0].status)}${sLabel(r[1].status)}${sLabel(r[2].status)}  Inf: ${sLabel(i[0].status)}${sLabel(i[1].status)}${sLabel(i[2].status)}  Cre: ${sLabel(c[0].status)}${sLabel(c[1].status)}${sLabel(c[2].status)}`);
    }
  }
  
  console.log('\n' + '='.repeat(70));
  console.log('✅ Backtest complete.');
}

main();
