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

function calcRealizedVol(spxData, startIdx, h) {
  if (h < 2) return null;
  const logRets = [];
  for (let j = 0; j < h; j++) {
    const todayClose = spxData[startIdx + j].adjClose;
    const prevClose = startIdx + j - 1 >= 0 ? spxData[startIdx + j - 1].adjClose : spxData[startIdx + j].adjOpen;
    logRets.push(Math.log(todayClose / prevClose));
  }
  const mean = logRets.reduce((a, b) => a + b, 0) / logRets.length;
  let sumSq = 0;
  for (const r of logRets) {
    sumSq += Math.pow(r - mean, 2);
  }
  const variance = sumSq / (logRets.length - 1); // ddof=1
  return Math.sqrt(variance * 252);
}

function main() {
  const yahooDir = path.join(__dirname, '../data/yahoo');
  const snapshotPath = process.argv[2] || path.join(__dirname, 'phase3/snapshots_phase3.json');
  const outPath = process.argv[3] || path.join(__dirname, 'phase3/forward_labels_phase3.json');

  const snapshots = loadJson(snapshotPath);
  if (!snapshots) {
    console.error("No snapshots found at " + snapshotPath);
    return;
  }
  
  const spx = loadJson(path.join(yahooDir, '_GSPC.json'));
  
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
      
      // Insufficient future data check (max horizon is 20)
      if (startIdx + 19 >= spxData.length) {
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
      
      const res = {
        signalAvailableAt: mData.signalAvailableAt,
        firstTradableSession: fts,
        labelStatus: "ok"
      };

      const horizons = [1, 3, 5, 10, 20];
      for (const h of horizons) {
        const hKey = h + 'd';
        const adjClose_Fh = spxData[startIdx + h - 1].adjClose;
        const ret = (adjClose_Fh / adjOpen_F) - 1;
        
        const prices = [];
        const lows = [];
        for (let j = 0; j < h; j++) {
          prices.push({
             adjHigh: spxData[startIdx + j].adjHigh,
             adjLow: spxData[startIdx + j].adjLow
          });
          lows.push(spxData[startIdx + j].adjLow);
        }
        
        let mae = 0;
        for (const l of lows) {
          const dd = (l / adjOpen_F) - 1;
          if (dd < mae) mae = dd;
        }
        
        const mdd = calculateMaxDrawdown(prices, adjOpen_F);
        
        res['return' + hKey + 'Open'] = ret;
        res['mae' + hKey] = mae;
        res['mdd' + hKey] = mdd;
        res['lastLabelSession' + hKey] = spxData[startIdx + h - 1].date;
        
        if (h >= 5) {
            const vol = calcRealizedVol(spxData, startIdx, h);
            if (vol !== null) {
                res['vol' + hKey] = vol;
            }
        }
      }
      
      labels[date].modules[m] = res;
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
      if (startIdx + 19 < spxData.length) {
        const adjOpen_F = spxData[startIdx].adjOpen;
        const resComp = { firstTradableSession: compFts };
        const horizons = [1, 3, 5, 10, 20];
        for (const h of horizons) {
            const adjClose_Fh = spxData[startIdx + h - 1].adjClose;
            resComp['return' + h + 'dOpen'] = (adjClose_Fh / adjOpen_F) - 1;
            resComp['lastLabelSession' + h + 'd'] = spxData[startIdx + h - 1].date;
        }
        labels[date].composite = resComp;
      }
    }
  }
  
  const outDir = path.dirname(outPath);
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(outPath, JSON.stringify(labels, null, 2));
  console.log(`Wrote forward labels for ${Object.keys(labels).length} days to ${outPath}`);
}

main();
