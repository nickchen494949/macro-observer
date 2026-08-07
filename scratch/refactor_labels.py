import re

with open('backtest/build_forward_labels.js', 'r') as f:
    content = f.read()

old_calc = """function calculateMaxDrawdown(prices) {
  if (!prices || prices.length === 0) return 0;
  let maxPx = prices[0];
  let maxDd = 0;
  for (let i = 1; i < prices.length; i++) {
    if (prices[i] > maxPx) {
      maxPx = prices[i];
    } else {
      const dd = (prices[i] - maxPx) / maxPx;
      if (dd < maxDd) maxDd = dd;
    }
  }
  return maxDd;
}"""

new_calc = """// True Intraday Path-Dependent Drawdown
function calculateMaxDrawdown(prices) {
  if (!prices || prices.length === 0) return 0;
  // prices should be an array of objects: { high, low, adjHigh, adjLow }
  let maxPx = prices[0].adjHigh;
  let maxDd = 0;
  for (let i = 1; i < prices.length; i++) {
    if (prices[i].adjHigh > maxPx) {
      maxPx = prices[i].adjHigh;
    }
    const dd = (prices[i].adjLow - maxPx) / maxPx;
    if (dd < maxDd) maxDd = dd;
  }
  return maxDd;
}"""
content = content.replace(old_calc, new_calc)

old_loop = """    // Evaluate per-module
    const mods = ['volControl', 'ctaEtfProxy', 'riskParityProxy', 'pensionRebalance'];
    for (const m of mods) {
      const mData = snap.modules[m];
      if (!mData || !mData.firstTradableSession) continue;
      
      const fts = mData.firstTradableSession;
      if (!spxMap.has(fts)) continue;
      
      const startIdx = spxMap.get(fts).idx;
      if (startIdx + 4 >= spxData.length) continue;
      
      const adjOpen_F = spxData[startIdx].adjOpen;
      const adjClose_F = spxData[startIdx].adjClose;
      const adjClose_F4 = spxData[startIdx + 4].adjClose;
      
      const ret1d = (adjClose_F / adjOpen_F) - 1;
      const ret5d = (adjClose_F4 / adjOpen_F) - 1;
      
      const prices5d = [];
      for (let i = startIdx; i <= startIdx + 4; i++) prices5d.push(spxData[i].adjClose);
      
      const mdd = calculateMaxDrawdown(prices5d);
      
      // We calculate a proxy MAE as max positive return
      let maxPx = prices5d[0];
      let maxMae = 0;
      for (let i = 1; i < prices5d.length; i++) {
        const r = (prices5d[i] - adjOpen_F) / adjOpen_F;
        if (r > maxMae) maxMae = r;
      }
      
      labels[date].modules[m] = {
        signalAvailableAt: mData.signalAvailableAt,
        firstTradableSession: fts,
        return1dOpen: Number(ret1d.toFixed(4)),
        return5dOpen: Number(ret5d.toFixed(4)),
        mae5d: Number(maxMae.toFixed(4)),
        mdd5d: Number(mdd.toFixed(4))
      };
    }"""

new_loop = """    // Evaluate per-module
    const mods = ['volControl', 'ctaEtfProxy', 'riskParity', 'pensionRebalance'];
    for (const m of mods) {
      const mData = snap.modules[m];
      if (!mData || !mData.firstTradableSession) continue;
      
      const fts = mData.firstTradableSession;
      if (!spxMap.has(fts)) continue;
      
      const startIdx = spxMap.get(fts).idx;
      
      // Insufficient future data check
      if (startIdx + 4 >= spxData.length) {
          labels[date].modules[m] = {
              signalAvailableAt: mData.signalAvailableAt,
              firstTradableSession: fts,
              labelStatus: "insufficient_future_data"
          };
          continue;
      }
      
      // Adjusted OHLC integrity check
      const d0 = spxData[startIdx];
      const adjRatio = d0.adjClose / d0.close;
      if (Math.abs(d0.adjOpen - (d0.open * adjRatio)) > 0.01) {
          labels[date].modules[m] = {
              signalAvailableAt: mData.signalAvailableAt,
              firstTradableSession: fts,
              labelStatus: "adjusted_ohlc_integrity_error"
          };
          continue;
      }

      const adjOpen_F = spxData[startIdx].adjOpen;
      const adjClose_F = spxData[startIdx].adjClose;
      const adjClose_F4 = spxData[startIdx + 4].adjClose;
      
      const ret1d = (adjClose_F / adjOpen_F) - 1;
      const ret5d = (adjClose_F4 / adjOpen_F) - 1;
      
      const prices5d = [];
      for (let i = startIdx; i <= startIdx + 4; i++) {
         prices5d.push(spxData[i]);
      }
      
      const mdd = calculateMaxDrawdown(prices5d);
      
      // Path-dependent MAE
      let maxPx = prices5d[0].adjHigh;
      let maxMae = 0;
      for (let i = 1; i < prices5d.length; i++) {
        const r = (prices5d[i].adjHigh - adjOpen_F) / adjOpen_F;
        if (r > maxMae) maxMae = r;
      }
      
      labels[date].modules[m] = {
        signalAvailableAt: mData.signalAvailableAt,
        firstTradableSession: fts,
        labelStatus: "ok",
        return1dOpen: Number(ret1d.toFixed(4)),
        return5dOpen: Number(ret5d.toFixed(4)),
        mae5d: Number(maxMae.toFixed(4)),
        mdd5d: Number(mdd.toFixed(4))
      };
    }"""
content = content.replace(old_loop, new_loop)

with open('backtest/build_forward_labels.js', 'w') as f:
    f.write(content)

# 10. Write true automated hard-gate tests.
# Write a bash script to run missing_data_logic_test.js?
