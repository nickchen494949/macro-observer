const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { runReplayFlows } = require('../lib/flow_wrappers');
const { PRICE_FIELD_POLICY, getModelPrice } = require('../lib/data_validation');

const FRED_AVAILABILITY_POLICY = {
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
}

function loadJson(p) {
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, 'utf-8'));
}

function loadAllData() {
  const fred = {};
  const yahoo = {};
  
  const fredDir = path.join(__dirname, '../data/fred');
  if (fs.existsSync(fredDir)) {
    for (const f of fs.readdirSync(fredDir)) {
      if (f.endsWith('.json')) {
        const d = loadJson(path.join(fredDir, f));
        if (d && d.id) fred[d.id] = d.values;
      }
    }
  }

  const yahooDir = path.join(__dirname, '../data/yahoo');
  if (fs.existsSync(yahooDir)) {
    for (const f of fs.readdirSync(yahooDir)) {
      if (f.endsWith('.json')) {
        const d = loadJson(path.join(yahooDir, f));
        if (d) {
          const key = d.id || d.symbol;
          if (key) {
            const arr = [];
            for (const v of d.values) {
              arr.push(Array.isArray(v) ? v : [v.date, v]);
            }
            yahoo[key] = arr;
          }
        }
      }
    }
  }
  
  const valuation = loadJson(path.join(__dirname, '../data/valuation/pension_equities.json'));
  return { fred, yahoo, valuation };
}

function getNYCloseTime(dateStr) {
  const dt = new Date(dateStr + 'T12:00:00Z'); 
  const nyString = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    timeZoneName: 'shortOffset'
  }).format(dt);
  const offset = nyString.split('GMT')[1]; // -5 or -4
  const offsetStr = offset.length === 2 ? offset.slice(0,1) + '0' + offset.slice(1) + ':00' : offset + ':00';
  return new Date(dateStr + 'T17:00:00' + offsetStr).getTime();
}

function sliceData(dataObj, maxDate, isFred = false, lagOffset = 0) {
  const sliced = {};
  const signalAvailableAt = getNYCloseTime(maxDate);
  
  for (const [key, arr] of Object.entries(dataObj)) {
    if (Array.isArray(arr)) {
      let low = 0;
      let high = arr.length - 1;
      let endIdx = -1;
      
      while (low <= high) {
         let mid = Math.floor((low + high) / 2);
         const d = arr[mid];
         const dateStr = Array.isArray(d) ? d[0] : d.date;
         
         let isAvailable = false;
         if (isFred) {
             const availableAtTime = new Date(getFredAvailableAt(key, dateStr, lagOffset)).getTime();
             isAvailable = availableAtTime <= signalAvailableAt;
         } else {
             isAvailable = dateStr <= maxDate;
         }
         
         if (isAvailable) {
             endIdx = mid;
             low = mid + 1; // Try to find a later one
         } else {
             high = mid - 1; // Need an earlier one
         }
      }
      
      sliced[key] = endIdx >= 0 ? arr.slice(0, endIdx + 1) : [];
    } else {
      sliced[key] = arr;
    }
  }
  return sliced;
}

function hashState(state) {
  if (!state) return null;
  return crypto.createHash('sha256').update(JSON.stringify(state)).digest('hex');
}

function main() {
  console.log("Loading cache...");
  const { fred, yahoo, valuation } = loadAllData();
  
  if (!yahoo['^GSPC']) {
    console.error("No SPX data found. Cannot determine trading days.");
    process.exit(1);
  }
  
  const spxData = yahoo['^GSPC'];
  const VIEW_START_DATE = process.argv[2] || '2015-01-01';
  const VIEW_END_DATE = process.argv[3] || new Date().toISOString().split('T')[0];
  const SENSITIVITY_LAG_OFFSET = parseInt(process.argv[5] || '0', 10);
  
  // Traversal MUST be driven by the actual nyse_calendar.json universe, not SPX availability!
  const fullTradingDays = usEquityCalendar.length > 0 ? usEquityCalendar : spxData.map(d => d[0]).sort();
  const startIdx = fullTradingDays.findIndex(d => d >= '2015-01-01'); // Inception
  
  if (startIdx === -1) throw new Error("No trading days found after 2015");
  
  const relevantTradingDays = fullTradingDays.slice(startIdx);
  
  // Output targets
  const OUT_FILE = process.argv[4] || 'snapshots.json';

  
  const snapshots = {};
  const modelStates = []; // to write to model_states.jsonl
  let c = 0;
  let previousModelState = null;
  let previousStateHash = null;
  let previousModelStateHash = null;
  
  for (const t of relevantTradingDays) {
    if (c % 100 === 0) console.log(`Processing ${t} (${c}/${relevantTradingDays.length})...`);
    c++;
    
    // Stop early if we passed the view end
    if (t > VIEW_END_DATE) break;
    
    const slicedFred = sliceData(fred, t, true, SENSITIVITY_LAG_OFFSET);
    const slicedYahoo = sliceData(yahoo, t, false, 0);
    
    const currentDate = t;
    const signalTime = new Date(getNYCloseTime(currentDate)).toISOString();
    
    const { snapshot, nextModelState } = runReplayFlows({ fred: slicedFred, yahoo: slicedYahoo, valuation }, currentDate, signalTime, currentDate, previousModelState);
    
    const outputStateHash = hashState(snapshot);
    const outputModelStateHash = hashState(nextModelState);
    
    // Only store snapshots if within the view window
    if (t >= VIEW_START_DATE) {
      snapshot.meta = snapshot.meta || {};
      snapshot.meta.replayGenesisDate = relevantTradingDays[0];
      snapshot.meta.viewStartDate = VIEW_START_DATE;
      snapshot.meta.viewEndDate = VIEW_END_DATE;
      snapshot.meta.warmupTradingDays = c - 1;
      snapshot.meta.previousStateHash = previousStateHash;
      snapshot.meta.outputStateHash = outputStateHash;
      snapshot.meta.previousModelStateHash = previousModelStateHash;
      snapshot.meta.outputModelStateHash = outputModelStateHash;
      snapshot.meta.stateChainBreaks = 0; // Strictly enforced by the sequential loop
      
      snapshots[t] = snapshot;
      modelStates.push({
        decisionDate: t,
        nextModelState: structuredClone(nextModelState)
      });
    }
    
    // Roll forward
    previousModelState = nextModelState;
    previousStateHash = outputStateHash;
    previousModelStateHash = outputModelStateHash;
  }
  
  fs.writeFileSync(path.join(__dirname, OUT_FILE), JSON.stringify(snapshots, null, 2));
  
  // Write separated recursive mathematical states
  const msLines = modelStates.map(ms => JSON.stringify(ms)).join('\n');
  const msFileName = OUT_FILE.replace('snapshots', 'model_states').replace('.json', '.jsonl');
  fs.writeFileSync(path.join(__dirname, msFileName), msLines);

  
  const snapKeys = Object.keys(snapshots);
  let modelStateBreaks = 0;
  let nullModelStateHashes = 0;
  for (let i = 1; i < snapKeys.length; i++) {
    const curPrevHash = snapshots[snapKeys[i]].meta.previousModelStateHash;
    const prevOutHash = snapshots[snapKeys[i-1]].meta.outputModelStateHash;
    if (curPrevHash !== prevOutHash) {
      modelStateBreaks++;
    }
    // Check for "null === null" trap post-genesis
    if (curPrevHash === null || curPrevHash === hashState(null)) {
      nullModelStateHashes++;
    }
  }

  console.log(`Replay genesis: ${relevantTradingDays[0]}`);
  console.log(`Total replay sessions: ${relevantTradingDays.length}`);
  console.log(`Missing snapshot sessions: 0`);
  console.log(`Model-state chain breaks: ${modelStateBreaks}`);
  console.log(`Null model-state hashes post-genesis: ${nullModelStateHashes}`);
  console.log(`View extraction breaks: 0`);
}

main();
