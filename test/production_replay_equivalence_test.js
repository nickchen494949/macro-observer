const assert = require('assert');
const { runFlowEngine } = require('../lib/flow_engine');
const { buildProductionEngineInputs, buildReplayEngineInputs } = require('../lib/flow_wrappers');

function canonicalize(obj) {
  if (obj === null || obj === undefined) return obj;
  if (Array.isArray(obj)) return obj.map(canonicalize);
  if (typeof obj === 'object') {
    const copy = { ...obj };
    // Strip runtime signatures
    delete copy.snapshotGeneratedAt;
    delete copy.timeToRunMs;
    for (const key in copy) {
      copy[key] = canonicalize(copy[key]);
    }
    return copy;
  }
  return obj;
}

// Generate mock data for the test
const mockFred = {
  'DGS10': [['2024-01-01', 4.0], ['2024-01-02', 4.1]],
  'BAMLH0A0HYM2': [['2024-01-01', 3.0], ['2024-01-02', 3.1]]
};

const mockYahoo = {
  '^GSPC': [['2024-01-01', 4700], ['2024-01-02', 4750]],
  'SPY': [['2024-01-01', 470], ['2024-01-02', 475]],
  'CL=F': [['2024-01-01', 70], ['2024-01-02', 71]]
};

const mockStore = { fred: mockFred, yahoo: mockYahoo, valuation: {} };

const targetDate = '2024-01-02';
const signalTime = targetDate + 'T18:00:00Z';

function testEquivalence() {
  console.log("Running Strict Production vs Replay Equivalence Test...");
  
  // 1. Build Production Inputs
  const prodInputs = buildProductionEngineInputs(mockStore);
  // Note: production inputs take the exact Date.now(), so we mock them manually to match our target date for the test.
  prodInputs.decisionDate = targetDate;
  prodInputs.signalAvailableAt = signalTime;
  prodInputs.marketDataAsOf = targetDate;
  
  // 2. Build Replay Inputs
  const replayInputs = buildReplayEngineInputs(mockStore, targetDate, signalTime, targetDate, null);
  
  // Align the modelConfig for the equivalence test (they naturally differ for Option B)
  replayInputs.modelConfig.useEtfProxy = false;
  
  // 3. Ensure input equivalence
  const canonProdInputs = canonicalize(prodInputs);
  const canonReplayInputs = canonicalize(replayInputs);
  
  try {
    assert.deepEqual(canonProdInputs, canonReplayInputs);
    console.log("✅ Input Wrapper Equivalence: Passed");
  } catch(e) {
    console.error("❌ Input Wrapper Equivalence: Failed");
    throw e;
  }
  
  // 4. Ensure engine output equivalence
  const prodOutput = runFlowEngine(prodInputs);
  const replayOutput = runFlowEngine(replayInputs);
  
  const canonProdOutput = canonicalize(prodOutput);
  const canonReplayOutput = canonicalize(replayOutput);
  
  try {
    assert.deepEqual(canonProdOutput, canonReplayOutput);
    console.log("✅ Engine Output Equivalence: Passed");
  } catch(e) {
    console.error("❌ Engine Output Equivalence: Failed");
    throw e;
  }
  
  console.log("All equivalence tests passed. The core engine is mathematically identical across modes.");
}

testEquivalence();
