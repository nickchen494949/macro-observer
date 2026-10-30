const fs = require('fs');
const path = require('path');

function loadJson(p) {
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, 'utf-8'));
}

// Daily OHLC does not reveal high/low order. Report explicit drawdown bounds.
function calculateDrawdownBounds(prices, adjOpen_F) {
  if (!Number.isFinite(adjOpen_F) || adjOpen_F <= 0) throw new Error('Invalid entry price');
  let peak = adjOpen_F, conservative = 0, optimistic = 0;
  for (const day of prices) {
    const {adjOpen:o, adjHigh:h, adjLow:l, adjClose:c} = day;
    if (![o,h,l,c].every(x=>Number.isFinite(x)&&x>0) || l>Math.min(o,c) || h<Math.max(o,c) || l>h)
      throw new Error('Invalid adjusted OHLC');
    optimistic = Math.min(optimistic, l / Math.max(peak,o) - 1, c / Math.max(peak,h) - 1);
    conservative = Math.min(conservative, l / Math.max(peak,h) - 1);
    peak = Math.max(peak,h);
  }
  return {conservative,optimistic};
}
function calculateMaxDrawdown(prices, adjOpen_F) {
  return calculateDrawdownBounds(prices,adjOpen_F).conservative;
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

function main(args = process.argv.slice(2)) {
  const yahooDir = args[2] || path.join(__dirname, '../data/backtest_ohlc');
  const snapshotPath = args[0] || path.join(__dirname, 'phase3/snapshots_phase3.json');
  const outPath = args[1] || path.join(__dirname, 'phase3/forward_labels_phase3.json');

  const snapshots = loadJson(snapshotPath);
  if (!snapshots) {
    console.error("No snapshots found at " + snapshotPath);
    throw new Error('Required snapshots missing');
  }
  
  const spx = loadJson(path.join(yahooDir, '_GSPC.json'));
  
  if (!spx || !snapshots) {
    console.error("Missing SPX data or snapshots.json");
    process.exit(1);
  }
  
  const spxData = (spx.values || spx).map(x => Array.isArray(x)
    ? (x[1] && typeof x[1] === 'object' ? x[1] : {date:x[0],close:x[1],status:'missing_ohlc'}) : x);
  const numericOHLC = x => [x.open,x.high,x.low,x.close,x.adjOpen,x.adjHigh,x.adjLow,x.adjClose].every(v=>Number.isFinite(v)&&v>0);
  if (!spxData.some(numericOHLC) || spxData.some((x,i)=>!x.date || (i && x.date<=spxData[i-1].date))) {
    throw new Error('BLOCK: sorted daily adjusted OHLC required; close-only caches cannot generate path labels');
  }
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
      if (!mData) continue;
      if (!mData.firstTradableSession) { labels[date].modules[m]={labelStatus:'missing_first_tradable_session'}; continue; }
      
      const fts = mData.firstTradableSession;
      if (!spxMap.has(fts)) {
        labels[date].modules[m]={signalAvailableAt:mData.signalAvailableAt,firstTradableSession:fts,labelStatus:'missing_entry_session'};
        continue;
      }
      
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
      
      if (spxData.slice(startIdx,startIdx+20).some(x=>!numericOHLC(x))) {
        labels[date].modules[m]={signalAvailableAt:mData.signalAvailableAt,firstTradableSession:fts,labelStatus:'missing_ohlc_in_window'};
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
             adjOpen: spxData[startIdx + j].adjOpen,
             adjClose: spxData[startIdx + j].adjClose,
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
        
        const bounds = calculateDrawdownBounds(prices, adjOpen_F);
        const mdd = bounds.conservative;
        
        res['return' + hKey + 'Open'] = ret;
        res['mae' + hKey] = mae;
        res['mdd' + hKey] = mdd;
        res['mddOptimistic' + hKey] = bounds.optimistic;
        res.drawdownMethod = 'daily_ohlc_conservative_bound_not_intraday_path';
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
      if (startIdx + 19 < spxData.length && spxData.slice(startIdx,startIdx+20).every(numericOHLC)) {
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

module.exports={main,calculateMaxDrawdown,calculateDrawdownBounds,calcRealizedVol};
if(require.main===module) main();
