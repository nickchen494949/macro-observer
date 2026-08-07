const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

console.log("Running automated hard-gate tests for Forward Labels...");

// Backup
const spxPath = path.join(__dirname, '../data/yahoo/_GSPC.json');
const snapPath = path.join(__dirname, '../backtest/snapshots.json');
const spxBackup = fs.readFileSync(spxPath);
const snapBackup = fs.existsSync(snapPath) ? fs.readFileSync(snapPath) : null;

try {
    const testData = {
        "2023-01-03": {
            "decisionDate": "2023-01-03",
            "modules": {
                "volControl": {
                    "signalAvailableAt": "2023-01-03T22:00:00.000Z",
                    "firstTradableSession": "2023-01-04"
                }
            }
        }
    };
    fs.writeFileSync(snapPath, JSON.stringify(testData));

    const dummyYahoo = { values: [
        { date: "2023-01-03", open: 100, close: 100, adjOpen: 100, adjClose: 100, adjHigh: 102, adjLow: 98, high: 102, low: 98 },
        { date: "2023-01-04", open: 101, close: 105, adjOpen: 101, adjClose: 105, adjHigh: 106, adjLow: 100, high: 106, low: 100 }, // fts
        { date: "2023-01-05", open: 105, close: 102, adjOpen: 105, adjClose: 102, adjHigh: 106, adjLow: 90, high: 106, low: 90 }, // large drawdown
        { date: "2023-01-06", open: 102, close: 104, adjOpen: 102, adjClose: 104, adjHigh: 105, adjLow: 101, high: 105, low: 101 },
        { date: "2023-01-09", open: 104, close: 106, adjOpen: 104, adjClose: 106, adjHigh: 107, adjLow: 103, high: 107, low: 103 },
        { date: "2023-01-10", open: 106, close: 110, adjOpen: 106, adjClose: 110, adjHigh: 111, adjLow: 105, high: 111, low: 105 } // h=5 from fts
    ] };
    fs.writeFileSync(spxPath, JSON.stringify(dummyYahoo));

    execSync('node backtest/build_forward_labels.js', { stdio: 'pipe', cwd: path.join(__dirname, '..') });

    const labels = JSON.parse(fs.readFileSync(path.join(__dirname, '../backtest/forward_labels.json')));
    const mData = labels["2023-01-03"].modules.volControl;

    // 1. h=1 off-by-one check
    assert.strictEqual(mData.return1dOpen, Number((105 / 101 - 1).toFixed(4)), "h=1 must be adjClose_F / adjOpen_F");

    // 2. h=5 exactly 5 sessions check
    assert.strictEqual(mData.return5dOpen, Number((110 / 101 - 1).toFixed(4)), "h=5 must be adjClose_F4 / adjOpen_F");

    // 3. MDD logic
    assert.strictEqual(mData.mdd5d, Number(((90 - 106) / 106).toFixed(4)), "MDD must be correctly computed on adjHigh to adjLow");

    // 4. Insufficient Future Data
    const shortYahoo = { values: dummyYahoo.values.slice(0, 4) };
    fs.writeFileSync(spxPath, JSON.stringify(shortYahoo));
    execSync('node backtest/build_forward_labels.js', { stdio: 'pipe', cwd: path.join(__dirname, '..') });
    const labels2 = JSON.parse(fs.readFileSync(path.join(__dirname, '../backtest/forward_labels.json')));
    assert.strictEqual(labels2["2023-01-03"].modules.volControl.labelStatus, "insufficient_future_data", "Must flag insufficient_future_data");

    // 5. Adjusted OHLC Invariant
    const badOhlc = { values: [...dummyYahoo.values] };
    badOhlc.values[1] = { date: "2023-01-04", open: 101, close: 105, adjOpen: 90, adjClose: 105, adjHigh: 106, adjLow: 100, high: 106, low: 100 };
    fs.writeFileSync(spxPath, JSON.stringify(badOhlc));
    execSync('node backtest/build_forward_labels.js', { stdio: 'pipe', cwd: path.join(__dirname, '..') });
    const labels3 = JSON.parse(fs.readFileSync(path.join(__dirname, '../backtest/forward_labels.json')));
    assert.strictEqual(labels3["2023-01-03"].modules.volControl.labelStatus, "adjusted_ohlc_integrity_error", "Must flag adjusted_ohlc_integrity_error");

    console.log("All forward label assertions passed!");
} finally {
    // Restore
    fs.writeFileSync(spxPath, spxBackup);
    if (snapBackup) fs.writeFileSync(snapPath, snapBackup);
    else fs.rmSync(snapPath);
}
