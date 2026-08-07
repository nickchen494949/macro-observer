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
  // prices should be an array of objects: { adjHigh, adjLow }
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
      const lows5d = [];
      for (let j = 0; j <= 4; j++) {
        prices5d.push(spxData[startIdx + j].adjClose);
        lows5d.push(spxData[startIdx + j].adjLow);
      }
      
      // MAE_h: from entry AdjOpen_F to worst AdjLow
      let mae = 0;
      for (const l of lows5d) {
        const dd = (l - adjOpen_F) / adjOpen_F;
        if (dd < mae) mae = dd;
      }
      
      const mdd = calculateMaxDrawdown(prices5d);
      
      labels[date].modules[m] = {
        signalAvailableAt: mData.signalAvailableAt,
        firstTradableSession: fts,
        return1dOpen: ret1d,
        return5dOpen: ret5d,
        mae5d: mae,
        mdd5d: mdd
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
      const lows5d = [];
      for (let j = 0; j <= 4; j++) {
        prices5d.push({
           adjHigh: spxData[startIdx + j].adjHigh,
           adjLow: spxData[startIdx + j].adjLow
        });
        lows5d.push(spxData[startIdx + j].adjLow);
      }
      
      // MAE_h: from entry AdjOpen_F to worst AdjLow
      let mae = 0;
      for (const l of lows5d) {
        const dd = (l - adjOpen_F) / adjOpen_F;
        if (dd < mae) mae = dd;
      }
      
      const mdd = calculateMaxDrawdown(prices5d);
      
      labels[date].modules[m] = {
        signalAvailableAt: mData.signalAvailableAt,
        firstTradableSession: fts,
        labelStatus: "ok",
        return1dOpen: Number(ret1d.toFixed(4)),
        return5dOpen: Number(ret5d.toFixed(4)),
        mae5d: Number(mae.toFixed(4)),
        mdd5d: Number(mdd.toFixed(4))
      };
    }"""
content = content.replace(old_loop, new_loop)

# Fix composite
old_comp = """      const mData = snap.modules[m];
      if (mData && mData.firstTradableSession) {
        if (!maxSig || mData.signalAvailableAt > maxSig) {
          maxSig = mData.signalAvailableAt;
        }
        if (!compFts || mData.firstTradableSession > compFts) {
          compFts = mData.firstTradableSession;
        }
      }"""

new_comp = """      const mData = snap.modules[m];
      if (mData && mData.firstTradableSession) {
        if (!maxSig || mData.signalAvailableAt > maxSig) {
          maxSig = mData.signalAvailableAt;
        }
        if (!compFts || mData.firstTradableSession > compFts) {
          compFts = mData.firstTradableSession;
        }
      }"""
content = content.replace(old_comp, new_comp)

with open('backtest/build_forward_labels.js', 'w') as f:
    f.write(content)
