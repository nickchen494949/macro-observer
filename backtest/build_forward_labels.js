const fs = require('fs');
const path = require('path');

function loadJson(p) {
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, 'utf-8'));
}

function calculateMaxDrawdown(prices) {
  if (!prices || prices.length === 0) return 0;
  let maxPx = prices[0];
  let maxDd = 0;
  for (let i = 1; i < prices.length; i++) {
    if (prices[i] > maxPx) {
      maxPx = prices[i];
    } else {
      const dd = (prices[i] - maxPx) / maxPx;
      if (dd < maxDd) maxDd = dd;
    }
  }
  return maxDd;
}

function calculateRealizedVol(returns) {
  if (!returns || returns.length < 2) return 0;
  const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
  const variance = returns.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / (returns.length - 1);
  return Math.sqrt(variance) * Math.sqrt(252) * 100;
}

function main() {
  const yahooDir = path.join(__dirname, '../data/yahoo');
  const fredDir = path.join(__dirname, '../data/fred');
  const spx = loadJson(path.join(yahooDir, '_GSPC.json'));
  const dgs10 = loadJson(path.join(fredDir, 'DGS10.json'));
  
  if (!spx || !dgs10) {
    console.error("Missing necessary Yahoo or Fred data for SPX or DGS10.");
    process.exit(1);
  }
  
  const spxData = spx.values;
  const bondData = dgs10.values;
  
  // Index by date for O(1) lookups
  const spxMap = new Map();
  spxData.forEach((d, i) => spxMap.set(d[0], { idx: i, price: d[1] }));
  
  const bondMap = new Map();
  bondData.forEach((d, i) => bondMap.set(d[0], { idx: i, yield: d[1] }));

  const labels = {};
  
  for (let i = 0; i < spxData.length - 1; i++) {
    const today = spxData[i][0];
    
    // T+1 is i+1, T+h is i+h
    // Forward return uses T+1 close to T+h close.
    // That means return = (Price(T+h) - Price(T+1)) / Price(T+1)
    
    const pxT1 = spxData[i+1][1];
    
    const getRet = (horizon) => {
      if (i + horizon < spxData.length) {
        return (spxData[i+horizon][1] / pxT1) - 1;
      }
      return null;
    };
    
    const ret1d = getRet(1);
    const ret5d = getRet(5);
    const ret10d = getRet(10);
    const ret20d = getRet(20);
    
    // Max Drawdown 5d
    let maxDd5d = null;
    if (i + 5 < spxData.length) {
      const prices5d = [];
      for (let j = 1; j <= 5; j++) prices5d.push(spxData[i+j][1]);
      maxDd5d = calculateMaxDrawdown(prices5d);
    }
    
    // Realized Vol 5d
    let realVol5d = null;
    if (i + 5 < spxData.length) {
      const rets5d = [];
      for (let j = 2; j <= 5; j++) {
        rets5d.push((spxData[i+j][1] / spxData[i+j-1][1]) - 1);
      }
      realVol5d = calculateRealizedVol(rets5d);
    }
    
    // Equity minus Bond 5d
    let eqMinusBd5d = null;
    if (i + 5 < spxData.length && bondMap.has(today)) {
      const bondIdx = bondMap.get(today).idx;
      if (bondIdx + 5 < bondData.length) {
        const yieldT1 = bondData[bondIdx+1][1];
        const yieldT5 = bondData[bondIdx+5][1];
        // Proxy bond return: -Duration * (YieldT5 - YieldT1) / 100
        const bondRet5d = -8 * (yieldT5 - yieldT1) / 100;
        eqMinusBd5d = ret5d - bondRet5d;
      }
    }
    
    labels[today] = {
      futureReturn1d: ret1d,
      futureReturn5d: ret5d,
      futureReturn10d: ret10d,
      futureReturn20d: ret20d,
      futureMaxDrawdown5d: maxDd5d,
      futureRealizedVol5d: realVol5d,
      equityMinusBond5d: eqMinusBd5d
    };
  }
  
  const outPath = path.join(__dirname, 'labels.json');
  fs.writeFileSync(outPath, JSON.stringify(labels, null, 2));
  console.log(`Wrote forward labels for ${Object.keys(labels).length} days to ${outPath}`);
}

main();
