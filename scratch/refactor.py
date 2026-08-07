import re
import sys

with open('lib/flow_engine.js', 'r') as f:
    content = f.read()

# 1. Update runFlowEngine signature to destructure config properly and add nextModelState
# We also need to extract `previousModelState = config.previousModelState` instead of `previousState`
content = content.replace(
    "const { decisionDate, signalAvailableAt, marketDataAsOf, inputsAsOfDecision, previousState, modelConfig } = config;",
    "const { decisionDate, signalAvailableAt, marketDataAsOf, inputsAsOfDecision, previousModelState, modelConfig } = config;\n  const nextModelState = {};"
)

# 2. Fix the getDailyReturns to not calculate across nulls!
old_returns = """  const getDailyReturns = (arr, days) => {
    if (!arr || arr.length <= days) return [];
    const returns = [];
    const start = arr.length - days - 1;
    for (let i = start + 1; i < arr.length; i++) {
      if (arr[i][1] == null || arr[i - 1][1] == null) return null;
      returns.push(Math.log(arr[i][1] / arr[i - 1][1]));
    }
    return returns;
  };"""
new_returns = """  const getDailyReturns = (arr, days) => {
    if (!arr || arr.length <= days) return [];
    const returns = [];
    const start = arr.length - days - 1;
    for (let i = start + 1; i < arr.length; i++) {
      // Missing data compression fix: refuse to calculate return across missing days
      if (arr[i][1] == null || arr[i - 1][1] == null) return null;
      returns.push(Math.log(arr[i][1] / arr[i - 1][1]));
    }
    return returns;
  };"""
content = content.replace(old_returns, new_returns)

# 3. Replace the Enforce Common As-Of Date block with the true Market Calendar logic
# Lines 60 to 118
calendar_logic = """
  // --- V3: Module-Specific Availability & Market Calendar ---
  // Determine if a session is valid. SPY or ^GSPC acts as the master US equity calendar.
  const masterCalSource = (store.yahoo && store.yahoo['^GSPC']) ? store.yahoo['^GSPC'] : [];
  const marketCalendar = masterCalSource.map(pt => pt[0]).sort(); // array of YYYY-MM-DD
  
  const alignToCalendar = (symbol, arr, purpose) => {
    if (!arr || marketCalendar.length === 0) return null;
    const aligned = [];
    const sourceMap = new Map();
    for (const pt of arr) {
       sourceMap.set(pt[0], pt[1]);
    }
    
    for (const date of marketCalendar) {
      if (date > marketDataAsOf) break;
      let val = sourceMap.has(date) ? sourceMap.get(date) : null;
      if (val != null && typeof val === 'object' && purpose) {
        val = getFieldForPurpose(symbol, val, purpose);
      }
      aligned.push([date, val]); // explicitly inserts [date, null] if missing
    }
    return aligned.length > 0 ? aligned : null;
  };

  const spx = alignToCalendar('^GSPC', (store.yahoo && store.yahoo['^GSPC']) ? store.yahoo['^GSPC'] : null, 'cta_close');
  const vix = alignToCalendar('^VIX', (store.yahoo && store.yahoo['^VIX']) ? store.yahoo['^VIX'] : null, 'cta_close');
  const ndx = alignToCalendar('^IXIC', (store.yahoo && store.yahoo['^IXIC']) ? store.yahoo['^IXIC'] : null, 'cta_close');
  const sox = alignToCalendar('SOXX', (store.yahoo && store.yahoo['SOXX']) ? store.yahoo['SOXX'] : null, 'cta_close');
  const dgs10 = alignToCalendar('DGS10', (store.fred && store.fred['DGS10']) ? store.fred['DGS10'] : null);
  const hyOasData = alignToCalendar('BAMLH0A0HYM2', store.fred && store.fred['BAMLH0A0HYM2'] ? store.fred['BAMLH0A0HYM2'] : null);
  
  const commonAsOfDate = marketDataAsOf; // Anchorage
  const isSeriesTooStale = isStale(commonAsOfDate);
"""
# regex replace between "// Enforce Common As-Of Date" and "// 1. Leveraged ETF"
content = re.sub(r'// Enforce Common As-Of Date.*?// 1\. Leveraged ETF', calendar_logic + '\n  // 1. Leveraged ETF', content, flags=re.DOTALL)


# 4. Vol Control state logic
old_vc_state = """
    // Determine actual exposure yesterday
    let prevActualExp = null;
    if (previousState && previousState.modules && previousState.modules.volControl) {
      prevActualExp = previousState.modules.volControl.actualExposureToday;
    }
"""
new_vc_state = """
    // State separation: Load recursive mathematical state from previousModelState
    let prevActualExp = null;
    if (previousModelState && previousModelState.volControl) {
      prevActualExp = previousModelState.volControl.actualExposure;
    }
"""
content = content.replace(old_vc_state, new_vc_state)

old_vc_save = """    volControl.actualExposureYesterday = prevActualExp;
    volControl.actualExposureToday = actualExpHistory[actualExpHistory.length - 1];"""
new_vc_save = """    volControl.actualExposureYesterday = prevActualExp;
    volControl.actualExposureToday = actualExpHistory[actualExpHistory.length - 1];
    
    // Save to pure nextModelState
    nextModelState.volControl = {
      actualExposure: volControl.actualExposureToday,
      paused: false,
      missingSessions: 0
    };"""
content = content.replace(old_vc_save, new_vc_save)

old_vc_pause = """    if (volControl.status === 'insufficient_data') {
      volControl.stateUpdate = 'paused_missing_data';
    }"""
new_vc_pause = """    if (volControl.status === 'insufficient_data') {
      volControl.stateUpdate = 'paused_missing_data';
      nextModelState.volControl = {
        actualExposure: prevActualExp,
        paused: true,
        missingSessions: ((previousModelState && previousModelState.volControl) ? previousModelState.volControl.missingSessions : 0) + 1
      };
    }"""
content = content.replace(old_vc_pause, new_vc_pause)

# 5. CTA Sma null fix
old_sma = """        let sum = 0;
        for (let i = assetData.length - days; i < assetData.length; i++) {
          sum += assetData[i][1];
        }"""
new_sma = """        let sum = 0;
        for (let i = assetData.length - days; i < assetData.length; i++) {
          if (assetData[i][1] == null) return null; // strictly fail on null
          sum += assetData[i][1];
        }"""
content = content.replace(old_sma, new_sma)

# 6. Risk Parity alignment
old_rp_bond = """  const getBondReturnsRP = (arr, days, duration) => {
    if (!arr || arr.length <= days) return [];
    const returns = [];
    const start = arr.length - days - 1;
    for (let i = start + 1; i < arr.length; i++) {
      returns.push(-duration * (arr[i][1] - arr[i - 1][1]) / 100);
    }
    return returns;
  };"""
new_rp_bond = """  const getBondReturnsRP = (arr, days, duration) => {
    if (!arr || arr.length <= days) return [];
    const returns = [];
    const start = arr.length - days - 1;
    for (let i = start + 1; i < arr.length; i++) {
      if (arr[i][1] == null || arr[i - 1][1] == null) return null;
      returns.push(-duration * (arr[i][1] - arr[i - 1][1]) / 100);
    }
    return returns;
  };"""
content = content.replace(old_rp_bond, new_rp_bond)

# 7. Pension Rebalance Date Logic
old_pension = """  const todayDate = new Date(commonAsOfDate);
  const daysInMonth = new Date(todayDate.getFullYear(), todayDate.getMonth() + 1, 0).getDate();
  const daysLeft = daysInMonth - todayDate.getDate();
  const isRebalanceWindow = daysLeft <= 4;"""
new_pension = """  // Pension Phase 3 Strict Market Windows
  // We need to know if commonAsOfDate is in the last 3 sessions of the month, last 5 of quarter, or first 2
  let isRebalanceWindow = false;
  let daysLeft = null;
  if (marketCalendar && marketCalendar.length > 5 && commonAsOfDate) {
    const idx = marketCalendar.indexOf(commonAsOfDate);
    if (idx !== -1) {
      const currentMonth = commonAsOfDate.substring(0, 7);
      // find last session of this month
      let lastIdx = idx;
      while (lastIdx + 1 < marketCalendar.length && marketCalendar[lastIdx+1].substring(0,7) === currentMonth) {
         lastIdx++;
      }
      daysLeft = lastIdx - idx;
      if (daysLeft < 3) isRebalanceWindow = true; // last 3 trading sessions
      
      // also allow first 2 trading sessions of the month
      let firstIdx = idx;
      while (firstIdx - 1 >= 0 && marketCalendar[firstIdx-1].substring(0,7) === currentMonth) {
         firstIdx--;
      }
      if (idx - firstIdx < 2) isRebalanceWindow = true;
    }
  }
"""
content = content.replace(old_pension, new_pension)


# 8. Add nextModelState to return
old_return = """    engineVersion: "flow-engine-v3.0.0",
    moduleVersions: {
      volControl: "vol-control-v2",
      ctaFuturesProxy: "cta-futures-v1",
      ctaEtfProxy: "cta-etf-v1",
      riskParity: "risk-parity-v2"
    },
    modelInputManifest: {
      ctaFuturesProxy: ["CL=F", "GC=F", "NG=F"],
      ctaEtfProxy: ["SPY", "QQQ", "IWM", "IEF", "USO", "GLD"]
    },
    snapshotGeneratedAt: new Date().toISOString(),
    summary,
    modules: {
      volControl,
      leveragedEtf,
      ctaFuturesProxy,
      ctaEtfProxy,
      riskParity: riskParityProxy,
      pensionRebalance,
      stressConditions
    }
  };
}"""
new_return = """    engineVersion: "flow-engine-v3.0.0",
    moduleVersions: {
      volControl: "vol-control-v3",
      ctaFuturesProxy: "cta-futures-v1",
      ctaEtfProxy: "cta-etf-v1",
      riskParity: "risk-parity-v3"
    },
    modelInputManifest: {
      ctaFuturesProxy: ["CL=F", "GC=F", "NG=F"],
      ctaEtfProxy: ["SPY", "QQQ", "IWM", "IEF", "USO", "GLD"]
    },
    snapshotGeneratedAt: new Date().toISOString(),
    summary,
    modules: {
      volControl,
      leveragedEtf,
      ctaFuturesProxy,
      ctaEtfProxy,
      riskParity: riskParityProxy,
      pensionRebalance,
      stressConditions
    }
  };
  
  // Return separated UI snapshot and mathematically pure state
  return { snapshot, nextModelState };
}"""
# Note we need to replace the `return { ...status: ok... }` with `const snapshot = { ...status: ok... }`
content = content.replace("  return { \n    status: 'ok',", "  const snapshot = { \n    status: 'ok',")
content = content.replace(old_return, new_return)


with open('lib/flow_engine_v3.js', 'w') as f:
    f.write(content)
