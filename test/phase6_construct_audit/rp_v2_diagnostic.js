#!/usr/bin/env node
/**
 * Phase 6.7 — Reduced Risk Parity Mechanical Model
 * 
 * Computes a 2-asset (SPX + 10Y Treasury) RP model with:
 *   Layer 1: Inverse-vol relative weights (same as V1)
 *   Layer 2: Portfolio covariance & volatility
 *   Layer 3: Target-vol implied leverage
 *   Layer 4: Mechanical deleveraging pressure
 * 
 * Runs over the full available history to produce a daily time series
 * comparing V1 (no leverage) with V2 (with leverage).
 */

const fs = require('fs');
const path = require('path');

// --- CONFIG (ASSUMPTIONS — NOT VERIFIED) ---
const CONFIG = {
  volLookback: 20,          // days for inverse-vol weights
  corrLookback: 60,         // days for correlation/covariance
  bondDuration: 8,          // modified duration for 10Y Treasury
  targetPortfolioVol: 0.10, // 10% annualized — ASSUMPTION, S&P RP 10% reference
  leverageCap: 3.0,         // max leverage — ASSUMPTION, conservative cap
  leverageFloor: 0.2,       // min leverage — avoid going below 20%
  annFactor: Math.sqrt(252),
  warmup: 65,               // need at least corrLookback + 5 days
};

// --- LOAD DATA ---
const spxRaw = JSON.parse(fs.readFileSync(path.join(__dirname, '../../data/yahoo/_GSPC.json'), 'utf-8'));
const dgsRaw = JSON.parse(fs.readFileSync(path.join(__dirname, '../../data/fred/DGS10.json'), 'utf-8'));
const spxData = spxRaw.values; // [[date, close, ...], ...]
const dgsData = (dgsRaw.values || dgsRaw.observations); // [[date, value, ...], ...]

// --- ALIGN DATA ---
// Build date-indexed maps
// SPX data format is mixed: most entries are [date, {adjClose, close, ...}], last few are [date, number]
const spxMap = new Map();
spxData.forEach(pt => {
  const val = pt[1];
  if (val == null) return;
  const price = typeof val === 'object' ? (val.adjClose || val.close) : val;
  if (price != null && !isNaN(price)) spxMap.set(pt[0], price);
});
const dgsMap = new Map();
dgsData.forEach(pt => { if (pt[1] != null && !isNaN(pt[1])) dgsMap.set(pt[0], pt[1]); });

// Find common dates
const allSpxDates = [...spxMap.keys()].sort();
const commonDates = allSpxDates.filter(d => dgsMap.has(d));
console.log(`Common dates: ${commonDates.length} (${commonDates[0]} to ${commonDates[commonDates.length-1]})`);

// Build aligned return arrays
const eqPrices = commonDates.map(d => spxMap.get(d));
const bondYields = commonDates.map(d => dgsMap.get(d));

// Daily returns
const eqReturns = [];  // log returns
const bondReturns = []; // -D * ΔY / 100
for (let i = 1; i < commonDates.length; i++) {
  eqReturns.push(Math.log(eqPrices[i] / eqPrices[i-1]));
  bondReturns.push(-CONFIG.bondDuration * (bondYields[i] - bondYields[i-1]) / 100);
}
const returnDates = commonDates.slice(1);

console.log(`Return series: ${returnDates.length} observations`);

// --- HELPER FUNCTIONS ---
function rollingStats(eqRet, bondRet, volWindow, corrWindow, endIdx) {
  if (endIdx < Math.max(volWindow, corrWindow)) return null;
  
  // Vol (20d)
  const eqSlice = eqRet.slice(endIdx - volWindow, endIdx);
  const bondSlice = bondRet.slice(endIdx - volWindow, endIdx);
  
  const mean = arr => arr.reduce((a,b) => a+b, 0) / arr.length;
  const std = arr => {
    const m = mean(arr);
    const v = arr.reduce((a,b) => a + (b-m)**2, 0) / (arr.length - 1 || 1);
    return Math.sqrt(v);
  };
  
  const eqVol = std(eqSlice) * CONFIG.annFactor;
  const bondVol = std(bondSlice) * CONFIG.annFactor;
  
  // Correlation & covariance (60d)
  const eqCorrSlice = eqRet.slice(endIdx - corrWindow, endIdx);
  const bondCorrSlice = bondRet.slice(endIdx - corrWindow, endIdx);
  const eqMean = mean(eqCorrSlice);
  const bondMean = mean(bondCorrSlice);
  
  let cov = 0, eqVar = 0, bondVar = 0;
  for (let i = 0; i < corrWindow; i++) {
    const de = eqCorrSlice[i] - eqMean;
    const db = bondCorrSlice[i] - bondMean;
    cov += de * db;
    eqVar += de * de;
    bondVar += db * db;
  }
  cov /= (corrWindow - 1);
  eqVar /= (corrWindow - 1);
  bondVar /= (corrWindow - 1);
  
  const corr = (eqVar > 0 && bondVar > 0) ? cov / (Math.sqrt(eqVar) * Math.sqrt(bondVar)) : 0;
  
  // Annualize covariance
  const annCov = cov * 252;
  const annEqVar = eqVar * 252;
  const annBondVar = bondVar * 252;
  
  return { eqVol, bondVol, corr, annCov, annEqVar, annBondVar };
}

function computeRP(stats) {
  if (!stats || stats.eqVol <= 0 || stats.bondVol <= 0) return null;
  
  // Layer 1: Inverse-vol weights (V1 approach)
  const wEq_invVol = (1/stats.eqVol) / (1/stats.eqVol + 1/stats.bondVol);
  const wBond_invVol = 1 - wEq_invVol;
  
  // Layer 2: Portfolio volatility using full covariance
  // σ_p² = w_eq² * σ_eq² + w_bond² * σ_bond² + 2 * w_eq * w_bond * cov(eq, bond)
  const portVar = wEq_invVol**2 * stats.annEqVar 
                + wBond_invVol**2 * stats.annBondVar 
                + 2 * wEq_invVol * wBond_invVol * stats.annCov;
  const portVol = Math.sqrt(Math.max(portVar, 0));
  
  // Layer 3: Target-vol leverage
  let targetLeverage = portVol > 0 ? CONFIG.targetPortfolioVol / portVol : 1;
  targetLeverage = Math.min(targetLeverage, CONFIG.leverageCap);
  targetLeverage = Math.max(targetLeverage, CONFIG.leverageFloor);
  
  // Gross exposures = weight × leverage
  const eqGrossExposure = wEq_invVol * targetLeverage;
  const bondGrossExposure = wBond_invVol * targetLeverage;
  
  return {
    wEq_invVol,
    wBond_invVol,
    portVol,
    corr: stats.corr,
    targetLeverage,
    eqGrossExposure,
    bondGrossExposure,
    totalGrossExposure: eqGrossExposure + bondGrossExposure,
  };
}

// --- MAIN LOOP: compute daily RP model ---
const results = [];
for (let i = CONFIG.warmup; i < returnDates.length; i++) {
  const stats = rollingStats(eqReturns, bondReturns, CONFIG.volLookback, CONFIG.corrLookback, i);
  const rp = computeRP(stats);
  if (!rp) continue;
  
  results.push({
    date: returnDates[i],
    ...rp,
    eqVol: stats.eqVol,
    bondVol: stats.bondVol,
  });
}

console.log(`\nRP model computed for ${results.length} days (${results[0].date} to ${results[results.length-1].date})\n`);

// --- ADD DELTAS ---
for (let i = 1; i < results.length; i++) {
  const prev = results[i-1];
  const curr = results[i];
  curr.leverageChange1d = curr.targetLeverage - prev.targetLeverage;
  curr.eqExposureChange1d = curr.eqGrossExposure - prev.eqGrossExposure;
  curr.bondExposureChange1d = curr.bondGrossExposure - prev.bondGrossExposure;
  
  // Broad deleveraging: BOTH exposures reduced
  curr.broadDeleveraging = (curr.eqExposureChange1d < -0.001 && curr.bondExposureChange1d < -0.001);
  
  // Pressure direction
  if (curr.leverageChange1d < -0.01) curr.pressureDirection = 'deleveraging';
  else if (curr.leverageChange1d > 0.01) curr.pressureDirection = 'leveraging';
  else curr.pressureDirection = 'neutral';
}

// 5-day changes
for (let i = 5; i < results.length; i++) {
  const prev5 = results[i-5];
  const curr = results[i];
  curr.leverageChange5d = curr.targetLeverage - prev5.targetLeverage;
  curr.eqExposureChange5d = curr.eqGrossExposure - prev5.eqGrossExposure;
  curr.bondExposureChange5d = curr.bondGrossExposure - prev5.bondGrossExposure;
  curr.broadDeleveraging5d = (curr.eqExposureChange5d < -0.005 && curr.bondExposureChange5d < -0.005);
}

// --- ANALYSIS ---
console.log('=== SECTION 1: Current State (latest observation) ===\n');
const latest = results[results.length - 1];
console.log(`Date:                  ${latest.date}`);
console.log(`Equity Vol (20d):      ${(latest.eqVol * 100).toFixed(1)}%`);
console.log(`Bond Vol (20d):        ${(latest.bondVol * 100).toFixed(1)}%`);
console.log(`Stock-Bond Corr (60d): ${latest.corr.toFixed(3)}`);
console.log(`Inv-Vol Eq Weight:     ${(latest.wEq_invVol * 100).toFixed(1)}%`);
console.log(`Inv-Vol Bond Weight:   ${(latest.wBond_invVol * 100).toFixed(1)}%`);
console.log(`Portfolio Vol:         ${(latest.portVol * 100).toFixed(2)}%`);
console.log(`Target Leverage:       ${latest.targetLeverage.toFixed(3)}x`);
console.log(`Eq Gross Exposure:     ${(latest.eqGrossExposure * 100).toFixed(1)}%`);
console.log(`Bond Gross Exposure:   ${(latest.bondGrossExposure * 100).toFixed(1)}%`);
console.log(`Total Gross:           ${(latest.totalGrossExposure * 100).toFixed(1)}%`);
console.log(`Leverage Chg 1d:       ${latest.leverageChange1d != null ? latest.leverageChange1d.toFixed(4) : 'N/A'}`);
console.log(`Leverage Chg 5d:       ${latest.leverageChange5d != null ? latest.leverageChange5d.toFixed(4) : 'N/A'}`);
console.log(`Pressure:              ${latest.pressureDirection || 'N/A'}`);
console.log(`Broad Deleveraging:    ${latest.broadDeleveraging || false}`);

console.log('\n=== SECTION 2: V1 vs V2 Comparison ===\n');

// Count how many days V1 would say "no deleveraging" but V2 shows meaningful deleverage
let v1MissCount = 0;
let totalBroadDelev = 0;
let v2DeleveragingDays = 0;
const stressEpisodes = [];
let inEpisode = false;
let episodeStart = null;
let episodeMinLev = Infinity;

for (let i = 5; i < results.length; i++) {
  const r = results[i];
  if (!r.leverageChange5d) continue;
  
  // V1 would only flag "deleverage" if eqVol>20% AND bondVol>15% AND corr>0.3
  const v1HighVol = r.eqVol > 0.20 && r.bondVol > 0.15 && r.corr > 0.3;
  
  // V2 detects leverage decrease
  const v2Deleverage = r.leverageChange5d < -0.05;
  
  if (v2Deleverage && !v1HighVol) v1MissCount++;
  if (r.broadDeleveraging5d) totalBroadDelev++;
  if (v2Deleverage) v2DeleveragingDays++;
  
  // Track stress episodes (broad deleveraging for 3+ consecutive days)
  if (r.broadDeleveraging) {
    if (!inEpisode) { inEpisode = true; episodeStart = r.date; episodeMinLev = r.targetLeverage; }
    episodeMinLev = Math.min(episodeMinLev, r.targetLeverage);
  } else {
    if (inEpisode && results[i-1]) {
      const days = i - results.findIndex(x => x.date === episodeStart);
      if (days >= 3) {
        stressEpisodes.push({ start: episodeStart, end: results[i-1].date, days, minLev: episodeMinLev });
      }
    }
    inEpisode = false;
  }
}

console.log(`Total observations:                  ${results.length - 5}`);
console.log(`V2 deleveraging days (5d chg<-5%):   ${v2DeleveragingDays} (${(v2DeleveragingDays/(results.length-5)*100).toFixed(1)}%)`);
console.log(`Broad deleveraging days (both down):  ${totalBroadDelev} (${(totalBroadDelev/(results.length-5)*100).toFixed(1)}%)`);
console.log(`Days V2 deleveraging but V1 missed:   ${v1MissCount} (${(v1MissCount/(results.length-5)*100).toFixed(1)}%)`);

console.log('\n=== SECTION 3: Stress Episodes (broad deleveraging ≥3 days) ===\n');
if (stressEpisodes.length === 0) {
  console.log('No sustained broad deleveraging episodes found.');
} else {
  stressEpisodes.sort((a,b) => a.minLev - b.minLev);
  stressEpisodes.forEach(ep => {
    console.log(`  ${ep.start} → ${ep.end}  (${ep.days}d)  Min leverage: ${ep.minLev.toFixed(3)}x`);
  });
}

console.log('\n=== SECTION 4: Correlation Impact on Portfolio Vol ===\n');
// Find periods where correlation flipped positive and its impact
const corrBuckets = { 'neg_strong': [], 'neg_weak': [], 'near_zero': [], 'pos_weak': [], 'pos_strong': [] };
for (const r of results) {
  const bucket = r.corr < -0.3 ? 'neg_strong' : r.corr < -0.1 ? 'neg_weak' : r.corr < 0.1 ? 'near_zero' : r.corr < 0.3 ? 'pos_weak' : 'pos_strong';
  corrBuckets[bucket].push(r);
}

console.log('| Corr Bucket     | Count | Avg PortVol | Avg Leverage | Avg Total Gross |');
console.log('|-----------------|-------|-------------|--------------|-----------------|');
for (const [bucket, rows] of Object.entries(corrBuckets)) {
  if (rows.length === 0) continue;
  const avgPV = rows.reduce((a,r) => a + r.portVol, 0) / rows.length;
  const avgLev = rows.reduce((a,r) => a + r.targetLeverage, 0) / rows.length;
  const avgGross = rows.reduce((a,r) => a + r.totalGrossExposure, 0) / rows.length;
  console.log(`| ${bucket.padEnd(15)} | ${String(rows.length).padStart(5)} | ${(avgPV*100).toFixed(1).padStart(10)}% | ${avgLev.toFixed(3).padStart(12)}x | ${(avgGross*100).toFixed(1).padStart(14)}% |`);
}

console.log('\n=== SECTION 5: Biggest Deleveraging Episodes ===\n');
// Find the 10 biggest 5-day leverage drops
const with5d = results.filter(r => r.leverageChange5d != null).sort((a,b) => a.leverageChange5d - b.leverageChange5d);
console.log('Top 10 leverage drops (5d):');
for (let i = 0; i < Math.min(10, with5d.length); i++) {
  const r = with5d[i];
  console.log(`  ${r.date}  ΔLev: ${r.leverageChange5d.toFixed(4)}  Lev: ${r.targetLeverage.toFixed(3)}  PortVol: ${(r.portVol*100).toFixed(1)}%  Corr: ${r.corr.toFixed(3)}  EqVol: ${(r.eqVol*100).toFixed(1)}%  BondVol: ${(r.bondVol*100).toFixed(1)}%`);
}

console.log('\nTop 10 leverage increases (5d):');
const incr = [...with5d].reverse();
for (let i = 0; i < Math.min(10, incr.length); i++) {
  const r = incr[i];
  console.log(`  ${r.date}  ΔLev: ${r.leverageChange5d.toFixed(4)}  Lev: ${r.targetLeverage.toFixed(3)}  PortVol: ${(r.portVol*100).toFixed(1)}%  Corr: ${r.corr.toFixed(3)}`);
}

// --- QUESTION ANSWERS ---
console.log('\n' + '='.repeat(70));
console.log('PLAIN-LANGUAGE ANSWERS');
console.log('='.repeat(70));

console.log('\n1. Does V1 get the relative stock/bond allocation broadly right?');
// Compare inv-vol weights vs true ERC weights
let maxWeightDiff = 0;
let avgWeightDiff = 0;
let ercCount = 0;
for (const r of results) {
  // True 2-asset ERC: w_eq such that w_eq * σ_p/∂w_eq = w_bond * σ_p/∂w_bond
  // For 2 assets: w_eq = (σ_bond² - cov) / (σ_eq² + σ_bond² - 2*cov)
  const eqVar = r.eqVol**2;
  const bondVar = r.bondVol**2;
  const cov = r.corr * r.eqVol * r.bondVol;
  const denom = eqVar + bondVar - 2*cov;
  if (denom > 0) {
    const wEq_erc = (bondVar - cov) / denom;
    const diff = Math.abs(r.wEq_invVol - wEq_erc);
    maxWeightDiff = Math.max(maxWeightDiff, diff);
    avgWeightDiff += diff;
    ercCount++;
  }
}
avgWeightDiff /= ercCount || 1;
console.log(`   Avg |inv-vol - ERC| weight diff: ${(avgWeightDiff * 100).toFixed(2)} pp`);
console.log(`   Max |inv-vol - ERC| weight diff: ${(maxWeightDiff * 100).toFixed(2)} pp`);
console.log(`   → V1 inverse-vol is a ${avgWeightDiff < 0.02 ? 'GOOD' : 'MODERATE'} approximation of true ERC for 2 assets.`);

console.log('\n2. How often does V2 leverage produce meaningful deleveraging that V1 completely missed?');
console.log(`   V2 produced meaningful deleveraging on ${v2DeleveragingDays} days.`);
console.log(`   Of those, V1 missed ${v1MissCount} days (${(v1MissCount/Math.max(v2DeleveragingDays,1)*100).toFixed(1)}%).`);
console.log(`   → The leverage layer captures deleveraging that V1's heuristic entirely ignores.`);

console.log('\n3. During stock-bond correlation spikes, how much does portfolio vol and leverage change?');
const negCorr = corrBuckets['neg_strong'].length > 0 ? corrBuckets['neg_strong'] : corrBuckets['neg_weak'];
const posCorr = corrBuckets['pos_strong'].length > 0 ? corrBuckets['pos_strong'] : corrBuckets['pos_weak'];
if (negCorr.length > 0 && posCorr.length > 0) {
  const avgNegPV = negCorr.reduce((a,r) => a+r.portVol, 0) / negCorr.length;
  const avgPosPV = posCorr.reduce((a,r) => a+r.portVol, 0) / posCorr.length;
  const avgNegLev = negCorr.reduce((a,r) => a+r.targetLeverage, 0) / negCorr.length;
  const avgPosLev = posCorr.reduce((a,r) => a+r.targetLeverage, 0) / posCorr.length;
  console.log(`   Negative corr → avg portVol ${(avgNegPV*100).toFixed(1)}%, avg leverage ${avgNegLev.toFixed(2)}x`);
  console.log(`   Positive corr → avg portVol ${(avgPosPV*100).toFixed(1)}%, avg leverage ${avgPosLev.toFixed(2)}x`);
  console.log(`   → Correlation flip from negative to positive increases portVol by ~${((avgPosPV-avgNegPV)*100).toFixed(1)}pp and reduces leverage by ~${(avgNegLev-avgPosLev).toFixed(2)}x.`);
}

console.log('\n4. Which historical stress periods show the biggest mechanical deleveraging?');
if (stressEpisodes.length > 0) {
  const top = stressEpisodes.slice(0, 5);
  top.forEach(ep => {
    console.log(`   ${ep.start} → ${ep.end}: ${ep.days} days, leverage bottomed at ${ep.minLev.toFixed(3)}x`);
  });
} else {
  console.log('   No sustained broad deleveraging episodes found in history.');
  console.log('   Checking for individual extreme deleveraging days:');
  with5d.slice(0, 5).forEach(r => {
    console.log(`   ${r.date}: leverage=${r.targetLeverage.toFixed(3)}, ΔLev5d=${r.leverageChange5d.toFixed(4)}`);
  });
}

// --- OUTPUT JSON for integration ---
const outputPath = path.join(__dirname, 'rp_v2_diagnostic_output.json');
const output = {
  config: CONFIG,
  latestObservation: latest,
  stressEpisodes,
  summary: {
    totalDays: results.length,
    v2DeleveragingDays,
    v1MissCount,
    totalBroadDelev,
    avgWeightDiffVsERC: avgWeightDiff,
    maxWeightDiffVsERC: maxWeightDiff,
  },
  // Save a sample of daily results (last 60 days for inspection)
  recentDays: results.slice(-60).map(r => ({
    date: r.date,
    eqVol: +r.eqVol.toFixed(4),
    bondVol: +r.bondVol.toFixed(4),
    corr: +r.corr.toFixed(4),
    wEq: +r.wEq_invVol.toFixed(4),
    portVol: +r.portVol.toFixed(4),
    leverage: +r.targetLeverage.toFixed(4),
    eqGross: +r.eqGrossExposure.toFixed(4),
    bondGross: +r.bondGrossExposure.toFixed(4),
    levChg1d: r.leverageChange1d != null ? +r.leverageChange1d.toFixed(4) : null,
    levChg5d: r.leverageChange5d != null ? +r.leverageChange5d.toFixed(4) : null,
    broadDelev: r.broadDeleveraging || false,
    pressure: r.pressureDirection || null,
  })),
};
fs.writeFileSync(outputPath, JSON.stringify(output, null, 2));
console.log(`\nDiagnostic output saved to: ${outputPath}`);
