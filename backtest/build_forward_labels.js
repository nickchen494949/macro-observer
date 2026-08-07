const fs = require('fs');
const path = require('path');

function loadJson(p) {
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, 'utf-8'));
}

// True Intraday Path-Dependent Drawdown
function calculateMaxDrawdown(prices) {
  if (!prices || prices.length === 0) return 0;
  // prices should be an array of objects: { high, low, adjHigh, adjLow }
  let maxPx = prices[0].adjHigh;
  let maxDd = 0;
  for (let i = 1; i < prices.length; i++) {
    if (prices[i].adjHigh > maxPx) {
      maxPx = prices[i].adjHigh;
    }
    const dd = (prices[i].adjLow - maxPx) / maxPx;
    if (dd < maxDd) maxDd = dd;
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
    const mods = ['volControl', 'ctaEtfProxy', 'riskParityProxy', 'pensionRebalance'];
    for (const m of mods) {
      const mData = snap.modules[m];
      if (!mData || !mData.firstTradableSession) continue;
      
      const fts = mData.firstTradableSession;
      if (!spxMap.has(fts)) continue;
      
      const startIdx = spxMap.get(fts).idx;
      if (startIdx + 4 >= spxData.length) continue;
      
      const adjOpen_F = spxData[startIdx].adjOpen;
      const adjClose_F = spxData[startIdx].adjClose;
      const adjClose_F4 = spxData[startIdx + 4].adjClose;
      
      const ret1d = (adjClose_F / adjOpen_F) - 1;
      const ret5d = (adjClose_F4 / adjOpen_F) - 1;
      
      const prices5d = [];
      const lows5d = [];
      for (let j = 0; j <= 4; j++) {
        prices5d.push(spxData[startIdx + j].adjClose);
        lows5d.push(spxData[startIdx + j].adjLow);
      }
      
      // MAE_h: from entry AdjOpen_F to worst AdjLow
      let mae = 0;
      for (const l of lows5d) {
        const dd = (l - adjOpen_F) / adjOpen_F;
        if (dd < mae) mae = dd;
      }
      
      const mdd = calculateMaxDrawdown(prices5d);
      
      labels[date].modules[m] = {
        signalAvailableAt: mData.signalAvailableAt,
        firstTradableSession: fts,
        return1dOpen: ret1d,
        return5dOpen: ret5d,
        mae5d: mae,
        mdd5d: mdd
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
