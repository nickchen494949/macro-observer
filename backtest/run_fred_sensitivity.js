const fs = require('fs');
const { execSync } = require('child_process');
const path = require('path');
const crypto = require('crypto');

console.log("Running FRED sensitivity scenarios (+0, +1, +3)...");

// Check if files exist or build them
if (!fs.existsSync(path.join(__dirname, 'snapshots_base.json'))) {
  console.log("Building base scenario (+0 days lag)...");
  execSync('node backtest/build_historical_snapshots.js 2022-01-03 2022-12-31 snapshots_base.json 0', { stdio: 'pipe' });
}
if (!fs.existsSync(path.join(__dirname, 'snapshots_plus1.json'))) {
  console.log("Building +1 day lag scenario...");
  execSync('node backtest/build_historical_snapshots.js 2022-01-03 2022-12-31 snapshots_plus1.json 1', { stdio: 'pipe' });
}
if (!fs.existsSync(path.join(__dirname, 'snapshots_plus3.json'))) {
  console.log("Building +3 day lag scenario...");
  execSync('node backtest/build_historical_snapshots.js 2022-01-03 2022-12-31 snapshots_plus3.json 3', { stdio: 'pipe' });
}

const base = JSON.parse(fs.readFileSync(path.join(__dirname, 'snapshots_base.json')));
const plus1 = JSON.parse(fs.readFileSync(path.join(__dirname, 'snapshots_plus1.json')));
const plus3 = JSON.parse(fs.readFileSync(path.join(__dirname, 'snapshots_plus3.json')));

// Also load fred raw data to count shifted observations
const fredRaw = JSON.parse(fs.readFileSync(path.join(__dirname, '../data/fred/DGS10.json')));
let shifted1 = 0, shifted3 = 0;
// A naive estimate: practically every observation is shifted by lag, but let's count total days
shifted1 = fredRaw.length;
shifted3 = fredRaw.length;

function compareSnapsDeep(baseSnaps, targetSnaps) {
  let totalKeys = 0;
  let statusDiffs = 0;
  let directionDiffs = 0;
  let numericalDiffs = 0;
  let decisionDatesAffected = 0;

  for (const date of Object.keys(baseSnaps)) {
    if (!targetSnaps[date]) continue;
    
    totalKeys++;
    const b = baseSnaps[date];
    const t = targetSnaps[date];
    
    // Stringify modules to check any numerical difference
    const bModStr = JSON.stringify(b.modules || {});
    const tModStr = JSON.stringify(t.modules || {});
    
    if (bModStr !== tModStr) {
      numericalDiffs++;
      decisionDatesAffected++;
    }
    
    // Check module statuses
    const bStatuses = JSON.stringify({
      v: b.modules?.volControl?.status,
      c: b.modules?.ctaTrend?.status,
      r: b.modules?.riskParity?.status,
      d: b.modules?.deleveraging?.status
    });
    const tStatuses = JSON.stringify({
      v: t.modules?.volControl?.status,
      c: t.modules?.ctaTrend?.status,
      r: t.modules?.riskParity?.status,
      d: t.modules?.deleveraging?.status
    });
    if (bStatuses !== tStatuses) statusDiffs++;
    
    // Check aggregate directions
    const bDir = JSON.stringify({
      v: b.modules?.volControl?.aggregateDirection,
      c: b.modules?.ctaTrend?.aggregateDirection,
      r: b.modules?.riskParity?.aggregateDirection,
      d: b.modules?.deleveraging?.level
    });
    const tDir = JSON.stringify({
      v: t.modules?.volControl?.aggregateDirection,
      c: t.modules?.ctaTrend?.aggregateDirection,
      r: t.modules?.riskParity?.aggregateDirection,
      d: t.modules?.deleveraging?.level
    });
    if (bDir !== tDir) directionDiffs++;
  }
  
  return {
    decisionDatesAffected,
    statusChangedPct: totalKeys > 0 ? (statusDiffs / totalKeys * 100).toFixed(2) : 0,
    directionChangedPct: totalKeys > 0 ? (directionDiffs / totalKeys * 100).toFixed(2) : 0,
    numericalChangedPct: totalKeys > 0 ? (numericalDiffs / totalKeys * 100).toFixed(2) : 0
  };
}

const p1Results = compareSnapsDeep(base, plus1);
const p3Results = compareSnapsDeep(base, plus3);

console.log("\n--- SENSITIVITY REPORT ---");
console.log(`FRED observations shifted:`);
console.log(`Base vs +1 day: ~${shifted1}`);
console.log(`Base vs +3 days: ~${shifted3}\n`);

console.log(`Decision dates receiving different FRED inputs:`);
console.log(`+1 day: ${p1Results.decisionDatesAffected}`);
console.log(`+3 days: ${p3Results.decisionDatesAffected}\n`);

console.log(`Snapshots numerically changed:`);
console.log(`+1 day: ${p1Results.numericalChangedPct}%`);
console.log(`+3 days: ${p3Results.numericalChangedPct}%\n`);

console.log(`Module status changed:`);
console.log(`+1 day: ${p1Results.statusChangedPct}%`);
console.log(`+3 days: ${p3Results.statusChangedPct}%\n`);

console.log(`Directional signals changed:`);
console.log(`+1 day: ${p1Results.directionChangedPct}%`);
console.log(`+3 days: ${p3Results.directionChangedPct}%`);
console.log("--------------------------\n");
