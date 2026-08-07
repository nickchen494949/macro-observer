const fs = require('fs');
const { execSync } = require('child_process');
const path = require('path');
const assert = require('assert');

console.log("Running FRED sensitivity scenarios (+0, +1, +3)...");

console.log("Building base scenario (+0 days lag)...");
execSync('node backtest/build_historical_snapshots.js 2022-01-03 2022-12-31 snapshots_base.json 0', { stdio: 'pipe' });
console.log("Building +1 day lag scenario...");
execSync('node backtest/build_historical_snapshots.js 2022-01-03 2022-12-31 snapshots_plus1.json 1', { stdio: 'pipe' });
console.log("Building +3 day lag scenario...");
execSync('node backtest/build_historical_snapshots.js 2022-01-03 2022-12-31 snapshots_plus3.json 3', { stdio: 'pipe' });

const base = JSON.parse(fs.readFileSync(path.join(__dirname, 'snapshots_base.json')));
const plus1 = JSON.parse(fs.readFileSync(path.join(__dirname, 'snapshots_plus1.json')));
const plus3 = JSON.parse(fs.readFileSync(path.join(__dirname, 'snapshots_plus3.json')));

function compareSnapsDeep(baseSnaps, targetSnaps) {
  let totalKeys = 0;
  let statusDiffs = 0;
  let directionDiffs = 0;
  
  let riskParityNumDiffs = 0;
  let volControlNumDiffs = 0;
  let ctaEtfNumDiffs = 0;
  let decisionDatesAffected = 0;
  
  let pitSelectionsChanged = 0;
  let pitDiffLog = [];

  for (const date of Object.keys(baseSnaps)) {
    if (!targetSnaps[date]) continue;
    
    totalKeys++;
    const b = baseSnaps[date];
    const t = targetSnaps[date];
    
    const bObsDate = b.modules?.riskParity?.dgs10ObservationDate;
    const tObsDate = t.modules?.riskParity?.dgs10ObservationDate;
    const bVal = b.modules?.riskParity?.dgs10Value;
    const tVal = t.modules?.riskParity?.dgs10Value;
    
    if (bObsDate !== tObsDate || bVal !== tVal) {
        pitSelectionsChanged++;
        pitDiffLog.push({
            decisionDate: date,
            base: { observationDate: bObsDate, value: bVal },
            target: { observationDate: tObsDate, value: tVal }
        });
    }

    let dateAffected = false;

    const extractNumState = (rp) => {
        const { dgs10ObservationDate, dgs10Value, ...rest } = rp || {};
        return JSON.stringify(rest);
    };

    const bRP = extractNumState(b.modules?.riskParity);
    const tRP = extractNumState(t.modules?.riskParity);
    if (bRP !== tRP) {
        riskParityNumDiffs++;
        dateAffected = true;
    }

    const bVC = JSON.stringify(b.modules?.volControl || {});
    const tVC = JSON.stringify(t.modules?.volControl || {});
    if (bVC !== tVC) {
        volControlNumDiffs++;
        dateAffected = true;
    }

    const bCTA = JSON.stringify(b.modules?.ctaEtfProxy || {});
    const tCTA = JSON.stringify(t.modules?.ctaEtfProxy || {});
    if (bCTA !== tCTA) {
        ctaEtfNumDiffs++;
        dateAffected = true;
    }

    if (dateAffected) decisionDatesAffected++;
    
    const bStatuses = JSON.stringify({
      v: b.modules?.volControl?.status,
      c: b.modules?.ctaEtfProxy?.status,
      r: b.modules?.riskParity?.status
    });
    const tStatuses = JSON.stringify({
      v: t.modules?.volControl?.status,
      c: t.modules?.ctaEtfProxy?.status,
      r: t.modules?.riskParity?.status
    });
    if (bStatuses !== tStatuses) statusDiffs++;
    
    const bDir = JSON.stringify({
      v: b.modules?.volControl?.nextDayEstimateIfTargetUnchanged,
      r: b.modules?.riskParity?.allocationDirection
    });
    const tDir = JSON.stringify({
      v: t.modules?.volControl?.nextDayEstimateIfTargetUnchanged,
      r: t.modules?.riskParity?.allocationDirection
    });
    if (bDir !== tDir) directionDiffs++;
  }
  
  assert(volControlNumDiffs === 0, 'Vol-Control numerical states changed! Causal isolation broken.');
  assert(ctaEtfNumDiffs === 0, 'CTA ETF numerical states changed! Causal isolation broken.');

  return {
    decisionDatesAffected,
    riskParityNumDiffs,
    volControlNumDiffs,
    ctaEtfNumDiffs,
    pitSelectionsChanged,
    pitDiffLog,
    statusChangedPct: totalKeys > 0 ? (statusDiffs / totalKeys * 100).toFixed(2) : 0,
    directionChangedPct: totalKeys > 0 ? (directionDiffs / totalKeys * 100).toFixed(2) : 0
  };
}

const p1Results = compareSnapsDeep(base, plus1);
const p3Results = compareSnapsDeep(base, plus3);

fs.writeFileSync(path.join(__dirname, 'fred_sensitivity_report.json'), JSON.stringify({
    plus1: p1Results,
    plus3: p3Results
}, null, 2));

console.log("\n--- SENSITIVITY REPORT ---");
console.log(`FRED PIT selections changed:`);
console.log(`Base vs +1 day: ${p1Results.pitSelectionsChanged}`);
console.log(`Base vs +3 days: ${p3Results.pitSelectionsChanged}\n`);

console.log(`Decision dates with different PIT inputs:`);
console.log(`+1 day: ${p1Results.decisionDatesAffected}`);
console.log(`+3 days: ${p3Results.decisionDatesAffected}\n`);

console.log(`Numerical module states changed:`);
console.log(`+1 day: Risk-Parity=${p1Results.riskParityNumDiffs}, Vol-Control=${p1Results.volControlNumDiffs}, CTA-ETF=${p1Results.ctaEtfNumDiffs}`);
console.log(`+3 days: Risk-Parity=${p3Results.riskParityNumDiffs}, Vol-Control=${p3Results.volControlNumDiffs}, CTA-ETF=${p3Results.ctaEtfNumDiffs}\n`);

console.log(`Module statuses changed:`);
console.log(`+1 day: ${p1Results.statusChangedPct}%`);
console.log(`+3 days: ${p3Results.statusChangedPct}%\n`);

console.log(`Directional signals changed:`);
console.log(`+1 day: ${p1Results.directionChangedPct}%`);
console.log(`+3 days: ${p3Results.directionChangedPct}%`);
console.log("--------------------------\n");
console.log("Causal isolation validated: non-FRED modules mathematically invariant.");
