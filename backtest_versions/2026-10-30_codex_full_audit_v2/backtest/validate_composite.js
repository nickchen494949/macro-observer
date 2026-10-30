const fs = require('fs');
const path = require('path');

function main() {
  const snaps = JSON.parse(fs.readFileSync(path.join(__dirname, 'snapshots.json')));
  const labels = JSON.parse(fs.readFileSync(path.join(__dirname, 'labels.json')));
  
  const dates = Object.keys(snaps).sort();
  
  const groups = {
    'buying': [],
    'selling': [],
    'conflicting': [],
    'none': []
  };
  
  for (const date of dates) {
    const snap = snaps[date];
    const lbl = labels[date];
    if (!lbl || lbl.futureReturn5d == null) continue;
    
    const dir = snap.summary.timelinePressures.ongoing1To5Days.direction;
    if (groups[dir]) {
      groups[dir].push(lbl);
    }
  }
  
  const results = {};
  for (const [dir, lbls] of Object.entries(groups)) {
    if (lbls.length === 0) continue;
    
    const avg5d = lbls.reduce((sum, d) => sum + d.futureReturn5d, 0) / lbls.length;
    const known20 = lbls.filter(d => Number.isFinite(d.futureReturn20d));
    const avg20d = known20.length ? known20.reduce((sum, d) => sum + d.futureReturn20d, 0) / known20.length : NaN;
    
    const hitRate5d = lbls.filter(d => d.futureReturn5d > 0).length / lbls.length;
    const hitRate20d = known20.length ? known20.filter(d => d.futureReturn20d > 0).length / known20.length : NaN;
    
    results[dir] = {
      count: lbls.length, count20d: known20.length,
      avgRet5d: avg5d,
      avgRet20d: avg20d,
      hitRate5d: hitRate5d,
      hitRate20d: hitRate20d
    };
  }
  
  fs.writeFileSync(path.join(__dirname, 'composite_results.json'), JSON.stringify(results, null, 2));
  console.log("Wrote composite results to composite_results.json");
}

// Legacy flat labels have no execution-time/availability contract and incompatible snapshot fields.
if (require.main === module) {
  console.error('BLOCKED_LEGACY_SCHEMA: use test/phase3_validation and phase4_composite_validation; legacy statistics are not certified results.');
  process.exitCode = 2;
}

