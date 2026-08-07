const { runFlowEngine } = require('./flow_engine');

function buildProductionEngineInputs(store) {
  // In production, the inputs are exactly what's in the global store.
  // The store contains real-time downloaded data.
  // We make a shallow copy or pass it directly.
  return {
    decisionDate: new Date().toISOString().split('T')[0],
    signalAvailableAt: new Date().toISOString(),
    marketDataAsOf: new Date().toISOString().split('T')[0],
    inputsAsOfDecision: store,
    previousModelState: null,
    modelConfig: {
      useEtfProxy: false
    }
  };
}

function runProductionFlows(store) {
  const config = buildProductionEngineInputs(store);
  const { snapshot, nextModelState } = runFlowEngine(config);
  return snapshot; // Production API only needs snapshot currently
}

function buildReplayEngineInputs(storeSlice, decisionDate, signalAvailableAt, marketDataAsOf, previousModelState) {
  return {
    decisionDate,
    signalAvailableAt,
    marketDataAsOf,
    inputsAsOfDecision: storeSlice, // Contains only data available BEFORE signalAvailableAt
    previousModelState,
    modelConfig: {
      useEtfProxy: true // Phase 1 specifies backtest uses ETF proxy
    }
  };
}

function runReplayFlows(storeSlice, decisionDate, signalAvailableAt, marketDataAsOf, previousModelState) {
  const config = buildReplayEngineInputs(storeSlice, decisionDate, signalAvailableAt, marketDataAsOf, previousModelState);
  return runFlowEngine(config); // Returns { snapshot, nextModelState }
}

module.exports = {
  buildProductionEngineInputs,
  runProductionFlows,
  buildReplayEngineInputs,
  runReplayFlows
};
