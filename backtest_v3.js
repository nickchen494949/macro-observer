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
function loadAllFred() {
  const store = {};
  for (const f of fs.readdirSync(FRED_DIR).filter(f => f.endsWith('.json'))) {
    try { const d = JSON.parse(fs.readFileSync(path.join(FRED_DIR, f))); store[d.id] = d.values; } catch(e) {}
  }
  return store;
}

function getLatestValue(values, asOf) {
  let latest = null, latestDate = null;
  for (const [date, val] of values) { if (date > asOf) break; latest = val; latestDate = date; }
  return { value: latest, date: latestDate };
}
function computeYoY(values, asOf) {
  let latest = null, latestDate = null, yearAgo = null;
  for (const [date, val] of values) { if (date > asOf) break; latest = val; latestDate = date; }
  if (latestDate) {
    const t = new Date(latestDate); t.setFullYear(t.getFullYear() - 1);
    let bestDist = Infinity;
    for (const [date, val] of values) { const dist = Math.abs(new Date(date) - t); if (dist < bestDist) { bestDist = dist; yearAgo = val; } if (date > latestDate) break; }
  }
  if (latest !== null && yearAgo !== null && yearAgo !== 0) return { value: ((latest / yearAgo) - 1) * 100, date: latestDate };
  return { value: null, date: latestDate };
}
function computeMoMAbs(values, asOf) {
  let latest = null, latestDate = null, prev = null;
  for (const [date, val] of values) { if (date > asOf) break; prev = latest; latest = val; latestDate = date; }
  if (latest !== null && prev !== null) return { value: latest - prev, date: latestDate };
  return { value: null, date: latestDate };
}
function computeMoMPct(values, asOf) {
  let latest = null, latestDate = null, prev = null;
  for (const [date, val] of values) { if (date > asOf) break; prev = latest; latest = val; latestDate = date; }
  if (latest !== null && prev !== null && prev !== 0) return { value: ((latest / prev) - 1) * 100, date: latestDate };
  return { value: null, date: latestDate };
}
function computeAnnualizedNM(values, asOf, nMonths) {
  let candidates = [];
  for (const [date, val] of values) { if (date > asOf) break; candidates.push([date, val]); }
  if (candidates.length < nMonths + 1) return { value: null, date: null };
  const end = candidates[candidates.length - 1], start = candidates[candidates.length - 1 - nMonths];
  if (start[1] === 0) return { value: null, date: end[0] };
  return { value: (Math.pow(end[1] / start[1], 12 / nMonths) - 1) * 100, date: end[0] };
}

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
  // Returns array of { startIdx, endIdx, startDate, endDate, durationMonths }
  const alerts = [];
  let inAlert = false, startIdx = -1;
  for (let i = 0; i < dates.length; i++) {
    const on = signalFn(i);
    if (on && !inAlert) { inAlert = true; startIdx = i; }
    else if (!on && inAlert) {
      alerts.push({ startIdx, endIdx: i-1, startDate: dates[startIdx], endDate: dates[i-1], duration: i - startIdx });
      inAlert = false;
    }
  }
  if (inAlert) alerts.push({ startIdx, endIdx: dates.length-1, startDate: dates[startIdx], endDate: dates[dates.length-1], duration: dates.length - startIdx });
  return alerts;
}

function scoreAlerts(alerts, events, allDates) {
  const results = { hits: [], misses: [], falseAlarms: [] };

  // For each event, find the earliest alert that overlaps or precedes (within 6m) the event
  const eventHit = new Array(events.length).fill(false);
  const alertUsed = new Array(alerts.length).fill(false);

  for (let ei = 0; ei < events.length; ei++) {
    const ev = events[ei];
    // Look for alerts that start before or during the event, and end during or after event start
    let bestAlert = null, bestLead = Infinity;
    for (let ai = 0; ai < alerts.length; ai++) {
      const al = alerts[ai];
      // Alert overlaps with event window, or leads it by up to 12 months
      const alertEnd = al.endDate;
      const alertStart = al.startDate;
      if (alertEnd < ev.start) {
        // Alert ended before event. How long before?
        const leadMonths = monthDiff(alertEnd, ev.start);
        if (leadMonths <= 6) { // Alert ended within 6 months of event
          if (leadMonths < bestLead) { bestAlert = ai; bestLead = leadMonths; }
        }
      } else if (alertStart <= ev.end) {
        // Alert overlaps with event
        const leadMonths = monthDiff(alertStart, ev.start);
        if (Math.abs(leadMonths) < Math.abs(bestLead)) { bestAlert = ai; bestLead = -leadMonths; } // negative = alert started after event
      }
    }
    if (bestAlert !== null) {
      eventHit[ei] = true;
      alertUsed[bestAlert] = true;
      results.hits.push({ event: ev.name, eventStart: ev.start, alertStart: alerts[bestAlert].startDate, leadMonths: bestLead, alertDuration: alerts[bestAlert].duration });
    } else {
      results.misses.push({ event: ev.name, eventStart: ev.start });
    }
  }

  // Unused alerts = false alarms
  for (let ai = 0; ai < alerts.length; ai++) {
    if (!alertUsed[ai]) {
      results.falseAlarms.push({ alertStart: alerts[ai].startDate, alertEnd: alerts[ai].endDate, duration: alerts[ai].duration });
    }
  }

  return results;
}

function monthDiff(dateA, dateB) {
  const a = new Date(dateA), b = new Date(dateB);
  return (b.getFullYear() - a.getFullYear()) * 12 + (b.getMonth() - a.getMonth());
}

// ============================================
// BASELINES
// ============================================
function baselineSignal(fredStore, allDates, seriesId, transform, threshold, direction) {
  // direction: 'above' = signal when value > threshold, 'below' = value < threshold
  return (idx) => {
    const asOf = allDates[idx];
    const vals = fredStore[seriesId];
    if (!vals) return false;
    let val;
    if (transform === 'yoy') val = computeYoY(vals, asOf).value;
    else if (transform === 'ann_3m') val = computeAnnualizedNM(vals, asOf, 3).value;
    else if (transform === 'ann_6m') val = computeAnnualizedNM(vals, asOf, 6).value;
    else if (transform === 'raw_bp') { const r = getLatestValue(vals, asOf); val = r.value !== null ? r.value * 100 : null; }
    else val = getLatestValue(vals, asOf).value;
    if (val === null) return false;
    return direction === 'above' ? val > threshold : val < threshold;
  };
}

function baselineSpreadSignal(fredStore, allDates, seriesA, seriesB, threshold, direction) {
  return (idx) => {
    const asOf = allDates[idx];
    const vA = getLatestValue(fredStore[seriesA]||[], asOf).value;
    const vB = getLatestValue(fredStore[seriesB]||[], asOf).value;
    if (vA === null || vB === null) return false;
    const spread = (vA - vB) * 100; // bp
    return direction === 'above' ? spread > threshold : spread < threshold;
  };
}

// ============================================
// MAIN
// ============================================
function main() {
  console.log('📊 Loading data...');
  const fredStore = loadAllFred();

  const allDates = [];
  for (let y = 2006; y <= 2026; y++) {
    const maxM = (y === 2026) ? 6 : 12;
    for (let m = 1; m <= maxM; m++) { allDates.push(new Date(y, m, 0).toISOString().split('T')[0]); }
  }
  console.log(`  ${allDates.length} monthly snapshots\n`);

  // Run engine
  console.log('  Running macro_engine on all dates...');
  const diagHistory = [];
  for (const dateStr of allDates) {
    const ind = buildIndicatorsAsOf(dateStr, fredStore);
    try { diagHistory.push(evaluateDiagnostics(ind)); } catch(e) { diagHistory.push(null); }
  }

  // ============================================
  // PART 1: EVENT-BASED SCORING
  // ============================================
  console.log('\n' + '='.repeat(70));
  console.log('📌 PART 1: EVENT-BASED SCORING');
  console.log('  (consecutive signal months = 1 alert, scored against named events)');
  console.log('='.repeat(70));

  const modules = [
    { name: 'Recession (Pressure≥Yellow)', events: EVENTS.recession,
      signalFn: (i) => diagHistory[i]?.recession?.stages?.[0]?.score >= 0.5 },
    { name: 'Inflation (Level=Red)', events: EVENTS.inflation,
      signalFn: (i) => diagHistory[i]?.inflation?.stages?.[0]?.score >= 0.7 },
    { name: 'Credit (Pressure≥Yellow)', events: EVENTS.credit,
      signalFn: (i) => diagHistory[i]?.credit?.stages?.[0]?.score >= 0.5 },
  ];

  for (const mod of modules) {
    console.log(`\n  ── ${mod.name} ──`);
    const alerts = extractAlerts(allDates, mod.signalFn);
    const result = scoreAlerts(alerts, mod.events, allDates);

    console.log(`  Total alerts: ${alerts.length}`);
    console.log(`  Events hit: ${result.hits.length}/${mod.events.length}`);
    console.log(`  False alarm alerts: ${result.falseAlarms.length}`);

    if (result.hits.length > 0) {
      console.log('  Hits:');
      for (const h of result.hits) {
        const leadStr = h.leadMonths > 0 ? `+${h.leadMonths}m lead` : h.leadMonths < 0 ? `${h.leadMonths}m late` : 'on time';
        console.log(`    ✅ ${h.event}: alert ${h.alertStart}, event ${h.eventStart} (${leadStr}, alert lasted ${h.alertDuration}m)`);
      }
    }
    if (result.misses.length > 0) {
      console.log('  Misses:');
      for (const m of result.misses) console.log(`    ❌ ${m.event}: no alert near ${m.eventStart}`);
    }
    if (result.falseAlarms.length > 0) {
      console.log(`  False alarms (${result.falseAlarms.length}):`);
      for (const f of result.falseAlarms) console.log(`    ⚠️  ${f.alertStart} ~ ${f.alertEnd} (${f.duration}m)`);
    }
  }

  // ============================================
  // PART 2: BASELINE COMPARISON
  // ============================================
  console.log('\n' + '='.repeat(70));
  console.log('📐 PART 2: BASELINE COMPARISON');
  console.log('  (single-indicator models vs our multi-indicator engine)');
  console.log('='.repeat(70));

  // Recession baselines
  console.log('\n  ── RECESSION BASELINES ──');
  const recBaselines = [
    { name: '10Y-3M Spread < 0bp', fn: baselineSignal(fredStore, allDates, 'T10Y3M', 'raw_bp', 0, 'below') },
    { name: 'Sahm Rule ≥ 0.50', fn: baselineSignal(fredStore, allDates, 'SAHMREALTIME', 'raw', 0.50, 'above') },
    { name: 'Initial Claims > 250k', fn: baselineSignal(fredStore, allDates, 'ICSA', 'raw', 250, 'above') },
    { name: 'NFCI > 0', fn: baselineSignal(fredStore, allDates, 'NFCI', 'raw', 0, 'above') },
    { name: 'Our Engine (Pressure≥0.5)', fn: (i) => diagHistory[i]?.recession?.stages?.[0]?.score >= 0.5 },
  ];
  for (const bl of recBaselines) {
    const alerts = extractAlerts(allDates, bl.fn);
    const result = scoreAlerts(alerts, EVENTS.recession, allDates);
    const hitRate = `${result.hits.length}/${EVENTS.recession.length}`;
    const leads = result.hits.map(h => h.leadMonths > 0 ? `+${h.leadMonths}m` : `${h.leadMonths}m`).join(', ') || '—';
    console.log(`  ${bl.name.padEnd(35)} Hit: ${hitRate}  Alerts: ${alerts.length}  False: ${result.falseAlarms.length}  Lead: ${leads}`);
  }

  // Inflation baselines
  console.log('\n  ── INFLATION BASELINES ──');
  const infBaselines = [
    { name: 'Core PCE YoY > 3%', fn: baselineSignal(fredStore, allDates, 'PCEPILFE', 'yoy', 3.0, 'above') },
    { name: 'Core PCE 3M Ann > 3.5%', fn: baselineSignal(fredStore, allDates, 'PCEPILFE', 'ann_3m', 3.5, 'above') },
    { name: 'Core PCE 6M Ann > 3%', fn: baselineSignal(fredStore, allDates, 'PCEPILFE', 'ann_6m', 3.0, 'above') },
    { name: 'PPI YoY > 3%', fn: baselineSignal(fredStore, allDates, 'PPIFIS', 'yoy', 3.0, 'above') },
    { name: '10Y Breakeven > 2.5%', fn: baselineSignal(fredStore, allDates, 'T10YIE', 'raw', 2.5, 'above') },
    { name: 'Our Engine (Level≥Red)', fn: (i) => diagHistory[i]?.inflation?.stages?.[0]?.score >= 0.7 },
  ];
  for (const bl of infBaselines) {
    const alerts = extractAlerts(allDates, bl.fn);
    const result = scoreAlerts(alerts, EVENTS.inflation, allDates);
    const hitRate = `${result.hits.length}/${EVENTS.inflation.length}`;
    const leads = result.hits.map(h => h.leadMonths > 0 ? `+${h.leadMonths}m` : `${h.leadMonths}m`).join(', ') || '—';
    console.log(`  ${bl.name.padEnd(35)} Hit: ${hitRate}  Alerts: ${alerts.length}  False: ${result.falseAlarms.length}  Lead: ${leads}`);
  }

  // Credit baselines
  console.log('\n  ── CREDIT BASELINES ──');
  const creBaselines = [
    { name: 'HY-IG > 400bp', fn: baselineSpreadSignal(fredStore, allDates, 'BAMLH0A0HYM2', 'BAMLC0A0CM', 400, 'above') },
    { name: 'NFCI > 0.5', fn: baselineSignal(fredStore, allDates, 'NFCI', 'raw', 0.5, 'above') },
    { name: 'SLOOS C&I > 20%', fn: baselineSignal(fredStore, allDates, 'DRTSCILM', 'raw', 20, 'above') },
    { name: 'Our Engine (Pressure≥0.5)', fn: (i) => diagHistory[i]?.credit?.stages?.[0]?.score >= 0.5 },
  ];
  for (const bl of creBaselines) {
    const alerts = extractAlerts(allDates, bl.fn);
    const result = scoreAlerts(alerts, EVENTS.credit, allDates);
    const hitRate = `${result.hits.length}/${EVENTS.credit.length}`;
    const leads = result.hits.map(h => h.leadMonths > 0 ? `+${h.leadMonths}m` : `${h.leadMonths}m`).join(', ') || '—';
    console.log(`  ${bl.name.padEnd(35)} Hit: ${hitRate}  Alerts: ${alerts.length}  False: ${result.falseAlarms.length}  Lead: ${leads}`);
  }

  console.log('\n' + '='.repeat(70));
  console.log('✅ Backtest V3 complete.');
}

main();
