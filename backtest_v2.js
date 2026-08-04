#!/usr/bin/env node
/**
 * 🔭 Backtest V2 — Proper methodology
 * 
 * Fixes from V1:
 * 1. Two label modes: NOWCAST (are we in it?) vs FORECAST (will it happen in 6m?)
 * 2. Train/Test split: 2006–2018 (train), 2019–2026 (test)
 * 3. Grid search on train, validate on test — NO touching test during search
 * 4. Persistence requirement: signal must hold N consecutive months
 * 5. Transmission confirmation gate: Pressure alone insufficient
 */

const fs = require('fs');
const path = require('path');
const { evaluateDiagnostics } = require('./macro_engine');

const FRED_DIR = path.join(__dirname, 'data', 'fred');

// ============================================
// GROUND TRUTH
// ============================================
const NBER_RECESSIONS = [
  ['2007-12-01', '2009-06-01'],
  ['2020-02-01', '2020-04-01'],
];

const INFLATION_REGIMES = [
  ['2021-04-01', '2026-12-01'],
];

const CREDIT_STRESS_EVENTS = [
  ['2008-09-01', '2009-06-01'],
  ['2020-03-01', '2020-05-01'],
  ['2023-03-01', '2023-04-01'], // SVB — shorter
];

// ============================================
// DATA LOADING + TRANSFORMS (same as V1)
// ============================================
function loadAllFred() {
  const store = {};
  for (const f of fs.readdirSync(FRED_DIR).filter(f => f.endsWith('.json'))) {
    try {
      const d = JSON.parse(fs.readFileSync(path.join(FRED_DIR, f)));
      store[d.id] = d.values;
    } catch(e) {}
  }
  return store;
}

function computeYoY(values, asOf) {
  let latest = null, latestDate = null, yearAgo = null;
  for (const [date, val] of values) {
    if (date > asOf) break;
    latest = val; latestDate = date;
  }
  if (latestDate) {
    const t = new Date(latestDate);
    t.setFullYear(t.getFullYear() - 1);
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
    prev = latest; latest = val; latestDate = date;
  }
  if (latest !== null && prev !== null) return { value: latest - prev, date: latestDate };
  return { value: null, date: latestDate };
}

function computeMoMPct(values, asOf) {
  let latest = null, latestDate = null, prev = null;
  for (const [date, val] of values) {
    if (date > asOf) break;
    prev = latest; latest = val; latestDate = date;
  }
  if (latest !== null && prev !== null && prev !== 0) return { value: ((latest / prev) - 1) * 100, date: latestDate };
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
// INDICATOR BUILDER
// ============================================
const INDICATOR_MAP = [
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
  const hyVals = fredStore['BAMLH0A0HYM2'] || [];
  const igVals = fredStore['BAMLC0A0CM'] || [];
  const hyL = getLatestValue(hyVals, asOf);
  const igL = getLatestValue(igVals, asOf);
  let hyIg = (hyL.value !== null && igL.value !== null) ? (hyL.value - igL.value) * 100 : null;

  const sofrV = fredStore['SOFR'] || [];
  const iorbV = fredStore['IORB'] || [];
  const sofrL = getLatestValue(sofrV, asOf);
  const iorbL = getLatestValue(iorbV, asOf);
  let sofrIorb = (sofrL.value !== null && iorbL.value !== null) ? (sofrL.value - iorbL.value) * 100 : null;

  const intV = fredStore['A091RC1Q027SBEA'] || [];
  const gdpV = fredStore['GDP'] || [];
  const recV = fredStore['W006RC1Q027SBEA'] || [];
  const intL = getLatestValue(intV, asOf);
  const gdpL = getLatestValue(gdpV, asOf);
  const recL = getLatestValue(recV, asOf);
  let intGdp = (intL.value && gdpL.value) ? (intL.value / gdpL.value) * 100 : null;
  let intRec = (intL.value && recL.value) ? (intL.value / recL.value) * 100 : null;

  for (const ind of INDICATOR_MAP) {
    let current = null, lastObsDate = null;
    if (ind.series === '_HY_IG_SPREAD') { current = hyIg; lastObsDate = hyL.date; }
    else if (ind.series === '_SOFR_IORB') { current = sofrIorb; lastObsDate = sofrL.date; }
    else if (ind.series === '_INTEREST_GDP') { current = intGdp; lastObsDate = intL.date; }
    else if (ind.series === '_INTEREST_RECEIPTS') { current = intRec; lastObsDate = intL.date; }
    else {
      const vals = fredStore[ind.series];
      if (!vals || vals.length === 0) continue;
      switch(ind.transform) {
        case 'yoy': { const r = computeYoY(vals, asOf); current = r.value; lastObsDate = r.date; break; }
        case 'mom_abs_k': { const r = computeMoMAbs(vals, asOf); current = r.value; lastObsDate = r.date; break; }
        case 'mom_pct': { const r = computeMoMPct(vals, asOf); current = r.value; lastObsDate = r.date; break; }
        case 'ann_1m': { const r = computeAnnualizedNM(vals, asOf, 1); current = r.value; lastObsDate = r.date; break; }
        case 'ann_3m': { const r = computeAnnualizedNM(vals, asOf, 3); current = r.value; lastObsDate = r.date; break; }
        case 'ann_6m': { const r = computeAnnualizedNM(vals, asOf, 6); current = r.value; lastObsDate = r.date; break; }
        case 'div1000': { const r = getLatestValue(vals, asOf); current = r.value !== null ? r.value / 1000 : null; lastObsDate = r.date; break; }
        case 'raw_bp': { const r = getLatestValue(vals, asOf); current = r.value !== null ? r.value * 100 : null; lastObsDate = r.date; break; }
        default: { const r = getLatestValue(vals, asOf); current = r.value; lastObsDate = r.date; break; }
      }
    }
    results.push({ id: ind.id, label: ind.label, current, lastObsDate, daysSinceObs: lastObsDate ? Math.round((new Date(asOf) - new Date(lastObsDate)) / 86400000) : 0 });
  }
  return results;
}

// ============================================
// LABEL DEFINITIONS
// ============================================
function isInRange(date, ranges) {
  for (const [s, e] of ranges) { if (date >= s && date <= e) return true; }
  return false;
}

function willEnterWithinMonths(dateStr, ranges, months) {
  const d = new Date(dateStr);
  const horizon = new Date(d);
  horizon.setMonth(horizon.getMonth() + months);
  const hStr = horizon.toISOString().split('T')[0];
  for (const [s, e] of ranges) {
    // Will the start of a range fall within [dateStr, hStr]?
    if (s >= dateStr && s <= hStr) return true;
    // Or are we already in range?
    if (dateStr >= s && dateStr <= e) return true;
  }
  return false;
}

// ============================================
// SIGNAL DEFINITIONS WITH GATES
// ============================================

// For recession: require Pressure ≥ threshold AND Transmission ≥ trans_threshold
// For persistence: require N consecutive months meeting condition
function evaluateSignalWithGates(diagHistory, dateIdx, module, pressureThresh, transThresh, persistMonths) {
  if (dateIdx < persistMonths - 1) return false;
  for (let i = 0; i < persistMonths; i++) {
    const h = diagHistory[dateIdx - i];
    if (!h) return false;
    const stages = h[module]?.stages;
    if (!stages) return false;
    const pScore = stages[0]?.score || 0;
    const tScore = stages[1]?.score || 0;
    if (pScore < pressureThresh) return false;
    if (tScore < transThresh) return false;
  }
  return true;
}

// ============================================
// SCORING
// ============================================
function computeStats(predictions, labels) {
  let tp = 0, fp = 0, tn = 0, fn = 0;
  for (let i = 0; i < predictions.length; i++) {
    if (predictions[i] && labels[i]) tp++;
    else if (predictions[i] && !labels[i]) fp++;
    else if (!predictions[i] && labels[i]) fn++;
    else tn++;
  }
  const precision = tp + fp > 0 ? tp / (tp + fp) : 0;
  const recall = tp + fn > 0 ? tp / (tp + fn) : 0;
  const f1 = precision + recall > 0 ? 2 * precision * recall / (precision + recall) : 0;
  return { tp, fp, tn, fn, precision, recall, f1 };
}

// ============================================
// MAIN
// ============================================
function main() {
  console.log('📊 Loading data...');
  const fredStore = loadAllFred();
  console.log(`  FRED: ${Object.keys(fredStore).length} series`);

  // Generate dates
  const allDates = [];
  for (let y = 2006; y <= 2026; y++) {
    const maxM = (y === 2026) ? 6 : 12;
    for (let m = 1; m <= maxM; m++) {
      const d = new Date(y, m, 0);
      allDates.push(d.toISOString().split('T')[0]);
    }
  }
  console.log(`  ${allDates.length} monthly snapshots\n`);

  // Split: Train = 2006-2018, Test = 2019-2026
  const TRAIN_END = '2018-12-31';
  const trainIdx = allDates.filter(d => d <= TRAIN_END).length;
  console.log(`  Train: ${allDates[0]} ~ ${allDates[trainIdx-1]} (${trainIdx} months)`);
  console.log(`  Test:  ${allDates[trainIdx]} ~ ${allDates[allDates.length-1]} (${allDates.length - trainIdx} months)\n`);

  // Run engine on all dates
  console.log('  Running engine on all dates...');
  const diagHistory = [];
  for (const dateStr of allDates) {
    const indicators = buildIndicatorsAsOf(dateStr, fredStore);
    try {
      diagHistory.push(evaluateDiagnostics(indicators));
    } catch(e) {
      diagHistory.push(null);
    }
  }

  // Build labels
  const FORECAST_HORIZON = 6; // months
  const recLabels_nowcast = allDates.map(d => isInRange(d, NBER_RECESSIONS));
  const recLabels_forecast = allDates.map(d => willEnterWithinMonths(d, NBER_RECESSIONS, FORECAST_HORIZON));
  const creLabels_nowcast = allDates.map(d => isInRange(d, CREDIT_STRESS_EVENTS));
  const creLabels_forecast = allDates.map(d => willEnterWithinMonths(d, CREDIT_STRESS_EVENTS, FORECAST_HORIZON));

  // ============================================
  // GRID SEARCH ON TRAIN SET
  // ============================================
  console.log('\n' + '='.repeat(70));
  console.log('🔍 GRID SEARCH (Train period only: 2006–2018)');
  console.log('='.repeat(70));

  const pressureGrid = [0.3, 0.4, 0.5, 0.6, 0.7];
  const transGrid = [0.0, 0.2, 0.3, 0.5];
  const persistGrid = [1, 2, 3];

  // Search for recession FORECAST
  let bestRec = { f1: 0, config: null, stats: null };
  for (const pT of pressureGrid) {
    for (const tT of transGrid) {
      for (const per of persistGrid) {
        const preds = allDates.map((_, i) => i < trainIdx ? evaluateSignalWithGates(diagHistory, i, 'recession', pT, tT, per) : false);
        const trainPreds = preds.slice(0, trainIdx);
        const trainLabels = recLabels_forecast.slice(0, trainIdx);
        const s = computeStats(trainPreds, trainLabels);
        if (s.recall >= 0.70 && s.f1 > bestRec.f1) {
          bestRec = { f1: s.f1, config: { pressureThresh: pT, transThresh: tT, persist: per }, stats: s };
        }
      }
    }
  }

  // Search for credit FORECAST
  let bestCre = { f1: 0, config: null, stats: null };
  for (const pT of pressureGrid) {
    for (const tT of transGrid) {
      for (const per of persistGrid) {
        const preds = allDates.map((_, i) => i < trainIdx ? evaluateSignalWithGates(diagHistory, i, 'credit', pT, tT, per) : false);
        const trainPreds = preds.slice(0, trainIdx);
        const trainLabels = creLabels_forecast.slice(0, trainIdx);
        const s = computeStats(trainPreds, trainLabels);
        if (s.recall >= 0.70 && s.f1 > bestCre.f1) {
          bestCre = { f1: s.f1, config: { pressureThresh: pT, transThresh: tT, persist: per }, stats: s };
        }
      }
    }
  }

  console.log('\n  RECESSION FORECAST (6-month horizon)');
  if (bestRec.config) {
    console.log(`    Best config: Pressure≥${bestRec.config.pressureThresh}, Trans≥${bestRec.config.transThresh}, Persist≥${bestRec.config.persist}m`);
    console.log(`    Train: P=${(bestRec.stats.precision*100).toFixed(1)}% R=${(bestRec.stats.recall*100).toFixed(1)}% F1=${(bestRec.stats.f1*100).toFixed(1)}%`);
    console.log(`           TP=${bestRec.stats.tp} FP=${bestRec.stats.fp} TN=${bestRec.stats.tn} FN=${bestRec.stats.fn}`);
  } else {
    console.log('    No config found with recall ≥ 70%');
  }

  console.log('\n  CREDIT FORECAST (6-month horizon)');
  if (bestCre.config) {
    console.log(`    Best config: Pressure≥${bestCre.config.pressureThresh}, Trans≥${bestCre.config.transThresh}, Persist≥${bestCre.config.persist}m`);
    console.log(`    Train: P=${(bestCre.stats.precision*100).toFixed(1)}% R=${(bestCre.stats.recall*100).toFixed(1)}% F1=${(bestCre.stats.f1*100).toFixed(1)}%`);
    console.log(`           TP=${bestCre.stats.tp} FP=${bestCre.stats.fp} TN=${bestCre.stats.tn} FN=${bestCre.stats.fn}`);
  } else {
    console.log('    No config found with recall ≥ 70%');
  }

  // ============================================
  // OUT-OF-SAMPLE VALIDATION ON TEST SET
  // ============================================
  console.log('\n' + '='.repeat(70));
  console.log('✅ OUT-OF-SAMPLE VALIDATION (Test period: 2019–2026)');
  console.log('='.repeat(70));

  if (bestRec.config) {
    const preds = allDates.map((_, i) => evaluateSignalWithGates(diagHistory, i, 'recession', bestRec.config.pressureThresh, bestRec.config.transThresh, bestRec.config.persist));
    const testPreds = preds.slice(trainIdx);
    const testLabels = recLabels_forecast.slice(trainIdx);
    const s = computeStats(testPreds, testLabels);
    console.log(`\n  RECESSION FORECAST (test)`);
    console.log(`    Config: Pressure≥${bestRec.config.pressureThresh}, Trans≥${bestRec.config.transThresh}, Persist≥${bestRec.config.persist}m`);
    console.log(`    Test:  P=${(s.precision*100).toFixed(1)}% R=${(s.recall*100).toFixed(1)}% F1=${(s.f1*100).toFixed(1)}%`);
    console.log(`           TP=${s.tp} FP=${s.fp} TN=${s.tn} FN=${s.fn}`);
  }

  if (bestCre.config) {
    const preds = allDates.map((_, i) => evaluateSignalWithGates(diagHistory, i, 'credit', bestCre.config.pressureThresh, bestCre.config.transThresh, bestCre.config.persist));
    const testPreds = preds.slice(trainIdx);
    const testLabels = creLabels_forecast.slice(trainIdx);
    const s = computeStats(testPreds, testLabels);
    console.log(`\n  CREDIT FORECAST (test)`);
    console.log(`    Config: Pressure≥${bestCre.config.pressureThresh}, Trans≥${bestCre.config.transThresh}, Persist≥${bestCre.config.persist}m`);
    console.log(`    Test:  P=${(s.precision*100).toFixed(1)}% R=${(s.recall*100).toFixed(1)}% F1=${(s.f1*100).toFixed(1)}%`);
    console.log(`           TP=${s.tp} FP=${s.fp} TN=${s.tn} FN=${s.fn}`);
  }

  // ============================================
  // INFLATION (no change, just report on both splits)
  // ============================================
  console.log('\n' + '='.repeat(70));
  console.log('📊 INFLATION (original thresholds, no tuning)');
  console.log('='.repeat(70));

  const infLabels = allDates.map(d => isInRange(d, INFLATION_REGIMES));
  const infPreds = diagHistory.map(h => h ? (h.inflation?.stages?.[0]?.score >= 0.7) : false);

  const infTrain = computeStats(infPreds.slice(0, trainIdx), infLabels.slice(0, trainIdx));
  const infTest = computeStats(infPreds.slice(trainIdx), infLabels.slice(trainIdx));
  console.log(`\n  Train: P=${(infTrain.precision*100).toFixed(1)}% R=${(infTrain.recall*100).toFixed(1)}% F1=${(infTrain.f1*100).toFixed(1)}%`);
  console.log(`         TP=${infTrain.tp} FP=${infTrain.fp} TN=${infTrain.tn} FN=${infTrain.fn}`);
  console.log(`  Test:  P=${(infTest.precision*100).toFixed(1)}% R=${(infTest.recall*100).toFixed(1)}% F1=${(infTest.f1*100).toFixed(1)}%`);
  console.log(`         TP=${infTest.tp} FP=${infTest.fp} TN=${infTest.tn} FN=${infTest.fn}`);

  // ============================================
  // NOWCAST vs FORECAST comparison
  // ============================================
  console.log('\n' + '='.repeat(70));
  console.log('📐 LABEL COMPARISON: Nowcast vs Forecast (full sample, V1 thresholds)');
  console.log('='.repeat(70));

  // V1 simple: Pressure score >= 0.5 (yellow+)
  const recPredsV1 = diagHistory.map(h => h ? (h.recession?.stages?.[0]?.score >= 0.5) : false);
  const recNow = computeStats(recPredsV1, recLabels_nowcast);
  const recFore = computeStats(recPredsV1, recLabels_forecast);
  console.log('\n  RECESSION (V1 thresholds: Pressure ≥ 0.5)');
  console.log(`    Nowcast label:  P=${(recNow.precision*100).toFixed(1)}% R=${(recNow.recall*100).toFixed(1)}%  TP=${recNow.tp} FP=${recNow.fp} FN=${recNow.fn}`);
  console.log(`    Forecast label: P=${(recFore.precision*100).toFixed(1)}% R=${(recFore.recall*100).toFixed(1)}%  TP=${recFore.tp} FP=${recFore.fp} FN=${recFore.fn}`);

  const crePredsV1 = diagHistory.map(h => h ? (h.credit?.stages?.[0]?.score >= 0.5) : false);
  const creNow = computeStats(crePredsV1, creLabels_nowcast);
  const creFore = computeStats(crePredsV1, creLabels_forecast);
  console.log('\n  CREDIT (V1 thresholds: Pressure ≥ 0.5)');
  console.log(`    Nowcast label:  P=${(creNow.precision*100).toFixed(1)}% R=${(creNow.recall*100).toFixed(1)}%  TP=${creNow.tp} FP=${creNow.fp} FN=${creNow.fn}`);
  console.log(`    Forecast label: P=${(creFore.precision*100).toFixed(1)}% R=${(creFore.recall*100).toFixed(1)}%  TP=${creFore.tp} FP=${creFore.fp} FN=${creFore.fn}`);

  // ============================================
  // EPISODE DETAIL (unchanged — for human review)
  // ============================================
  console.log('\n' + '='.repeat(70));
  console.log('🔍 KEY EPISODES (same as V1, for reference)');
  console.log('='.repeat(70));

  const episodes = [
    { name: 'Pre-GFC', dates: ['2007-06-30','2007-09-30','2007-12-31','2008-03-31','2008-06-30','2008-09-30'] },
    { name: 'GFC Bottom', dates: ['2008-12-31','2009-03-31','2009-06-30'] },
    { name: 'Pre-COVID', dates: ['2019-12-31','2020-01-31','2020-02-29','2020-03-31','2020-04-30'] },
    { name: 'Inflation Build', dates: ['2021-03-31','2021-06-30','2021-09-30','2021-12-31','2022-03-31','2022-06-30'] },
    { name: 'SVB', dates: ['2023-02-28','2023-03-31','2023-04-30'] },
    { name: 'Current', dates: ['2025-12-31','2026-03-31','2026-06-30'] },
  ];

  for (const ep of episodes) {
    console.log(`\n  📌 ${ep.name}`);
    for (const dateStr of ep.dates) {
      const idx = allDates.indexOf(dateStr);
      if (idx < 0) continue;
      const diag = diagHistory[idx];
      if (!diag) continue;
      const sL = (s) => s === 'red' ? '🔴' : s === 'yellow' ? '🟡' : s === 'green' ? '🟢' : '⚪';
      const gt = {
        rec: isInRange(dateStr, NBER_RECESSIONS),
        recF: willEnterWithinMonths(dateStr, NBER_RECESSIONS, 6),
        inf: isInRange(dateStr, INFLATION_REGIMES),
        cre: isInRange(dateStr, CREDIT_STRESS_EVENTS),
        creF: willEnterWithinMonths(dateStr, CREDIT_STRESS_EVENTS, 6),
      };
      const gtParts = [];
      if (gt.rec) gtParts.push('REC');
      else if (gt.recF) gtParts.push('rec6m');
      if (gt.inf) gtParts.push('INF');
      if (gt.cre) gtParts.push('CRE');
      else if (gt.creF) gtParts.push('cre6m');
      const gtStr = gtParts.length > 0 ? gtParts.join('+') : '—';

      const r = diag.recession.stages;
      const i = diag.inflation.stages;
      const c = diag.credit.stages;
      console.log(`    ${dateStr}  GT:[${gtStr.padEnd(12)}]  Rec: ${sL(r[0].status)}${sL(r[1].status)}${sL(r[2].status)}  Inf: ${sL(i[0].status)}${sL(i[1].status)}${sL(i[2].status)}  Cre: ${sL(c[0].status)}${sL(c[1].status)}${sL(c[2].status)}`);
    }
  }

  console.log('\n' + '='.repeat(70));
  console.log('✅ Backtest V2 complete.');
}

main();
