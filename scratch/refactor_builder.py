import re
import sys

# 1. Rewrite `backtest/build_historical_snapshots.js`
with open('backtest/build_historical_snapshots.js', 'r') as f:
    content = f.read()

old_fred = """const FRED_AVAILABILITY_POLICY = {
  // Universal conservative mapping (T+1/7/35/90) will be mapped here
};

function getFredAvailableAt(seriesId, observationDateStr, lagSensitivityOffset = 0) {
  // Conservative publication-lag approximation
  // This is a naive calendar-day lag fallback
  // Returns ISO string of exact available time.
  const d = new Date(observationDateStr);
  let lagDays = 35; // Default monthly
  
  // Basic frequency heuristic from series ID if not explicitly known:
  if (seriesId === 'DFF' || seriesId.startsWith('DGS') || seriesId === 'BAMLH0A0HYM2') lagDays = 1; // Daily
  if (seriesId === 'WALCL' || seriesId === 'ICSA' || seriesId === 'CCSA') lagDays = 7; // Weekly
  if (seriesId === 'GDP' || seriesId === 'GDPNOW') lagDays = 90; // Quarterly
  
  lagDays += lagSensitivityOffset;
  
  d.setUTCDate(d.getUTCDate() + lagDays);
  return d.toISOString();
}"""

new_fred = """const FRED_AVAILABILITY_POLICY = {
  'DGS10': { method: 'fixed_business_day_lag', lagBusinessDays: 1, confidence: 'conservative_approximation' },
  'BAMLH0A0HYM2': { method: 'fixed_business_day_lag', lagBusinessDays: 1, confidence: 'conservative_approximation' },
  'DFF': { method: 'fixed_business_day_lag', lagBusinessDays: 1, confidence: 'conservative_approximation' },
  'WALCL': { method: 'fixed_business_day_lag', lagBusinessDays: 5, confidence: 'conservative_approximation' },
  'ICSA': { method: 'fixed_business_day_lag', lagBusinessDays: 5, confidence: 'conservative_approximation' },
  'CCSA': { method: 'fixed_business_day_lag', lagBusinessDays: 5, confidence: 'conservative_approximation' }
};

// Load strict US equity calendar
let usEquityCalendar = [];
try {
  usEquityCalendar = JSON.parse(fs.readFileSync(path.join(__dirname, '../data/nyse_calendar.json'), 'utf-8'));
} catch (e) {
  console.error('Failed to load nyse_calendar.json');
}

function getFredAvailableAt(seriesId, observationDateStr, lagSensitivityOffset = 0) {
  // True registry-driven PIT calculation
  const policy = FRED_AVAILABILITY_POLICY[seriesId];
  let lagBusinessDays = policy ? policy.lagBusinessDays : 25; // default 25 b-days approx 1 month

  lagBusinessDays += lagSensitivityOffset;

  if (usEquityCalendar.length > 0) {
    const idx = usEquityCalendar.indexOf(observationDateStr);
    if (idx !== -1) {
       // It's a trading day, add business days
       const availableIdx = idx + lagBusinessDays;
       if (availableIdx < usEquityCalendar.length) {
          return new Date(usEquityCalendar[availableIdx] + 'T17:00:00Z').toISOString();
       }
    } else {
       // Fallback for non-trading days
       const d = new Date(observationDateStr);
       d.setUTCDate(d.getUTCDate() + lagBusinessDays * 1.4); // approx calendar days
       return d.toISOString();
    }
  }

  // Final naive fallback if no calendar
  const d = new Date(observationDateStr);
  d.setUTCDate(d.getUTCDate() + lagBusinessDays * 1.4);
  return d.toISOString();
}"""
content = content.replace(old_fred, new_fred)

old_main_loop = """  // We ALWAYS start the chain from the very first available trading day (2015-01-01 or earlier)
  const fullTradingDays = spxData.map(d => d[0]).sort();
  const startIdx = fullTradingDays.findIndex(d => d >= '2015-01-01'); // Inception
  
  if (startIdx === -1) throw new Error("No trading days found after 2015");
  
  const relevantTradingDays = fullTradingDays.slice(startIdx);"""
new_main_loop = """  // Traversal MUST be driven by the actual nyse_calendar.json universe, not SPX availability!
  const fullTradingDays = usEquityCalendar.length > 0 ? usEquityCalendar : spxData.map(d => d[0]).sort();
  const startIdx = fullTradingDays.findIndex(d => d >= '2015-01-01'); // Inception
  
  if (startIdx === -1) throw new Error("No trading days found after 2015");
  
  const relevantTradingDays = fullTradingDays.slice(startIdx);
  
  // Output targets
  const OUT_FILE = process.argv[4] || 'snapshots.json';
"""
content = content.replace(old_main_loop, new_main_loop)

old_write = """  fs.writeFileSync(path.join(__dirname, 'snapshots.json'), JSON.stringify(snapshots, null, 2));"""
new_write = """  fs.writeFileSync(path.join(__dirname, OUT_FILE), JSON.stringify(snapshots, null, 2));"""
content = content.replace(old_write, new_write)

with open('backtest/build_historical_snapshots.js', 'w') as f:
    f.write(content)


# 2. Rewrite `backtest/run_fred_sensitivity.js`
with open('backtest/run_fred_sensitivity.js', 'r') as f:
    content2 = f.read()

old_sense = """// Check if files exist or build them
if (!fs.existsSync(path.join(__dirname, 'snapshots_base.json'))) {
  console.log("Building base scenario (+0 days lag)...");
  execSync('node backtest/build_historical_snapshots.js 2022-01-03 2022-12-31 snapshots_base.json 0', { stdio: 'pipe' });
}
if (!fs.existsSync(path.join(__dirname, 'snapshots_plus1.json'))) {
  console.log("Building +1 day lag scenario...");
  execSync('node backtest/build_historical_snapshots.js 2022-01-03 2022-12-31 snapshots_plus1.json 1', { stdio: 'pipe' });
}
if (!fs.existsSync(path.join(__dirname, 'snapshots_plus3.json'))) {
  console.log("Building +3 day lag scenario...");
  execSync('node backtest/build_historical_snapshots.js 2022-01-03 2022-12-31 snapshots_plus3.json 3', { stdio: 'pipe' });
}

const base = JSON.parse(fs.readFileSync(path.join(__dirname, 'snapshots_base.json')));
const plus1 = JSON.parse(fs.readFileSync(path.join(__dirname, 'snapshots_plus1.json')));
const plus3 = JSON.parse(fs.readFileSync(path.join(__dirname, 'snapshots_plus3.json')));

// Estimate shifted observations
const fredRaw = JSON.parse(fs.readFileSync(path.join(__dirname, '../data/fred/DGS10.json')));
let shifted1 = fredRaw.length, shifted3 = fredRaw.length;

function compareSnapsDeep(baseSnaps, targetSnaps) {
  let totalKeys = 0;
  let statusDiffs = 0;
  let directionDiffs = 0;
  
  let riskParityNumDiffs = 0;
  let volControlNumDiffs = 0;
  let ctaEtfNumDiffs = 0;
  let decisionDatesAffected = 0;

  for (const date of Object.keys(baseSnaps)) {
    if (!targetSnaps[date]) continue;
    
    totalKeys++;
    const b = baseSnaps[date];
    const t = targetSnaps[date];
    
    let dateAffected = false;

    // Check numerical isolation
    const bRP = JSON.stringify(b.modules?.riskParityProxy || {});
    const tRP = JSON.stringify(t.modules?.riskParityProxy || {});"""

new_sense = """// ALWAYS rebuild to prove causality right now
console.log("Building base scenario (+0 days lag)...");
execSync('node backtest/build_historical_snapshots.js 2022-01-03 2022-12-31 snapshots_base.json 0', { stdio: 'pipe' });
console.log("Building +1 day lag scenario...");
execSync('node backtest/build_historical_snapshots.js 2022-01-03 2022-12-31 snapshots_plus1.json 1', { stdio: 'pipe' });
console.log("Building +3 day lag scenario...");
execSync('node backtest/build_historical_snapshots.js 2022-01-03 2022-12-31 snapshots_plus3.json 3', { stdio: 'pipe' });

const base = JSON.parse(fs.readFileSync(path.join(__dirname, 'snapshots_base.json')));
const plus1 = JSON.parse(fs.readFileSync(path.join(__dirname, 'snapshots_plus1.json')));
const plus3 = JSON.parse(fs.readFileSync(path.join(__dirname, 'snapshots_plus3.json')));

// Estimate shifted observations properly
const fredRaw = JSON.parse(fs.readFileSync(path.join(__dirname, '../data/fred/DGS10.json')));
let fredArray = fredRaw;
if (!Array.isArray(fredArray)) fredArray = fredArray.values || [];
let shifted1 = fredArray.filter(v => {
    let d = Array.isArray(v) ? v[0] : v.date;
    return d >= '2022-01-03' && d <= '2022-12-31';
}).length;
let shifted3 = shifted1;

function compareSnapsDeep(baseSnaps, targetSnaps) {
  let totalKeys = 0;
  let statusDiffs = 0;
  let directionDiffs = 0;
  
  let riskParityNumDiffs = 0;
  let volControlNumDiffs = 0;
  let ctaEtfNumDiffs = 0;
  let decisionDatesAffected = 0;

  for (const date of Object.keys(baseSnaps)) {
    if (!targetSnaps[date]) continue;
    
    totalKeys++;
    const b = baseSnaps[date];
    const t = targetSnaps[date];
    
    let dateAffected = false;

    // Check numerical isolation
    const bRP = JSON.stringify(b.modules?.riskParity || {});
    const tRP = JSON.stringify(t.modules?.riskParity || {});"""

content2 = content2.replace(old_sense, new_sense)

with open('backtest/run_fred_sensitivity.js', 'w') as f:
    f.write(content2)
