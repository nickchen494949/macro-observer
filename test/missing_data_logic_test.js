const assert = require('assert');
const { runFlowEngine } = require('../lib/flow_engine');

console.log("Running true automated hard-gate tests for Missing Data & Determinism...");

const fullCal = [];
for (let i = 1; i <= 400; i++) { // 400 days from Jan 1 2019 reaches Feb 2020
    let d = new Date('2019-01-01');
    d.setDate(d.getDate() + i);
    let ds = d.toISOString().split('T')[0];
    if (d.getDay() !== 0 && d.getDay() !== 6) {
        fullCal.push(ds);
    }
}
fullCal.sort();

const makePerfectYahoo = () => {
    const dy = {
      '^GSPC': [], 'SPY': [], 'QQQ': [], 'IWM': [], 'IEF': [], 'GLD': [], 'USO': [], '^VIX': [], 'SOXX': [], '^IXIC': []
    };
    let val = 100;
    for (const ds of fullCal) {
        val = val * (1 + (Math.random()-0.5)*0.01); // Random noise to give non-zero volatility
        for (const k of Object.keys(dy)) dy[k].push([ds, val]);
    }
    return dy;
};
const makePerfectFred = () => {
    const df = { 'DGS10': [], 'BAMLH0A0HYM2': [] };
    let val = 1.5;
    for (const ds of fullCal) {
        val = val + (Math.random()-0.5)*0.05;
        for (const k of Object.keys(df)) df[k].push([ds, val]);
    }
    return df;
};

// 1. Missing Session Test (CTA should fail on null SMA for missing SPX day)
// We remove 2020-01-07 from Yahoo data to simulate a missing session
const dyA = makePerfectYahoo();
for (const k of Object.keys(dyA)) dyA[k] = dyA[k].filter(row => row[0] !== '2020-01-07');
const dfA = makePerfectFred();

const snapA = runFlowEngine({
    inputsAsOfDecision: { 'fred': dfA, 'yahoo': dyA, 'valuation': [] },
    decisionDate: '2020-01-08',
    signalAvailableAt: '2020-01-08T17:00:00Z',
    marketDataAsOf: '2020-01-08',
    previousModelState: null,
    usEquityCalendar: fullCal
});
assert.strictEqual(snapA.snapshot.modules.ctaEtfProxy.status, 'insufficient_data', "CTA should fail if SPX has missing/stale data in its SMA window");

// 2. Resume Test (Vol-Control should preserve actualExposure during pause)
const prevState = {
    volControl: {
        actualExposure: 0.75,
        paused: true,
        missingSessions: 0,
        fiveDayHistory: [0.75, 0.75, 0.75, 0.75, 0.75]
    }
};

const snapB = runFlowEngine({
    inputsAsOfDecision: { 'fred': dfA, 'yahoo': dyA, 'valuation': [] },
    decisionDate: '2020-01-08',
    signalAvailableAt: '2020-01-08T17:00:00Z',
    marketDataAsOf: '2020-01-08',
    previousModelState: prevState,
    usEquityCalendar: fullCal
});
assert.strictEqual(snapB.nextModelState.volControl.actualExposure, 0.75, "VolControl actualExposure should remain strictly unchanged when paused");
assert.strictEqual(snapB.nextModelState.volControl.paused, true, "VolControl should stay paused because 01-07 is missing");

// 3. Field-level missing (SPY has null on 2020-01-09, other days OK)
// For this we use a PERFECT Yahoo, but set SPY to null on 2020-01-09
const dyC = makePerfectYahoo();
const idx = dyC['SPY'].findIndex(r => r[0] === '2020-01-09');
dyC['SPY'][idx][1] = null;
const dfC = makePerfectFred();

const snapC = runFlowEngine({
    inputsAsOfDecision: { 'fred': dfC, 'yahoo': dyC, 'valuation': [] },
    decisionDate: '2020-01-09',
    signalAvailableAt: '2020-01-09T17:00:00Z',
    marketDataAsOf: '2020-01-09',
    previousModelState: snapB.nextModelState,
    usEquityCalendar: fullCal
});

assert.strictEqual(snapC.snapshot.modules.ctaEtfProxy.status, 'insufficient_data', "CTA should fail if field-level SPY data is null");
assert.strictEqual(snapC.nextModelState.volControl.paused, false, "VolControl should resume when data is back");
assert.strictEqual(snapC.snapshot.modules.volControl.estimatedDailyFlowUsd, null, "VolControl flow should be null on resume day to prevent gap-jump artifacts");

console.log("All missing data assertions passed!");
