const fs = require('fs');
const path = require('path');

function getRank(arr) {
  const sorted = arr.map((v, i) => ({v, i})).sort((a, b) => a.v - b.v);
  const ranks = new Array(arr.length);
  for (let i = 0; i < sorted.length; i++) {
    ranks[sorted[i].i] = i + 1;
  }
  return ranks;
}

function pearson(arr1, arr2) {
  if (arr1.length !== arr2.length || arr1.length === 0) return 0;
  const mean1 = arr1.reduce((a,b)=>a+b,0)/arr1.length;
  const mean2 = arr2.reduce((a,b)=>a+b,0)/arr2.length;
  let num = 0, den1 = 0, den2 = 0;
  for(let i=0; i<arr1.length; i++) {
    num += (arr1[i]-mean1) * (arr2[i]-mean2);
    den1 += Math.pow(arr1[i]-mean1, 2);
    den2 += Math.pow(arr2[i]-mean2, 2);
  }
  return num / Math.sqrt(den1 * den2 || 1);
}

function spearman(arr1, arr2) {
  return pearson(getRank(arr1), getRank(arr2));
}

function analyzeSignal(data, signalName) {
  // data is [{signal, ret1d, ret5d, ret10d, ret20d, ...}, ...]
  // We want to sort by signal to form quintiles
  data.sort((a, b) => a.signal - b.signal);
  
  const bucketSize = Math.floor(data.length / 5);
  const buckets = [];
  for (let i = 0; i < 5; i++) {
    const start = i * bucketSize;
    const end = i === 4 ? data.length : (i + 1) * bucketSize;
    const slice = data.slice(start, end);
    const avg5d = slice.reduce((sum, d) => sum + d.ret5d, 0) / slice.length;
    const avg20d = slice.reduce((sum, d) => sum + (d.ret20d || 0), 0) / slice.length;
    buckets.push({
      bucket: i + 1,
      name: i === 0 ? 'Strong Sell' : i === 1 ? 'Mild Sell' : i === 2 ? 'Neutral' : i === 3 ? 'Mild Buy' : 'Strong Buy',
      count: slice.length,
      avgRet5d: avg5d,
      avgRet20d: avg20d
    });
  }

  const signals = data.map(d => d.signal);
  const rets5d = data.map(d => d.ret5d);
  
  const ic5d = spearman(signals, rets5d);
  
  return {
    name: signalName,
    count: data.length,
    ic5d,
    buckets
  };
}

function main() {
  const snaps = JSON.parse(fs.readFileSync(path.join(__dirname, 'snapshots.json')));
  const labels = JSON.parse(fs.readFileSync(path.join(__dirname, 'labels.json')));
  
  const dates = Object.keys(snaps).sort();
  
  const vcData = [];
  const ctaData = [];
  const rpData = [];
  
  for (const date of dates) {
    const snap = snaps[date];
    const lbl = labels[date];
    if (!lbl || lbl.futureReturn5d == null) continue;
    
    // Vol-Control
    if (snap.modules.volControl.status === 'ok' && snap.modules.volControl.dailyPositionChange != null) {
      vcData.push({
        signal: snap.modules.volControl.dailyPositionChange,
        ret1d: lbl.futureReturn1d,
        ret5d: lbl.futureReturn5d,
        ret20d: lbl.futureReturn20d
      });
    }
    
    // CTA
    if (snap.modules.ctaTrend.status === 'ok' && snap.modules.ctaTrend.aggregatePositionChange != null) {
      ctaData.push({
        signal: snap.modules.ctaTrend.aggregatePositionChange,
        ret1d: lbl.futureReturn1d,
        ret5d: lbl.futureReturn5d,
        ret20d: lbl.futureReturn20d
      });
    }
    
    // Risk Parity (using equity minus bond return as target)
    if (snap.modules.riskParity.status === 'ok' && snap.modules.riskParity.equityAllocationChange5d != null) {
      if (lbl.equityMinusBond5d != null) {
        rpData.push({
          signal: snap.modules.riskParity.equityAllocationChange5d,
          ret1d: lbl.futureReturn1d,
          ret5d: lbl.equityMinusBond5d, // target is relative return
          ret20d: lbl.futureReturn20d
        });
      }
    }
  }
  
  const results = {
    volControl: analyzeSignal(vcData, 'Vol-Control'),
    cta: analyzeSignal(ctaData, 'CTA Trend'),
    riskParity: analyzeSignal(rpData, 'Risk Parity (Target: Eq-Bond 5d Return)')
  };
  
  fs.writeFileSync(path.join(__dirname, 'results.json'), JSON.stringify(results, null, 2));
  console.log("Wrote results to results.json");
}

main();
