const fs = require('fs');
const path = require('path');

function loadJson(p) {
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, 'utf-8'));
}

// True Intraday Path-Dependent Drawdown
function calculateMaxDrawdown(prices, adjOpen_F) {
  if (!prices || prices.length === 0) return 0;
  // prices should be an array of objects: { high, low, adjHigh, adjLow }
  let runningPeak = adjOpen_F;
  let maxDd = 0;
  for (const day of prices) {
    const dd = (day.adjLow / runningPeak) - 1;
    if (dd < maxDd) maxDd = dd;
    runningPeak = Math.max(runningPeak, day.adjHigh);
  }
  return maxDd;
}

function main() {
  const yahooDir = path.join(__dirname, '../data/yahoo');
  const snapshotsPath = path.join(__dirname, 'snapshots.json');
  
  const spx = loadJson(path.join(yahooDir, '_GSPC.json'));
  const snapshots = loadJson(snapshotsPath);
  
  if (!spx || !snapshots) {
    console.error("Missing SPX data or snapshots.json");
    process.exit(1);
  }
  
  const spxData = spx.values || spx; // Array of objects
  const spxMap = new Map();
  spxData.forEach((d, i) => spxMap.set(d.date, { idx: i, data: d }));
  
  const labels = {};
  
  for (const [date, snap] of Object.entries(snapshots)) {
    if (!snap.modules) continue;
    
    labels[date] = { decisionDate: date, modules: {}, composite: {} };
    
    // Evaluate per-module
    const mods = ['volControl', 'ctaEtfProxy', 'riskParity', 'pensionRebalance'];
    for (const m of mods) {
      const mData = snap.modules[m];
      if (!mData || !mData.firstTradableSession) continue;
      
      const fts = mData.firstTradableSession;
      if (!spxMap.has(fts)) continue;
      
      const startIdx = spxMap.get(fts).idx;
      
      // Insufficient future data check
      if (startIdx + 4 >= spxData.length) {
          labels[date].modules[m] = {
              signalAvailableAt: mData.signalAvailableAt,
              firstTradableSession: fts,
              labelStatus: "insufficient_future_data"
          };
          continue;
      }
      
      // Adjusted OHLC integrity check
      const d0 = spxData[startIdx];
      const adjRatio = d0.adjClose / d0.close;
      if (Math.abs(d0.adjOpen - (d0.open * adjRatio)) > 0.01) {
          labels[date].modules[m] = {
              signalAvailableAt: mData.signalAvailableAt,
              firstTradableSession: fts,
              labelStatus: "adjusted_ohlc_integrity_error"
          };
          continue;
      }

      const adjOpen_F = spxData[startIdx].adjOpen;
      const adjClose_F = spxData[startIdx].adjClose;
      const adjClose_F4 = spxData[startIdx + 4].adjClose;
      
      const ret1d = (adjClose_F / adjOpen_F) - 1;
      const ret5d = (adjClose_F4 / adjOpen_F) - 1;
      
      const prices5d = [];
      const lows5d = [];
      for (let j = 0; j <= 4; j++) {
        prices5d.push({
           adjHigh: spxData[startIdx + j].adjHigh,
           adjLow: spxData[startIdx + j].adjLow
        });
        lows5d.push(spxData[startIdx + j].adjLow);
      }
      
      // MAE_h: from entry AdjOpen_F to worst AdjLow
      let mae = 0;
      for (const l of lows5d) {
        const dd = (l - adjOpen_F) / adjOpen_F;
        if (dd < mae) mae = dd;
      }
      
      const mdd = calculateMaxDrawdown(prices5d, adjOpen_F);
      
      labels[date].modules[m] = {
        signalAvailableAt: mData.signalAvailableAt,
        firstTradableSession: fts,
        labelStatus: "ok",
        return1dOpen: Number(ret1d.toFixed(4)),
        return5dOpen: Number(ret5d.toFixed(4)),
        mae5d: Number(mae.toFixed(4)),
        mdd5d: Number(mdd.toFixed(4))
      };
    }
    
    // Composite evaluates from composite.firstTradableSession (max of all)
    let compFts = null;
    let maxSig = null;
    for (const m of mods) {
      const mData = snap.modules[m];
      if (mData && mData.firstTradableSession) {
        if (!maxSig || mData.signalAvailableAt > maxSig) {
          maxSig = mData.signalAvailableAt;
          compFts = mData.firstTradableSession;
        }
      }
    }
    
    if (compFts && spxMap.has(compFts)) {
      const startIdx = spxMap.get(compFts).idx;
      if (startIdx + 4 < spxData.length) {
        const adjOpen_F = spxData[startIdx].adjOpen;
        const adjClose_F4 = spxData[startIdx + 4].adjClose;
        const ret5d = (adjClose_F4 / adjOpen_F) - 1;
        labels[date].composite = {
          firstTradableSession: compFts,
          return5dOpen: ret5d
        };
      }
    }
  }
  
  const outPath = path.join(__dirname, 'forward_labels.json');
  fs.writeFileSync(outPath, JSON.stringify(labels, null, 2));
  console.log(`Wrote module-specific forward labels for ${Object.keys(labels).length} days to ${outPath}`);
}

main();
