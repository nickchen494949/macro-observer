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
    previousState: null,
    modelConfig: {
      useEtfProxy: false
    }
  };
}

function runProductionFlows(store) {
  const config = buildProductionEngineInputs(store);
  return runFlowEngine(config);
}

function buildReplayEngineInputs(storeSlice, decisionDate, signalAvailableAt, marketDataAsOf, previousState) {
  return {
    decisionDate,
    signalAvailableAt,
    marketDataAsOf,
    inputsAsOfDecision: storeSlice, // Contains only data available BEFORE signalAvailableAt
    previousState,
    modelConfig: {
      useEtfProxy: true // Phase 1 specifies backtest uses ETF proxy
    }
  };
}

function runReplayFlows(storeSlice, decisionDate, signalAvailableAt, marketDataAsOf, previousState) {
  const config = buildReplayEngineInputs(storeSlice, decisionDate, signalAvailableAt, marketDataAsOf, previousState);
  return runFlowEngine(config);
}

module.exports = {
  buildProductionEngineInputs,
  runProductionFlows,
  buildReplayEngineInputs,
  runReplayFlows
};
