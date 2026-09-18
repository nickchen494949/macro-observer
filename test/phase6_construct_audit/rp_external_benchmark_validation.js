#!/usr/bin/env node
/**
 * RP External Reality Validation
 * ===============================
 * Compares our 2-asset RP Mechanical Pressure model against:
 *   - RPAR ETF (RPAR Risk Parity ETF) — a real, traded multi-asset RP product
 *
 * KEY DIFFERENCE FROM VC VALIDATION:
 *   VC was a 1:1 benchmark replication (same underlying, same rules).
 *   RP is a MECHANISM PROXY validation:
 *     - Our model: 2 assets (SPX equity + DGS10 bond proxy, D=8)
 *     - RPAR: Multi-asset (equities, long Treasuries, TIPS, gold/commodities)
 *     - We do NOT expect daily return correlation >0.99
 *     - We DO expect: directional agreement during stress, leverage regime correlation,
 *       and co-movement of risk exposures during vol shocks
 *
 * WHAT WE'RE REALLY ASKING:
 *   "When the real RP world is deleveraging, does our simplified model also deleverage?"
 *   "Does our model-implied portfolio vol track real-world RP implied vol?"
 *
 * OUTPUT: Structured validation report
 */

'use strict';
const fs = require('fs');
const path = require('path');
const { computeRpSnapshot, buildAlignedReturns, DEFAULT_CONFIG } = require('../../lib/rp_mechanical');

const PROJECT = path.resolve(__dirname, '../..');

// ============================================================
// 1. Load Data
// ============================================================
const spxRaw = JSON.parse(fs.readFileSync(path.join(PROJECT, 'data/yahoo/_GSPC.json'), 'utf-8'));
const dgs10Raw = JSON.parse(fs.readFileSync(path.join(PROJECT, 'data/fred/DGS10.json'), 'utf-8'));
const rparRaw = JSON.parse(fs.readFileSync(path.join(PROJECT, 'data/benchmark/RPAR.json'), 'utf-8'));

// Build RPAR date→price map
const rparMap = new Map();
for (const pt of rparRaw.values) {
  if (pt[1] != null && !isNaN(pt[1]) && pt[1] > 0) rparMap.set(pt[0], pt[1]);
}
const rparDates = [...rparMap.keys()].sort();

console.log('=== DATA SUMMARY ===');
console.log(`RPAR: ${rparDates.length} obs (${rparDates[0]} to ${rparDates[rparDates.length-1]})`);

// ============================================================
// 2. Build RP Model Time Series
// ============================================================
// We need to build a FULL time series of RP snapshots, not just today's.
// Use buildAlignedReturns for the common date set, then slide the window.

const { dates: alignedDates, eqReturns, bondReturns } = buildAlignedReturns(
  spxRaw.values, dgs10Raw.values, DEFAULT_CONFIG.bondDuration
);

console.log(`Aligned returns: ${alignedDates.length} dates (${alignedDates[0]} to ${alignedDates[alignedDates.length-1]})`);

// Build daily RP snapshots for every date where we have enough history
const rpSnapshots = new Map(); // date → snapshot
const minLookback = Math.max(DEFAULT_CONFIG.allocLookback, DEFAULT_CONFIG.riskLookback); // 60

for (let t = minLookback; t < alignedDates.length; t++) {
  const eqSlice = eqReturns.slice(0, t + 1); // returns up to and including day t
  const bondSlice = bondReturns.slice(0, t + 1);
  
  const snap = computeRpSnapshot(eqSlice, bondSlice, DEFAULT_CONFIG);
  if (snap) {
    rpSnapshots.set(alignedDates[t], {
      ...snap,
      date: alignedDates[t],
    });
  }
}

console.log(`RP snapshots computed: ${rpSnapshots.size}`);

// ============================================================
// 3. Build Comparison Dataset
// ============================================================
// For each RPAR trading day, compute:
//   - RPAR daily return
//   - RPAR realized vol (rolling 20d, 60d)
//   - Our model leverage, portfolio vol, equity/bond weights
//   - Our model leverage change (ΔL)

const rparDateSet = new Set(rparDates);
const rpDateSet = new Set([...rpSnapshots.keys()]);

// Common dates with both RPAR and our model
const commonDates = rparDates.filter(d => rpDateSet.has(d));
console.log(`Common dates (RPAR ∩ RP model): ${commonDates.length} (${commonDates[0]} to ${commonDates[commonDates.length-1]})`);
console.log();

// Build comparison arrays
const comparison = [];
for (let i = 1; i < commonDates.length; i++) {
  const d = commonDates[i];
  const dPrev = commonDates[i-1];
  
  const rparPrice = rparMap.get(d);
  const rparPricePrev = rparMap.get(dPrev);
  if (!rparPrice || !rparPricePrev || rparPrice <= 0 || rparPricePrev <= 0) continue;
  
  const rparReturn = rparPrice / rparPricePrev - 1;
  
  const rpSnap = rpSnapshots.get(d);
  const rpSnapPrev = rpSnapshots.get(dPrev);
  if (!rpSnap || !rpSnapPrev) continue;
  
  const leverageChange = rpSnap.targetLeverage - rpSnapPrev.targetLeverage;
  const eqExpChange = rpSnap.eqGrossExposure - rpSnapPrev.eqGrossExposure;
  const bondExpChange = rpSnap.bondGrossExposure - rpSnapPrev.bondGrossExposure;
  
  // Synthetic RP portfolio return (using model weights & leverage)
  // Find this date in aligned returns
  const alignedIdx = alignedDates.indexOf(d);
  const synthReturn = alignedIdx >= 0
    ? rpSnap.targetLeverage * (rpSnap.equityWeight * eqReturns[alignedIdx] + rpSnap.bondWeight * bondReturns[alignedIdx])
    : null;
  
  comparison.push({
    date: d,
    rparReturn,
    synthReturn,
    leverage: rpSnap.targetLeverage,
    leveragePrev: rpSnapPrev.targetLeverage,
    leverageChange,
    portfolioVol: rpSnap.portfolioVol,
    eqWeight: rpSnap.equityWeight,
    bondWeight: rpSnap.bondWeight,
    eqGross: rpSnap.eqGrossExposure,
    bondGross: rpSnap.bondGrossExposure,
    eqExpChange,
    bondExpChange,
    stockBondCorr: rpSnap.stockBondCorrelation,
  });
}

console.log(`Comparison observations: ${comparison.length}`);
console.log();

// ============================================================
// 4. Statistical Helpers
// ============================================================
function pearson(x, y) {
  const n = x.length;
  const mx = x.reduce((a,b)=>a+b,0)/n;
  const my = y.reduce((a,b)=>a+b,0)/n;
  let num=0,dx2=0,dy2=0;
  for(let i=0;i<n;i++){const dx=x[i]-mx;const dy=y[i]-my;num+=dx*dy;dx2+=dx*dx;dy2+=dy*dy;}
  return dx2>0 && dy2>0 ? num/(Math.sqrt(dx2)*Math.sqrt(dy2)) : 0;
}
function stddev(arr) {
  const n=arr.length;if(n<2)return 0;
  const m=arr.reduce((a,b)=>a+b,0)/n;
  return Math.sqrt(arr.reduce((a,b)=>a+(b-m)**2,0)/(n-1));
}

// ============================================================
// 5. RPAR Realized Vol (Proxy for Real-World RP Portfolio Vol)
// ============================================================
// Compute rolling 20d and 60d realized vol of RPAR returns
const rparReturns = comparison.map(c => c.rparReturn);
const rollingRparVol20 = [];
const rollingRparVol60 = [];
const rollingModelVol = []; // our model's portfolio vol

for (let i = 0; i < comparison.length; i++) {
  if (i >= 20) {
    const window = rparReturns.slice(i - 20, i);
    rollingRparVol20.push(stddev(window) * Math.sqrt(252));
  } else {
    rollingRparVol20.push(null);
  }
  if (i >= 60) {
    const window = rparReturns.slice(i - 60, i);
    rollingRparVol60.push(stddev(window) * Math.sqrt(252));
  } else {
    rollingRparVol60.push(null);
  }
  rollingModelVol.push(comparison[i].portfolioVol);
}

// Correlation between RPAR realized vol and our model's portfolio vol
const vol20Pairs = [];
const vol60Pairs = [];
for (let i = 0; i < comparison.length; i++) {
  if (rollingRparVol20[i] != null) vol20Pairs.push([rollingRparVol20[i], rollingModelVol[i]]);
  if (rollingRparVol60[i] != null) vol60Pairs.push([rollingRparVol60[i], rollingModelVol[i]]);
}

const volCorr20 = pearson(vol20Pairs.map(p=>p[0]), vol20Pairs.map(p=>p[1]));
const volCorr60 = pearson(vol60Pairs.map(p=>p[0]), vol60Pairs.map(p=>p[1]));

console.log('=== PORTFOLIO VOL CORRELATION ===');
console.log(`Our model vol vs RPAR 20d realized vol: ${volCorr20.toFixed(4)}`);
console.log(`Our model vol vs RPAR 60d realized vol: ${volCorr60.toFixed(4)}`);
console.log();

// ============================================================
// 6. Leverage Regime Analysis
// ============================================================
// When our model says "deleverage", does RPAR also drop?
// When our model says "leverage up", does RPAR also rise?

// Classify our model's daily regime
let delevDaysOurs = 0, levDaysOurs = 0, neutralDaysOurs = 0;
let delevMatchRP = 0, levMatchRP = 0;
let delevDaysTotal = 0, levDaysTotal = 0;

for (const c of comparison) {
  const dir = c.leverageChange < -0.01 ? 'delev' : (c.leverageChange > 0.01 ? 'lever' : 'neutral');
  if (dir === 'delev') {
    delevDaysOurs++;
    // Did RPAR also have a negative return that day? (simple directional check)
    if (c.rparReturn < 0) delevMatchRP++;
    delevDaysTotal++;
  } else if (dir === 'lever') {
    levDaysOurs++;
    if (c.rparReturn > 0) levMatchRP++;
    levDaysTotal++;
  } else {
    neutralDaysOurs++;
  }
}

console.log('=== LEVERAGE REGIME DIRECTIONAL CHECK ===');
console.log(`Model deleverage days: ${delevDaysOurs} / ${comparison.length} (${(delevDaysOurs/comparison.length*100).toFixed(1)}%)`);
console.log(`Model leveraging days: ${levDaysOurs} / ${comparison.length} (${(levDaysOurs/comparison.length*100).toFixed(1)}%)`);
console.log(`Model neutral days:    ${neutralDaysOurs} / ${comparison.length} (${(neutralDaysOurs/comparison.length*100).toFixed(1)}%)`);
console.log();

// ============================================================
// 7. Rolling Leverage Correlation with RPAR Returns
// ============================================================
// Key test: does our model leverage LEVEL correlate with RPAR behavior?
// When we say leverage is low → RPAR should have lower vol
// When we say leverage is high → RPAR should have higher vol

// Test: rolling 20d correlation between our leverage and RPAR 20d vol
const rollingLevVolCorr = [];
for (let i = 20; i < comparison.length; i++) {
  const levWindow = comparison.slice(i-20, i).map(c => c.leverage);
  const rparVolWindow = rollingRparVol20.slice(i-20, i);
  if (rparVolWindow.some(v => v == null)) continue;
  // Our leverage should be INVERSELY correlated with RPAR vol
  // (higher vol → lower leverage from target-vol mechanism)
  const corr = pearson(levWindow, rparVolWindow);
  rollingLevVolCorr.push({ date: comparison[i].date, corr });
}

const avgLevVolCorr = rollingLevVolCorr.reduce((a,c) => a + c.corr, 0) / rollingLevVolCorr.length;
console.log('=== LEVERAGE vs RPAR REALIZED VOL ===');
console.log(`Average rolling 20d correlation (leverage vs RPAR vol): ${avgLevVolCorr.toFixed(4)}`);
console.log(`Expected: NEGATIVE (higher RPAR vol → model should reduce leverage)`);
console.log();

// ============================================================
// 8. Stress Period Analysis
// ============================================================
const stressPeriods = [
  { name: 'COVID Crash', start: '2020-02-19', end: '2020-03-23' },
  { name: 'COVID Recovery', start: '2020-03-24', end: '2020-06-30' },
  { name: '2022 Bear Start', start: '2022-01-03', end: '2022-06-16' },
  { name: '2022 Stocks+Bonds', start: '2022-08-15', end: '2022-10-15' },
  { name: '2022 Bear Recovery', start: '2022-10-12', end: '2023-01-31' },
  { name: 'SVB Crisis', start: '2023-03-08', end: '2023-03-20' },
  { name: 'Aug 2024 Unwind', start: '2024-07-15', end: '2024-08-15' },
  { name: 'April 2025 Tariff', start: '2025-04-01', end: '2025-04-15' },
];

console.log('=== STRESS PERIOD ANALYSIS ===');
console.log('Period               | RPAR Ret | Synth Ret | Lev Start | Lev End | ΔLev  | Corr');
console.log('---------------------|----------|-----------|-----------|---------|-------|------');

for (const sp of stressPeriods) {
  const periodData = comparison.filter(c => c.date >= sp.start && c.date <= sp.end);
  if (periodData.length < 3) {
    console.log(`${sp.name.padEnd(20)} | insufficient data`);
    continue;
  }
  
  const pRpar = periodData.reduce((a,c) => a * (1 + c.rparReturn), 1) - 1;
  const pSynth = periodData.filter(c => c.synthReturn != null).reduce((a,c) => a * (1 + c.synthReturn), 1) - 1;
  const levStart = periodData[0].leverage;
  const levEnd = periodData[periodData.length-1].leverage;
  const deltaLev = levEnd - levStart;
  
  const rr = periodData.map(c => c.rparReturn);
  const sr = periodData.filter(c => c.synthReturn != null).map(c => c.synthReturn);
  const corr = sr.length >= 3 ? pearson(rr.slice(0, sr.length), sr) : NaN;
  
  console.log(`${sp.name.padEnd(20)} | ${(pRpar*100).toFixed(1).padStart(6)}% | ${(pSynth*100).toFixed(1).padStart(7)}% | ${levStart.toFixed(2).padStart(9)} | ${levEnd.toFixed(2).padStart(7)} | ${(deltaLev>=0?'+':'')+deltaLev.toFixed(2).padStart(4)} | ${isNaN(corr) ? 'N/A' : corr.toFixed(3)}`);
}
console.log();

// ============================================================
// 9. Daily Return Correlation (Expected to be modest)
// ============================================================
const validSynthReturns = comparison.filter(c => c.synthReturn != null);
const rr = validSynthReturns.map(c => c.rparReturn);
const sr = validSynthReturns.map(c => c.synthReturn);

const dailyPearson = pearson(rr, sr);
const dailyDiffs = rr.map((r, i) => r - sr[i]);
const trackingErrorAnn = stddev(dailyDiffs) * Math.sqrt(252);

// Sign agreement
let signAgree = 0, signTotal = 0;
for (const c of validSynthReturns) {
  if (c.rparReturn === 0 || c.synthReturn === 0) continue;
  signTotal++;
  if (Math.sign(c.rparReturn) === Math.sign(c.synthReturn)) signAgree++;
}

console.log('=== DAILY RETURN COMPARISON ===');
console.log(`Pearson correlation:  ${dailyPearson.toFixed(4)}`);
console.log(`Tracking error (ann): ${(trackingErrorAnn * 100).toFixed(2)}%`);
console.log(`Direction agreement:  ${signAgree}/${signTotal} (${(signAgree/signTotal*100).toFixed(1)}%)`);
console.log();

// ============================================================
// 10. Cumulative Performance
// ============================================================
const totalYears = (new Date(validSynthReturns[validSynthReturns.length-1].date) - new Date(validSynthReturns[0].date)) / (365.25*86400000);
const cumRpar = validSynthReturns.reduce((a,c) => a * (1+c.rparReturn), 1) - 1;
const cumSynth = validSynthReturns.reduce((a,c) => a * (1+c.synthReturn), 1) - 1;
const annRpar = Math.pow(1+cumRpar, 1/totalYears) - 1;
const annSynth = Math.pow(1+cumSynth, 1/totalYears) - 1;
const rparVol = stddev(rr) * Math.sqrt(252) * 100;
const synthVol = stddev(sr) * Math.sqrt(252) * 100;

console.log('=== CUMULATIVE PERFORMANCE ===');
console.log(`Period: ${validSynthReturns[0].date} to ${validSynthReturns[validSynthReturns.length-1].date} (${totalYears.toFixed(1)} years)`);
console.log(`RPAR cum: ${(cumRpar*100).toFixed(2)}% (ann: ${(annRpar*100).toFixed(2)}%)`);
console.log(`Model cum: ${(cumSynth*100).toFixed(2)}% (ann: ${(annSynth*100).toFixed(2)}%)`);
console.log(`RPAR vol: ${rparVol.toFixed(2)}%`);
console.log(`Model vol: ${synthVol.toFixed(2)}%`);
console.log();

// ============================================================
// 11. Year-by-Year Comparison
// ============================================================
console.log('=== YEAR-BY-YEAR ===');
console.log('Year | RPAR Ret | Model Ret | RPAR Vol | Model Vol | Corr  | Dir Agree');
console.log('-----|----------|-----------|----------|-----------|-------|----------');
const years = [...new Set(validSynthReturns.map(c => c.date.substring(0,4)))];
for (const y of years) {
  const yd = validSynthReturns.filter(c => c.date.startsWith(y));
  if (yd.length < 10) continue;
  const yCumR = yd.reduce((a,c) => a*(1+c.rparReturn),1)-1;
  const yCumS = yd.reduce((a,c) => a*(1+c.synthReturn),1)-1;
  const yVolR = stddev(yd.map(c=>c.rparReturn)) * Math.sqrt(252) * 100;
  const yVolS = stddev(yd.map(c=>c.synthReturn)) * Math.sqrt(252) * 100;
  const yCorr = pearson(yd.map(c=>c.rparReturn), yd.map(c=>c.synthReturn));
  let yAgree = 0, yTotal = 0;
  for (const c of yd) { if(c.rparReturn!==0&&c.synthReturn!==0){yTotal++;if(Math.sign(c.rparReturn)===Math.sign(c.synthReturn))yAgree++;}}
  console.log(`${y} | ${(yCumR*100).toFixed(1).padStart(6)}% | ${(yCumS*100).toFixed(1).padStart(7)}% | ${yVolR.toFixed(1).padStart(6)}% | ${yVolS.toFixed(1).padStart(7)}% | ${yCorr.toFixed(3)} | ${(yAgree/yTotal*100).toFixed(0)}%`);
}
console.log();

// ============================================================
// 12. CRITICAL TEST: Deleverage Event Detection
// ============================================================
// When our model shows significant deleveraging (ΔL < -0.05),
// how does RPAR behave in the surrounding window?

console.log('=== SIGNIFICANT DELEVERAGING EVENTS (ΔLev < -0.05 over 5d) ===');
console.log('Date         | ΔLev(5d) | RPAR 5d Ret | Model Lev | Model PortVol | Same Dir?');

let bigDelevCount = 0, bigDelevMatch = 0;
for (let i = 5; i < comparison.length; i++) {
  const deltaLev5d = comparison[i].leverage - comparison[i-5].leverage;
  if (deltaLev5d < -0.05) {
    bigDelevCount++;
    // RPAR 5-day return
    const rpar5dRet = comparison.slice(i-4, i+1).reduce((a,c) => a * (1+c.rparReturn), 1) - 1;
    const sameDir = rpar5dRet < 0; // expect negative during deleveraging
    if (sameDir) bigDelevMatch++;
    
    if (bigDelevCount <= 30) {
      console.log(`${comparison[i].date}  | ${(deltaLev5d).toFixed(3).padStart(7)} | ${(rpar5dRet*100).toFixed(2).padStart(9)}% | ${comparison[i].leverage.toFixed(2).padStart(9)} | ${(comparison[i].portfolioVol*100).toFixed(1).padStart(11)}% | ${sameDir ? '✓' : '✗'}`);
    }
  }
}
console.log(`Total: ${bigDelevCount} events, RPAR also negative: ${bigDelevMatch}/${bigDelevCount} (${bigDelevCount > 0 ? (bigDelevMatch/bigDelevCount*100).toFixed(0) : 'N/A'}%)`);
console.log();

// ============================================================
// 13. Stock-Bond Correlation Regime Analysis
// ============================================================
// When stock-bond correlation flips, does RPAR behavior change?
const corrBuckets = { negative: [], near_zero: [], positive: [] };
for (const c of comparison) {
  if (c.stockBondCorr < -0.1) corrBuckets.negative.push(c);
  else if (c.stockBondCorr > 0.1) corrBuckets.positive.push(c);
  else corrBuckets.near_zero.push(c);
}

console.log('=== STOCK-BOND CORRELATION REGIME ===');
console.log('Regime    | Days | Model Avg Lev | Model Avg PortVol | RPAR Avg Vol | Dir Agree');
for (const [regime, data] of Object.entries(corrBuckets)) {
  if (data.length < 20) continue;
  const avgLev = data.reduce((a,c) => a + c.leverage, 0) / data.length;
  const avgPortVol = data.reduce((a,c) => a + c.portfolioVol, 0) / data.length;
  const rparVol20 = stddev(data.map(c => c.rparReturn)) * Math.sqrt(252);
  let agree = 0, total = 0;
  const synthData = data.filter(c => c.synthReturn != null);
  for (const c of synthData) { if(c.rparReturn!==0&&c.synthReturn!==0){total++;if(Math.sign(c.rparReturn)===Math.sign(c.synthReturn))agree++;}}
  console.log(`${regime.padEnd(9)} | ${String(data.length).padStart(4)} | ${avgLev.toFixed(2).padStart(13)} | ${(avgPortVol*100).toFixed(1).padStart(15)}% | ${(rparVol20*100).toFixed(1).padStart(10)}% | ${total>0?(agree/total*100).toFixed(0):'-'}%`);
}
console.log();

// ============================================================
// 14. FINAL VERDICT
// ============================================================
console.log('============================================================');
console.log('                    FINAL VERDICT');
console.log('============================================================');
console.log();

// Classification for RP (different criteria than VC):
// A. MECHANISM_VALIDATED:    vol corr > 0.6, stress direction match > 70%, daily corr > 0.5
// B. DIRECTIONALLY_USEFUL:  vol corr > 0.4, stress direction match > 60%
// C. WEAK_PROXY:            some alignment but large gaps
// D. NOT_SUPPORTED:         no meaningful alignment

let verdict, verdictReason;
const stressCorrs = []; // collect stress period correlations

if (volCorr60 > 0.6 && dailyPearson > 0.5 && signAgree/signTotal > 0.7) {
  verdict = 'A. MECHANISM_VALIDATED';
  verdictReason = 'Strong vol correlation, daily return agreement, and directional consistency with real RP product.';
} else if (volCorr60 > 0.4 && dailyPearson > 0.3 && signAgree/signTotal > 0.6) {
  verdict = 'B. DIRECTIONALLY_USEFUL';
  verdictReason = 'Model captures major risk-on/risk-off regime shifts. 2-asset simplification creates expected return gaps.';
} else if (dailyPearson > 0.2 || volCorr60 > 0.3) {
  verdict = 'C. WEAK_PROXY';
  verdictReason = 'Some alignment but significant gaps from 2-asset limitation.';
} else {
  verdict = 'D. NOT_SUPPORTED';
  verdictReason = 'Insufficient alignment with real-world RP product.';
}

console.log(`VERDICT: ${verdict}`);
console.log();
console.log(`REASON: ${verdictReason}`);
console.log();
console.log('KEY METRICS:');
console.log(`  Daily Pearson correlation:         ${dailyPearson.toFixed(4)}`);
console.log(`  Direction agreement:               ${(signAgree/signTotal*100).toFixed(1)}%`);
console.log(`  Model vol vs RPAR 20d vol corr:    ${volCorr20.toFixed(4)}`);
console.log(`  Model vol vs RPAR 60d vol corr:    ${volCorr60.toFixed(4)}`);
console.log(`  Lev-vol inverse correlation:       ${avgLevVolCorr.toFixed(4)}`);
console.log(`  Big delev event RPAR match:        ${bigDelevCount > 0 ? (bigDelevMatch/bigDelevCount*100).toFixed(0) : 'N/A'}%`);
console.log();
console.log('KNOWN LIMITATIONS:');
console.log('  1. 2-asset model omits commodities, TIPS, and gold (RPAR has all four)');
console.log('  2. Bond proxy (D=8 × ΔYield) differs from actual Treasury total returns');
console.log('  3. Our model targets 10% vol; RPAR may target different vol or use different');
console.log('     risk budgeting methodology');
console.log('  4. RPAR rebalances monthly; our model computes daily');
console.log('  5. Stock-bond correlation regimes (2022 positive corr) stress our 2-asset model');
console.log();

// Save results
const results = {
  benchmark: 'RPAR',
  model: 'RP_Mechanical_Pressure',
  period: { start: validSynthReturns[0].date, end: validSynthReturns[validSynthReturns.length-1].date, years: totalYears },
  observations: comparison.length,
  dailyPearsonCorrelation: Number(dailyPearson.toFixed(4)),
  directionAgreementPct: Number((signAgree/signTotal*100).toFixed(1)),
  trackingErrorAnnualized: Number((trackingErrorAnn * 100).toFixed(2)),
  modelVolVsRparVol20Corr: Number(volCorr20.toFixed(4)),
  modelVolVsRparVol60Corr: Number(volCorr60.toFixed(4)),
  leverageVolInverseCorr: Number(avgLevVolCorr.toFixed(4)),
  bigDelevEvents: bigDelevCount,
  bigDelevRparMatchPct: bigDelevCount > 0 ? Number((bigDelevMatch/bigDelevCount*100).toFixed(1)) : null,
  rparAnnReturn: Number((annRpar*100).toFixed(2)),
  modelAnnReturn: Number((annSynth*100).toFixed(2)),
  rparRealizedVol: Number(rparVol.toFixed(2)),
  modelRealizedVol: Number(synthVol.toFixed(2)),
  verdict,
  verdictReason,
  timestamp: new Date().toISOString(),
};

const outPath = path.join(__dirname, 'rp_benchmark_validation_results.json');
fs.writeFileSync(outPath, JSON.stringify(results, null, 2));
console.log(`Machine-readable results saved to: ${outPath}`);
