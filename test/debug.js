const { runFlowEngine } = require('../lib/flow_engine');

const fullCal = [];
for (let i = 1; i <= 250; i++) {
    let d = new Date('2019-01-01');
    d.setDate(d.getDate() + i);
    let ds = d.toISOString().split('T')[0];
    if (d.getDay() !== 0 && d.getDay() !== 6) {
        fullCal.push(ds);
    }
}
fullCal.push('2020-01-07');
fullCal.push('2020-01-08');
fullCal.push('2020-01-09');
fullCal.sort();

const makePerfectYahoo = () => {
    const dy = {
      '^GSPC': [], 'SPY': [], 'QQQ': [], 'IWM': [], 'IEF': [], 'GLD': [], 'USO': [], '^VIX': [], 'SOXX': [], '^IXIC': []
    };
    let val = 100;
    for (const ds of fullCal) {
        val = val * (1 + (Math.random()-0.5)*0.01);
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

const dyA = makePerfectYahoo();
for (const k of Object.keys(dyA)) dyA[k] = dyA[k].filter(row => row[0] !== '2020-01-07');
const dfA = makePerfectFred();

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
console.log("snapB missingSessions:", snapB.nextModelState.volControl.missingSessions);

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
console.log("snapC volControl:", snapC.nextModelState.volControl);
