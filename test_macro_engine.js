const fs = require('fs');
const path = require('path');
const { evaluateDiagnostics } = require('./macro_engine');

// Load just the required json files for tests
function loadData(cutoffDate) {
  const store = { fred: {}, yahoo: {}, valuation: {} };
  ['fred', 'yahoo', 'valuation'].forEach(type => {
    const dir = path.join(__dirname, 'data', type);
    if (!fs.existsSync(dir)) return;
    fs.readdirSync(dir).filter(f => f.endsWith('.json')).forEach(f => {
      try {
        const d = JSON.parse(fs.readFileSync(path.join(dir, f)));
        let vals = d.values.filter(v => v[0] <= cutoffDate);
        store[type][d.id] = vals;
      } catch(e) {}
    });
  });
  return store;
}

// We need to run the mapping from server.js. We can cheat by requiring server.js 
// but server.js starts a server and loads all data globally.
