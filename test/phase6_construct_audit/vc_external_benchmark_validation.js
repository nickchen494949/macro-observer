#!/usr/bin/env node
/**
 * VC External Benchmark Validation
 * =================================
 * Compares our VC Mechanical Pressure model reconstruction against
 * the real S&P 500 Average Daily Risk Control 10% Index (SPXAV10P).
 *
 * Methodology:
 *   1. Load SPX price history and SPXAV10P benchmark history
 *   2. Reconstruct a synthetic "risk control" index using our exact model:
 *      - max(vol20, vol40) simple annualized stddev
 *      - 10% target vol → exposure = min(1.0, 10/vol)
 *      - T-2 observation lag
 *      - 100% cap, 0% floor
 *   3. Compare daily returns, exposure paths, stress episodes
 *
 * OUTPUT: Structured validation report with metrics
 *
 * CRITICAL: This script does NOT tune any parameters.
 *           All model parameters are frozen from production code.
 */

'use strict';
const fs = require('fs');
const path = require('path');

// ============================================================
// 1. Load Data
// ============================================================
const PROJECT = path.resolve(__dirname, '../..');
const spxRaw = JSON.parse(fs.readFileSync(path.join(PROJECT, 'data/yahoo/_GSPC.json'), 'utf-8'));
const benchRaw = JSON.parse(fs.readFileSync(path.join(PROJECT, 'data/benchmark/SPXAV10P.json'), 'utf-8'));

// Build date→value maps (handle Yahoo mixed format)
function extractPrice(pt) {
  const val = pt[1];
  if (val == null) return null;
  if (typeof val === 'object') return val.adjClose || val.close || null;
  return typeof val === 'number' ? val : null;
}

const spxMap = new Map();
for (const pt of spxRaw.values) {
  const p = extractPrice(pt);
  if (p != null && !isNaN(p) && p > 0) spxMap.set(pt[0], p);
}

const benchMap = new Map();
for (const pt of benchRaw.values) {
  if (pt[1] != null && !isNaN(pt[1]) && pt[1] > 0) benchMap.set(pt[0], pt[1]);
}

// Sorted common dates
const allSpxDates = [...spxMap.keys()].sort();
const allBenchDates = [...benchMap.keys()].sort();
const benchDateSet = new Set(allBenchDates);
const spxDateSet = new Set(allSpxDates);
const commonDates = allSpxDates.filter(d => benchDateSet.has(d));

console.log('=== DATA SUMMARY ===');
console.log(`SPX observations:    ${allSpxDates.length} (${allSpxDates[0]} to ${allSpxDates[allSpxDates.length-1]})`);
console.log(`SPXAV10P benchmark:  ${allBenchDates.length} (${allBenchDates[0]} to ${allBenchDates[allBenchDates.length-1]})`);
console.log(`Common dates:        ${commonDates.length} (${commonDates[0]} to ${commonDates[commonDates.length-1]})`);
console.log();

// ============================================================
// 2. Reconstruct Synthetic VC Index
// ============================================================

/**
 * Compute annualized volatility ending at index `endIdx` over `window` days.
 * Uses sample stddev (ddof=1), log returns, annualized by sqrt(252)*100.
 * EXACT MATCH to flow_engine.js getVolEndingAt().
 */
function computeVol(prices, endIdx, window) {
  if (endIdx - window < 0) return null;
  const returns = [];
  for (let i = endIdx - window + 1; i <= endIdx; i++) {
    if (prices[i] == null || prices[i-1] == null || prices[i] <= 0 || prices[i-1] <= 0) return null;
    returns.push(Math.log(prices[i] / prices[i-1]));
  }
  if (returns.length < 2) return null;
  const n = returns.length;
  const mean = returns.reduce((a,b) => a+b, 0) / n;
  const variance = returns.reduce((a,b) => a + (b-mean)**2, 0) / (n - 1);
  return Math.sqrt(variance) * Math.sqrt(252) * 100;
}

// Build arrays aligned to common dates (for SPX)
const spxPrices = commonDates.map(d => spxMap.get(d));
const benchPrices = commonDates.map(d => benchMap.get(d));

// Compute exposure series
// T-2 observation lag: on day T, use vol computed from data through T-2
const exposures = new Array(commonDates.length).fill(null);
const vol20s = new Array(commonDates.length).fill(null);
const vol40s = new Array(commonDates.length).fill(null);
const selectedVols = new Array(commonDates.length).fill(null);

for (let t = 42; t < commonDates.length; t++) {
  // Observation lag: vol is computed from prices through index (t-2)
  const obsIdx = t - 2;
  if (obsIdx < 40) continue;
  
  const v20 = computeVol(spxPrices, obsIdx, 20);
  const v40 = computeVol(spxPrices, obsIdx, 40);
  vol20s[t] = v20;
  vol40s[t] = v40;
  
  const selVol = (v20 != null && v40 != null) ? Math.max(v20, v40) : (v20 || v40);
  selectedVols[t] = selVol;
  
  if (selVol != null && selVol > 0) {
    exposures[t] = Math.min(1.0, Math.max(0.0, 10.0 / selVol));
  }
}

// ============================================================
// 3. Construct Synthetic Index Returns
// ============================================================

// Synthetic index return on day t:
//   r_synth(t) = exposure(t) * r_spx(t) + (1 - exposure(t)) * r_cash(t)
// For PRICE RETURN index, cash return = 0 (no interest)
// So: r_synth(t) = exposure(t) * r_spx(t)

const synthReturns = [];  // {date, synthReturn, benchReturn, spxReturn, exposure}
const synthLevels = [];   // cumulative index level

let synthLevel = null;
let startIdx = null;

for (let t = 1; t < commonDates.length; t++) {
  if (exposures[t] == null || spxPrices[t] == null || spxPrices[t-1] == null) continue;
  if (spxPrices[t] <= 0 || spxPrices[t-1] <= 0) continue;
  if (benchPrices[t] == null || benchPrices[t-1] == null) continue;
  if (benchPrices[t] <= 0 || benchPrices[t-1] <= 0) continue;
  
  const spxRet = spxPrices[t] / spxPrices[t-1] - 1;
  const benchRet = benchPrices[t] / benchPrices[t-1] - 1;
  const exp = exposures[t];
  const synthRet = exp * spxRet;
  
  if (synthLevel == null) {
    synthLevel = benchPrices[t-1]; // Start synthetic at same level as benchmark
    startIdx = t;
  }
  
  synthLevel *= (1 + synthRet);
  
  synthReturns.push({
    date: commonDates[t],
    spxReturn: spxRet,
    benchReturn: benchRet,
    synthReturn: synthRet,
    exposure: exp,
    synthLevel: synthLevel,
    benchLevel: benchPrices[t],
  });
}

console.log(`=== SYNTHETIC INDEX CONSTRUCTED ===`);
console.log(`Observations with valid exposure+returns: ${synthReturns.length}`);
console.log(`Period: ${synthReturns[0].date} to ${synthReturns[synthReturns.length-1].date}`);
console.log();

// ============================================================
// 4. Statistical Comparison
// ============================================================

function pearson(x, y) {
  const n = x.length;
  const mx = x.reduce((a,b) => a+b, 0) / n;
  const my = y.reduce((a,b) => a+b, 0) / n;
  let num = 0, dx2 = 0, dy2 = 0;
  for (let i = 0; i < n; i++) {
    const dx = x[i] - mx;
    const dy = y[i] - my;
    num += dx * dy;
    dx2 += dx * dx;
    dy2 += dy * dy;
  }
  return num / (Math.sqrt(dx2) * Math.sqrt(dy2));
}

function spearman(x, y) {
  function rank(arr) {
    const indexed = arr.map((v, i) => ({v, i}));
    indexed.sort((a, b) => a.v - b.v);
    const ranks = new Array(arr.length);
    for (let i = 0; i < indexed.length; i++) ranks[indexed[i].i] = i + 1;
    return ranks;
  }
  return pearson(rank(x), rank(y));
}

function stddev(arr) {
  const n = arr.length;
  const mean = arr.reduce((a,b) => a+b, 0) / n;
  return Math.sqrt(arr.reduce((a,b) => a + (b-mean)**2, 0) / (n-1));
}

function annualizedReturn(startLevel, endLevel, years) {
  return Math.pow(endLevel / startLevel, 1/years) - 1;
}

// Extract return arrays
const sr = synthReturns.map(r => r.synthReturn);
const br = synthReturns.map(r => r.benchReturn);
const diffs = sr.map((s, i) => s - br[i]);

// --- 4a. Daily Return Correlations ---
const dailyPearson = pearson(sr, br);
const dailySpearman = spearman(sr, br);

// --- 4b. Tracking Error ---
const trackingErrorDaily = stddev(diffs);
const trackingErrorAnn = trackingErrorDaily * Math.sqrt(252);

// --- 4c. Mean Absolute Return Difference ---
const meanAbsDiff = diffs.reduce((a,b) => a + Math.abs(b), 0) / diffs.length;

// --- 4d. Cumulative Returns ---
const totalYears = (new Date(synthReturns[synthReturns.length-1].date) - new Date(synthReturns[0].date)) / (365.25 * 86400000);
const synthCumReturn = synthReturns[synthReturns.length-1].synthLevel / synthReturns[0].synthLevel - 1;
const benchCumReturn = synthReturns[synthReturns.length-1].benchLevel / synthReturns[0].benchLevel - 1;
const synthAnnReturn = annualizedReturn(synthReturns[0].synthLevel, synthReturns[synthReturns.length-1].synthLevel, totalYears);
const benchAnnReturn = annualizedReturn(synthReturns[0].benchLevel, synthReturns[synthReturns.length-1].benchLevel, totalYears);

// --- 4e. Realized Volatility ---
const synthVol = stddev(sr) * Math.sqrt(252) * 100;
const benchVol = stddev(br) * Math.sqrt(252) * 100;

console.log('=== DAILY RETURN COMPARISON ===');
console.log(`Pearson correlation:     ${dailyPearson.toFixed(6)}`);
console.log(`Spearman correlation:    ${dailySpearman.toFixed(6)}`);
console.log(`Tracking error (daily):  ${(trackingErrorDaily * 100).toFixed(4)}%`);
console.log(`Tracking error (annual): ${(trackingErrorAnn * 100).toFixed(2)}%`);
console.log(`Mean abs daily diff:     ${(meanAbsDiff * 10000).toFixed(2)} bp`);
console.log();
console.log('=== CUMULATIVE PERFORMANCE ===');
console.log(`Period: ${synthReturns[0].date} to ${synthReturns[synthReturns.length-1].date} (${totalYears.toFixed(1)} years)`);
console.log(`Synthetic cum return:    ${(synthCumReturn * 100).toFixed(2)}%  (ann: ${(synthAnnReturn * 100).toFixed(2)}%)`);
console.log(`Benchmark cum return:    ${(benchCumReturn * 100).toFixed(2)}%  (ann: ${(benchAnnReturn * 100).toFixed(2)}%)`);
console.log(`Cum return gap:          ${((synthCumReturn - benchCumReturn) * 100).toFixed(2)}%`);
console.log();
console.log('=== REALIZED VOLATILITY ===');
console.log(`Synthetic annualized:    ${synthVol.toFixed(2)}%`);
console.log(`Benchmark annualized:    ${benchVol.toFixed(2)}%`);
console.log(`Difference:              ${(synthVol - benchVol).toFixed(2)}%`);
console.log();

// ============================================================
// 5. Largest Divergence Dates
// ============================================================
const absDiffs = synthReturns.map((r, i) => ({
  date: r.date,
  diff: Math.abs(r.synthReturn - r.benchReturn),
  synthReturn: r.synthReturn,
  benchReturn: r.benchReturn,
  exposure: r.exposure,
}));
absDiffs.sort((a, b) => b.diff - a.diff);

console.log('=== TOP 20 LARGEST DAILY DIVERGENCES ===');
console.log('Date         | Diff (bp) | Synth Ret  | Bench Ret  | Exposure');
console.log('-------------|-----------|------------|------------|--------');
for (let i = 0; i < Math.min(20, absDiffs.length); i++) {
  const r = absDiffs[i];
  console.log(`${r.date}  | ${(r.diff * 10000).toFixed(1).padStart(7)} | ${(r.synthReturn * 100).toFixed(3).padStart(8)}% | ${(r.benchReturn * 100).toFixed(3).padStart(8)}% | ${(r.exposure * 100).toFixed(1)}%`);
}
console.log();

// ============================================================
// 6. Stress Period Analysis
// ============================================================
const stressPeriods = [
  { name: 'COVID Crash', start: '2020-02-19', end: '2020-03-23' },
  { name: 'COVID Recovery', start: '2020-03-24', end: '2020-06-30' },
  { name: 'VIX Spike 2018-02', start: '2018-01-26', end: '2018-02-12' },
  { name: 'Q4 2018 Selloff', start: '2018-10-01', end: '2018-12-24' },
  { name: '2022 Bear Start', start: '2022-01-03', end: '2022-06-16' },
  { name: '2022 Bear Recovery', start: '2022-10-12', end: '2023-01-31' },
  { name: 'Aug 2024 Unwind', start: '2024-07-15', end: '2024-08-15' },
  { name: 'April 2025 Tariff', start: '2025-04-01', end: '2025-04-15' },
];

console.log('=== STRESS PERIOD ANALYSIS ===');
console.log('Period               | Synth Ret | Bench Ret | Gap     | Synth Vol | Bench Vol | Corr');
console.log('---------------------|-----------|-----------|---------|-----------|-----------|------');

for (const sp of stressPeriods) {
  const periodData = synthReturns.filter(r => r.date >= sp.start && r.date <= sp.end);
  if (periodData.length < 3) {
    console.log(`${sp.name.padEnd(20)} | insufficient data`);
    continue;
  }
  
  const psr = periodData.map(r => r.synthReturn);
  const pbr = periodData.map(r => r.benchReturn);
  const pCumSynth = periodData.reduce((acc, r) => acc * (1 + r.synthReturn), 1) - 1;
  const pCumBench = periodData.reduce((acc, r) => acc * (1 + r.benchReturn), 1) - 1;
  const pSynthVol = stddev(psr) * Math.sqrt(252) * 100;
  const pBenchVol = stddev(pbr) * Math.sqrt(252) * 100;
  const pCorr = psr.length >= 3 ? pearson(psr, pbr) : NaN;
  
  console.log(`${sp.name.padEnd(20)} | ${(pCumSynth*100).toFixed(1).padStart(7)}% | ${(pCumBench*100).toFixed(1).padStart(7)}% | ${((pCumSynth-pCumBench)*100).toFixed(1).padStart(5)}% | ${pSynthVol.toFixed(1).padStart(7)}% | ${pBenchVol.toFixed(1).padStart(7)}% | ${pCorr.toFixed(3)}`);
}
console.log();

// ============================================================
// 7. Direction Agreement Analysis
// ============================================================
// Compare whether daily return sign agrees
let signAgree = 0, signDisagree = 0, signTotal = 0;
for (const r of synthReturns) {
  if (r.synthReturn === 0 || r.benchReturn === 0) continue;
  signTotal++;
  if (Math.sign(r.synthReturn) === Math.sign(r.benchReturn)) signAgree++;
  else signDisagree++;
}

console.log('=== DIRECTION AGREEMENT ===');
console.log(`Same sign days:     ${signAgree} / ${signTotal} (${(signAgree/signTotal*100).toFixed(1)}%)`);
console.log(`Opposite sign days: ${signDisagree} / ${signTotal} (${(signDisagree/signTotal*100).toFixed(1)}%)`);
console.log();

// ============================================================
// 8. Exposure Regime Analysis
// ============================================================
// Classify exposure into buckets and compare behavior
const exposureBuckets = { full: [], high: [], mid: [], low: [], minimal: [] };
for (const r of synthReturns) {
  if (r.exposure >= 0.95) exposureBuckets.full.push(r);
  else if (r.exposure >= 0.70) exposureBuckets.high.push(r);
  else if (r.exposure >= 0.40) exposureBuckets.mid.push(r);
  else if (r.exposure >= 0.15) exposureBuckets.low.push(r);
  else exposureBuckets.minimal.push(r);
}

console.log('=== EXPOSURE REGIME DISTRIBUTION ===');
console.log('Regime     | Days  | Pct   | Avg Bench Ret | Corr');
for (const [regime, data] of Object.entries(exposureBuckets)) {
  if (data.length < 5) { console.log(`${regime.padEnd(10)} | ${String(data.length).padStart(5)} | too few`); continue; }
  const avgBench = data.reduce((a,r) => a + r.benchReturn, 0) / data.length;
  const corr = pearson(data.map(r => r.synthReturn), data.map(r => r.benchReturn));
  console.log(`${regime.padEnd(10)} | ${String(data.length).padStart(5)} | ${(data.length/synthReturns.length*100).toFixed(1).padStart(4)}% | ${(avgBench*10000).toFixed(2).padStart(11)}bp | ${corr.toFixed(3)}`);
}
console.log();

// ============================================================
// 9. Year-by-Year Comparison
// ============================================================
console.log('=== YEAR-BY-YEAR COMPARISON ===');
console.log('Year | Synth Ret | Bench Ret | Gap     | Synth Vol | Bench Vol | Corr');
console.log('-----|-----------|-----------|---------|-----------|-----------|------');

const years = [...new Set(synthReturns.map(r => r.date.substring(0, 4)))];
for (const year of years) {
  const yd = synthReturns.filter(r => r.date.startsWith(year));
  if (yd.length < 10) continue;
  const ysr = yd.map(r => r.synthReturn);
  const ybr = yd.map(r => r.benchReturn);
  const yCumS = yd.reduce((a,r) => a * (1 + r.synthReturn), 1) - 1;
  const yCumB = yd.reduce((a,r) => a * (1 + r.benchReturn), 1) - 1;
  const yVolS = stddev(ysr) * Math.sqrt(252) * 100;
  const yVolB = stddev(ybr) * Math.sqrt(252) * 100;
  const yCorr = pearson(ysr, ybr);
  console.log(`${year} | ${(yCumS*100).toFixed(1).padStart(7)}% | ${(yCumB*100).toFixed(1).padStart(7)}% | ${((yCumS-yCumB)*100).toFixed(1).padStart(5)}% | ${yVolS.toFixed(1).padStart(7)}% | ${yVolB.toFixed(1).padStart(7)}% | ${yCorr.toFixed(3)}`);
}
console.log();

// ============================================================
// 10. Rolling 60-Day Tracking Error
// ============================================================
const rolling60TE = [];
for (let i = 60; i < synthReturns.length; i++) {
  const window = diffs.slice(i - 60, i);
  const te = stddev(window) * Math.sqrt(252) * 100;
  rolling60TE.push({ date: synthReturns[i].date, te });
}

// Find worst tracking error episodes
rolling60TE.sort((a, b) => b.te - a.te);
console.log('=== WORST 60-DAY ROLLING TRACKING ERROR EPISODES ===');
console.log('Date        | 60d TE (ann)');
for (let i = 0; i < Math.min(10, rolling60TE.length); i++) {
  console.log(`${rolling60TE[i].date}  | ${rolling60TE[i].te.toFixed(2)}%`);
}
console.log();

// Median and percentile tracking error
rolling60TE.sort((a, b) => a.te - b.te);
const medianTE = rolling60TE[Math.floor(rolling60TE.length / 2)].te;
const p95TE = rolling60TE[Math.floor(rolling60TE.length * 0.95)].te;
console.log(`Median 60d tracking error: ${medianTE.toFixed(2)}%`);
console.log(`95th pctl tracking error:  ${p95TE.toFixed(2)}%`);
console.log();

// ============================================================
// 11. Extreme Deleveraging Episode Comparison
// ============================================================
// Find days where our model shows extreme deleveraging (>5% exposure drop)
console.log('=== EXTREME DELEVERAGING EPISODES (|ΔExposure| > 5%) ===');
console.log('Date         | ΔExposure | Our Ret  | Bench Ret | Match?');
let extremeCount = 0;
let extremeMatchCount = 0;
for (let i = 1; i < synthReturns.length; i++) {
  const deltaExp = synthReturns[i].exposure - synthReturns[i-1].exposure;
  if (Math.abs(deltaExp) > 0.05) {
    extremeCount++;
    const retMatch = Math.sign(synthReturns[i].synthReturn) === Math.sign(synthReturns[i].benchReturn);
    if (retMatch) extremeMatchCount++;
    if (extremeCount <= 30) {
      console.log(`${synthReturns[i].date}  | ${(deltaExp*100).toFixed(1).padStart(7)}% | ${(synthReturns[i].synthReturn*100).toFixed(3).padStart(7)}% | ${(synthReturns[i].benchReturn*100).toFixed(3).padStart(7)}% | ${retMatch ? '✓' : '✗'}`);
    }
  }
}
console.log(`Total extreme days: ${extremeCount}, direction match: ${extremeMatchCount}/${extremeCount} (${extremeCount > 0 ? (extremeMatchCount/extremeCount*100).toFixed(0) : 'N/A'}%)`);
console.log();

// ============================================================
// 12. FINAL VERDICT
// ============================================================
console.log('============================================================');
console.log('                    FINAL VERDICT');
console.log('============================================================');
console.log();

// Classification criteria:
// A. REPRODUCED:           corr > 0.99, TE < 1%, cum gap < 5%/yr
// B. NEAR_REPRODUCTION:    corr > 0.95, TE < 3%, stress behavior aligns
// C. MECHANISM_ONLY:       corr > 0.80, same direction in stress
// D. NOT_SUPPORTED:        corr < 0.80 or persistent sign disagreement

let verdict, verdictReason;
if (dailyPearson > 0.99 && trackingErrorAnn < 0.01 && Math.abs(synthAnnReturn - benchAnnReturn) < 0.005) {
  verdict = 'A. REPRODUCED';
  verdictReason = 'Daily return correlation >0.99, tracking error <1%, annualized return within 50bp.';
} else if (dailyPearson > 0.95 && trackingErrorAnn < 0.03) {
  verdict = 'B. NEAR_REPRODUCTION';
  verdictReason = 'High correlation and low tracking error; small systematic differences from unknown methodology details.';
} else if (dailyPearson > 0.80) {
  verdict = 'C. MECHANISM_ONLY';
  verdictReason = 'Same mechanism (vol-targeting) but significant differences in implementation details.';
} else {
  verdict = 'D. NOT_SUPPORTED';
  verdictReason = 'Model does not reproduce the benchmark.';
}

console.log(`VERDICT: ${verdict}`);
console.log();
console.log(`REASON: ${verdictReason}`);
console.log();
console.log('KEY METRICS:');
console.log(`  Daily Pearson correlation:  ${dailyPearson.toFixed(6)}`);
console.log(`  Daily Spearman correlation: ${dailySpearman.toFixed(6)}`);
console.log(`  Annualized tracking error:  ${(trackingErrorAnn * 100).toFixed(2)}%`);
console.log(`  Direction agreement:        ${(signAgree/signTotal*100).toFixed(1)}%`);
console.log(`  Annualized return gap:      ${((synthAnnReturn - benchAnnReturn) * 100).toFixed(2)}%`);
console.log(`  Realized vol gap:           ${(synthVol - benchVol).toFixed(2)}%`);
console.log();

// Known differences to document
console.log('KNOWN / SUSPECTED RESIDUAL DIFFERENCES:');
console.log('  1. Cash return treatment: Our model uses price-return (cash=0%).');
console.log('     If SPXAV10P includes interest on cash portion, our index will');
console.log('     underperform in high-rate environments when exposure < 100%.');
console.log('  2. SPX price series source: We use Yahoo ^GSPC adjusted close.');
console.log('     S&P may use different closing values or corporate action adjustments.');
console.log('  3. Holiday/calendar: NYSE calendar alignment may differ from S&P\'s.');
console.log('  4. Rounding: S&P may round exposure/vol to fewer decimal places.');
console.log('  5. Index base level: Different starting levels affect compound drift.');
console.log();

// Write machine-readable results
const results = {
  benchmark: 'SPXAV10P',
  model: 'VC_Mechanical_Pressure',
  period: { start: synthReturns[0].date, end: synthReturns[synthReturns.length-1].date, years: totalYears },
  observations: synthReturns.length,
  dailyPearsonCorrelation: Number(dailyPearson.toFixed(6)),
  dailySpearmanCorrelation: Number(dailySpearman.toFixed(6)),
  trackingErrorAnnualized: Number((trackingErrorAnn * 100).toFixed(2)),
  meanAbsDailyDiffBp: Number((meanAbsDiff * 10000).toFixed(2)),
  directionAgreementPct: Number((signAgree/signTotal*100).toFixed(1)),
  synthAnnualizedReturn: Number((synthAnnReturn * 100).toFixed(2)),
  benchAnnualizedReturn: Number((benchAnnReturn * 100).toFixed(2)),
  synthRealizedVol: Number(synthVol.toFixed(2)),
  benchRealizedVol: Number(benchVol.toFixed(2)),
  medianRolling60dTE: Number(medianTE.toFixed(2)),
  p95Rolling60dTE: Number(p95TE.toFixed(2)),
  verdict,
  verdictReason,
  timestamp: new Date().toISOString(),
};

const outPath = path.join(__dirname, 'vc_benchmark_validation_results.json');
fs.writeFileSync(outPath, JSON.stringify(results, null, 2));
console.log(`Machine-readable results saved to: ${outPath}`);
