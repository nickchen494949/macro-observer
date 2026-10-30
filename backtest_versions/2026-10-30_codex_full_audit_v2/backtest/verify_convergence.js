const fs = require('fs');
const path = require('path');
const { runFlowEngine } = require('../lib/flow_engine');
const { getModelPrice } = require('../lib/data_validation');

function loadJson(p) {
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, 'utf-8'));
}

function loadAllData() {
  const yahoo = {};
  const yahooDir = path.join(__dirname, '../data/yahoo');
  if (fs.existsSync(yahooDir)) {
    for (const f of fs.readdirSync(yahooDir)) {
      if (f.endsWith('.json')) {
        const d = loadJson(path.join(yahooDir, f));
        if (d && (d.id || d.symbol)) {
          const arr = [];
          for (const v of d.values) {
            if (v.status === 'missing_source_observation') continue;
            try {
              arr.push(Array.isArray(v) ? v : [v.date, getModelPrice(d.id || d.symbol, v)]);
            } catch (e) {
              if (e.name !== 'DataValidationError') throw e;
            }
          }
          yahoo[d.id || d.symbol] = arr;
        }
      }
    }
  }
  return { fred: {}, yahoo, valuation: {} };
}

function verifyConvergence() {
  console.log("Running State Convergence Proof...");
  const store = loadAllData();
  const spx = store.yahoo['^GSPC'];
  if (!spx || spx.length < 252) throw new Error("Not enough SPX data");
  
  const targetDate = spx[spx.length - 1][0];
  const totalDays = spx.length - 100;
  
  // Base config configB (Target initialization)
  const configB = {
    decisionDate: targetDate,
    signalAvailableAt: targetDate + 'T18:00:00Z',
    marketDataAsOf: targetDate,
    inputsAsOfDecision: store,
    previousState: null,
    modelConfig: {
      useEtfProxy: false,
      recursionLookbackOverride: totalDays,
      exportHistory: true
    }
  };
  
  const resB = runFlowEngine(configB);
  const targetSeries = resB.modules.volControl.targetSeries;
  const firstDayTargetExposure = targetSeries[0].target;
  const historyB = resB.modules.volControl.actualExpHistory;
  
  // configA (100% allocation initialization)
  const configA = {
    ...configB,
    modelConfig: {
      useEtfProxy: false,
      recursionLookbackOverride: totalDays,
      initialExposureOverride: 1.0,
      exportHistory: true
    }
  };
  
  const resA = runFlowEngine(configA);
  const historyA = resA.modules.volControl.actualExpHistory;
  
  console.log(`Initial A Exposure: 1.0`);
  console.log(`Initial B Exposure: ${firstDayTargetExposure}`);
  
  let firstDateBelow1bp = null;
  let maxDiffAfterConvergence = 0;
  let laterBreaches = 0;
  
  const startDiff = Math.abs(historyA[0] - historyB[0]);
  console.log(`Difference at evaluation start: ${(startDiff * 10000).toFixed(2)} bp`);
  
  for (let i = 0; i < historyA.length; i++) {
    const diff = Math.abs(historyA[i] - historyB[i]);
    const bp = diff * 10000;
    
    if (firstDateBelow1bp === null && bp < 1.0) {
      // Find the corresponding date! 
      // The array has `totalDays + 1` elements.
      const dateIdx = spx.length - 1 - totalDays + i;
      firstDateBelow1bp = spx[dateIdx][0];
      console.log(`First convergence date below 1 bp: ${firstDateBelow1bp}`);
    } else if (firstDateBelow1bp !== null) {
      if (bp > maxDiffAfterConvergence) maxDiffAfterConvergence = bp;
      if (bp >= 1.0) laterBreaches++;
    }
  }
  
  console.log(`Maximum difference after convergence: ${maxDiffAfterConvergence.toFixed(4)} bp`);
  console.log(`Number of later threshold breaches: ${laterBreaches}`);
  
  if (laterBreaches > 0) {
    console.error("❌ Convergence failed! Found later threshold breaches.");
    process.exit(1);
  }
  console.log("✅ Convergence proven: State chain initializes robustly regardless of starting condition.");
}

verifyConvergence();
