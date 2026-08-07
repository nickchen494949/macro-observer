const assert = require('assert');
const { canonicalize } = require('../lib/canonicalize');
const { buildProductionEngineInputs, buildReplayEngineInputs } = require('../lib/flow_wrappers');

const dummyStore = {
  fred: { 'DGS10': [['2024-01-01', 4.0]] },
  yahoo: { 'SPY': [['2024-01-01', 500]] }
};

function testEquivalency() {
  const prodInputs = buildProductionEngineInputs(dummyStore);
  const replayInputs = buildReplayEngineInputs(
    dummyStore,
    prodInputs.decisionDate,
    prodInputs.signalAvailableAt,
    prodInputs.marketDataAsOf,
    prodInputs.previousState
  );

  // modelConfig is intentionally different between the two (useEtfProxy true vs false),
  // but we can assert the base inputs (store) map exactly the same.
  assert.deepEqual(canonicalize(prodInputs.inputsAsOfDecision), canonicalize(replayInputs.inputsAsOfDecision));
  
  console.log('✅ Input equivalency assertion passed (canonicalize).');
}

testEquivalency();
