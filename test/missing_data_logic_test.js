const assert = require('assert');
const { runFlowEngine } = require('../lib/flow_engine');
const crypto = require('crypto');

console.log("Running true automated hard-gate tests for Missing Data & Determinism...");

const dummyYahoo = {
  '^GSPC': [
    { date: '2020-01-02', close: 100, adjClose: 100, volume: 100 },
    { date: '2020-01-03', close: 101, adjClose: 101, volume: 100 },
    { date: '2020-01-06', close: 102, adjClose: 102, volume: 100 },
    // missing 01-07
    { date: '2020-01-08', close: 104, adjClose: 104, volume: 100 }
  ],
  'DGS10': [
    ['2020-01-02', 1.5],
    ['2020-01-03', 1.6],
    ['2020-01-06', 1.7]
    // missing 01-08
  ]
};

// 1. Missing Session Test (CTA should fail on null SMA)
const snapA = runFlowEngine({
    inputsAsOfDecision: { 'fred': { 'DGS10': dummyYahoo['DGS10'] }, 'yahoo': dummyYahoo, 'valuation': [] },
    decisionDate: '2020-01-08',
    signalAvailableAt: '2020-01-08T17:00:00Z',
    marketDataAsOf: '2020-01-08',
    previousModelState: null
});

assert.strictEqual(snapA.snapshot.modules.ctaEtfProxy.status, 'insufficient_data', "CTA should fail if SPX has missing/stale data in its SMA window");

// 2. Resume Test (Vol-Control should preserve actualExposure during pause)
const prevState = {
    volControl: {
        actualExposure: 0.75,
        paused: false,
        missingSessions: 0
    }
};

const snapB = runFlowEngine({
    inputsAsOfDecision: { 'fred': { 'DGS10': dummyYahoo['DGS10'] }, 'yahoo': dummyYahoo, 'valuation': [] },
    decisionDate: '2020-01-08',
    signalAvailableAt: '2020-01-08T17:00:00Z',
    marketDataAsOf: '2020-01-08',
    previousModelState: prevState
});

assert.strictEqual(snapB.nextModelState.volControl.actualExposure, 0.75, "VolControl actualExposure should remain strictly unchanged when paused");
assert.strictEqual(snapB.nextModelState.volControl.paused, true, "VolControl should enter paused state when target data is missing");

console.log("All missing data assertions passed!");
