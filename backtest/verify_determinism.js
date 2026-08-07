const assert = require('assert');
const { runFlowEngine } = require('../lib/flow_engine');
const { buildProductionEngineInputs, buildReplayEngineInputs } = require('../lib/flow_wrappers');

// Mock a simple store with just enough data to run the engine (or load it from a fixture)
const fs = require('fs');
const store = {
  fred: { 'DGS10': [['2026-08-01', 4.0]] },
  yahoo: { '^GSPC': [['2026-08-01', 5000]] },
  valuation: {}
};

// Test equivalence
console.log('Building inputs...');
const prodInput = buildProductionEngineInputs(store);
// For replay to be identical to prod, decisionDate must be today, signalAvailableAt must be same, etc.
const replayInput = buildReplayEngineInputs(
  store,
  prodInput.decisionDate, 
  prodInput.signalAvailableAt, 
  prodInput.marketDataAsOf, 
  null
);

// We must align the modelConfig so they are mathematically equivalent for the test
replayInput.modelConfig.useEtfProxy = prodInput.modelConfig.useEtfProxy;

console.log('Running mathematically pure engine...');
const A = runFlowEngine(prodInput);
const B = runFlowEngine(replayInput);

if (A.snapshot) delete A.snapshot.snapshotGeneratedAt;
if (B.snapshot) delete B.snapshot.snapshotGeneratedAt;

// Core Equivalence
console.log('Verifying bit-for-bit equivalence...');
assert.deepStrictEqual(A, B, "Core equivalence failed: Mathematical output of runFlowEngine differed between production and replay wrappers.");

console.log('Determinism OK');
