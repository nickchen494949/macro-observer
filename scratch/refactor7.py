import re

with open('lib/flow_engine.js', 'r') as f:
    content = f.read()

# Replace the targetSeries and RECURSION_LOOKBACK logic
old_vc = """  // 2. Vol-Control — full history recursion
  const realizedVol5d = spx ? calcStd(getDailyReturns(spx, 5)) * Math.sqrt(252) * 100 : null;
  const realizedVol20d = spx ? calcStd(getDailyReturns(spx, 20)) * Math.sqrt(252) * 100 : null;
  const realizedVol60d = spx ? calcStd(getDailyReturns(spx, 60)) * Math.sqrt(252) * 100 : null;
  const impliedVol = getLatest(vix);
  const targetVol = 10;
  const adjustmentSpeed = 0.25;
  const RECURSION_LOOKBACK = (modelConfig && modelConfig.recursionLookbackOverride !== undefined) ? modelConfig.recursionLookbackOverride : 60; // replay 60 days for state convergence

  // Step 1: Compute target exposure series for last RECURSION_LOOKBACK days
  const targetSeries = []; // index 0 = oldest, last = today
  let volForecastToday = null;
  let volForecastYesterday = null;
  if (spx && spx.length > RECURSION_LOOKBACK + 60) {
    for (let day = RECURSION_LOOKBACK; day >= 0; day--) {
      const endIdx = spx.length - 1 - day;
      const r20 = getVolEndingAt(spx, endIdx, 20);
      const r60 = getVolEndingAt(spx, endIdx, 60);
      let vf = r20;
      if (r60 != null && r20 != null) vf = 0.65 * r20 + 0.35 * r60;
      const target = vf ? Math.min(1.5, Math.max(0, targetVol / vf)) : null;
      targetSeries.push({ target, volForecast: vf });
    }
    volForecastToday = targetSeries[targetSeries.length - 1].volForecast;
    volForecastYesterday = targetSeries.length > 1 ? targetSeries[targetSeries.length - 2].volForecast : null;
  } else {
    // Fallback for insufficient data
    if (realizedVol20d != null) {
      volForecastToday = realizedVol60d != null ? 0.65 * realizedVol20d + 0.35 * realizedVol60d : realizedVol20d;
    }
  }

  let actualExpHistory = [];
  let volControlPaused = false;
  let missingSessionsCount = 0;
  let stateUpdateStr = undefined;
  let missingSessionsSinceLastUpdate = undefined;

  if (targetSeries.length > 0) {
    let actualExp = targetSeries[0].target; // seed with first target
    if (modelConfig && modelConfig.initialExposureOverride !== undefined) {
      actualExp = modelConfig.initialExposureOverride;
    }
    actualExpHistory.push(actualExp);
    for (let i = 1; i < targetSeries.length; i++) {
      const prevActual = actualExp;
      const target = targetSeries[i].target;
      let resumedToday = false;
      
      if (prevActual == null || target == null) {
        volControlPaused = true;
        missingSessionsCount++;
        actualExp = prevActual;
      } else {
        if (volControlPaused) {
          volControlPaused = false;
          resumedToday = true;
        }
        actualExp = prevActual + adjustmentSpeed * (target - prevActual);
      }
      
      if (i === targetSeries.length - 1) {
        if (volControlPaused) {
          stateUpdateStr = 'paused_missing_data';
        } else if (resumedToday) {
          stateUpdateStr = 'resumed_after_missing_data';
          missingSessionsSinceLastUpdate = missingSessionsCount;
          missingSessionsCount = 0; // reset
        }
      }
      actualExpHistory.push(actualExp);
    }
  }

  // Step 3: Extract today's and yesterday's actual exposure
  const actualExposureToday = actualExpHistory.length > 0 ? actualExpHistory[actualExpHistory.length - 1] : null;
  const actualExposureYesterday = actualExpHistory.length > 1 ? actualExpHistory[actualExpHistory.length - 2] : null;
  const dailyPositionChange = (actualExposureToday != null && actualExposureYesterday != null) ? actualExposureToday - actualExposureYesterday : null;
  
  // 5-day cumulative actual change (sum of last 5 daily changes)
  let fiveDayActualChange = null;
  if (actualExpHistory.length > 5) {
    fiveDayActualChange = actualExpHistory[actualExpHistory.length - 1] - actualExpHistory[actualExpHistory.length - 6];
  }

  // Target exposure snapshots for display
  const targetExposureToday = targetSeries.length > 0 ? targetSeries[targetSeries.length - 1].target : null;
  const targetExposureYesterday = targetSeries.length > 1 ? targetSeries[targetSeries.length - 2].target : null;
"""

new_vc = """  // 2. Vol-Control — True Stateful Recursive Implementation
  const realizedVol5d = spx ? calcStd(getDailyReturns(spx, 5)) * Math.sqrt(252) * 100 : null;
  const realizedVol20d = spx ? calcStd(getDailyReturns(spx, 20)) * Math.sqrt(252) * 100 : null;
  const realizedVol60d = spx ? calcStd(getDailyReturns(spx, 60)) * Math.sqrt(252) * 100 : null;
  const impliedVol = getLatest(vix);
  const targetVol = 10;
  const adjustmentSpeed = 0.25;

  let volForecastToday = null;
  if (realizedVol20d != null) {
    volForecastToday = realizedVol60d != null ? 0.65 * realizedVol20d + 0.35 * realizedVol60d : realizedVol20d;
  }
  const targetExposureToday = volForecastToday ? Math.min(1.5, Math.max(0, targetVol / volForecastToday)) : null;

  const prevVC = config.previousModelState?.volControl;
  let actualExposureYesterday = null;
  let actualExposureToday = null;
  let volControlPaused = false;
  let missingSessionsCount = 0;
  let stateUpdateStr = undefined;
  let missingSessionsSinceLastUpdate = undefined;
  
  if (prevVC) {
    actualExposureYesterday = prevVC.actualExposure;
    volControlPaused = prevVC.paused || false;
    missingSessionsCount = prevVC.missingSessions || 0;
  } else if (targetExposureToday != null) {
    // Genesis seed
    actualExposureYesterday = targetExposureToday;
    if (modelConfig && modelConfig.initialExposureOverride !== undefined) {
      actualExposureYesterday = modelConfig.initialExposureOverride;
    }
  }

  let resumedToday = false;
  if (actualExposureYesterday == null || targetExposureToday == null) {
    volControlPaused = true;
    missingSessionsCount++;
    actualExposureToday = actualExposureYesterday; // keep stale
    stateUpdateStr = 'paused_missing_data';
  } else {
    if (volControlPaused) {
      volControlPaused = false;
      resumedToday = true;
      stateUpdateStr = 'resumed_after_missing_data';
      missingSessionsSinceLastUpdate = missingSessionsCount;
      missingSessionsCount = 0;
    }
    actualExposureToday = actualExposureYesterday + adjustmentSpeed * (targetExposureToday - actualExposureYesterday);
  }

  const dailyPositionChange = (actualExposureToday != null && actualExposureYesterday != null) ? actualExposureToday - actualExposureYesterday : null;
  
  // 5-day cumulative actual change -> this requires a 5-day history buffer in nextModelState!
  let fiveDayHistory = prevVC?.fiveDayHistory || [];
  if (actualExposureToday != null) {
    fiveDayHistory.push(actualExposureToday);
    if (fiveDayHistory.length > 6) fiveDayHistory.shift(); // Keep at most 6 days (T, T-1 ... T-5)
  }
  let fiveDayActualChange = null;
  if (fiveDayHistory.length === 6) {
    fiveDayActualChange = fiveDayHistory[5] - fiveDayHistory[0];
  }

  const targetExposureYesterday = prevVC?.targetExposure;

  // Persist state
  nextModelState.volControl = {
    actualExposure: actualExposureToday,
    targetExposure: targetExposureToday,
    paused: volControlPaused,
    missingSessions: missingSessionsCount,
    fiveDayHistory: fiveDayHistory
  };
"""
content = content.replace(old_vc, new_vc)

# 2. Fix wall clock Date issue in isStale
old_stale = """  const isStale = (dateStr) => {
    if (!dateStr) return true;
    const date = new Date(dateStr);
    const now = new Date();
    const diffDays = (now - date) / (1000 * 60 * 60 * 24);
    return diffDays > 3;
  };"""
new_stale = """  const isStale = (dateStr) => {
    if (!dateStr) return true;
    const date = new Date(dateStr);
    // V3 constraint: Math core cannot rely on wall-clock time
    const anchor = new Date(decisionDate);
    const diffDays = (anchor - date) / (1000 * 60 * 60 * 24);
    return diffDays > 3;
  };"""
content = content.replace(old_stale, new_stale)

# Let's fix CTA ETF SMA null handling.
# "SMA窗口里有一个null → insufficient_data"
old_cta_sma = """  const getSma = (arr, days) => {
    if (!arr || arr.length < days) return null;
    let sum = 0;
    const start = arr.length - days;
    for (let i = start; i < arr.length; i++) {
      sum += arr[i][1];
    }
    return sum / days;
  };"""
new_cta_sma = """  const getSma = (arr, days) => {
    if (!arr || arr.length < days) return null;
    let sum = 0;
    const start = arr.length - days;
    for (let i = start; i < arr.length; i++) {
      if (arr[i][1] == null) return null; // Hard-fail on nulls
      sum += arr[i][1];
    }
    return sum / days;
  };"""
content = content.replace(old_cta_sma, new_cta_sma)

# Fix CTA ETF status aggregation
old_cta_status = """    ctaStatus = (spx && dgs10) ? 'ok' : 'insufficient_data';
  } else {
    ctaStatus = spx ? 'ok' : 'insufficient_data';
  }"""
new_cta_status = """    ctaStatus = (spx && dgs10) ? 'ok' : 'insufficient_data';
  } else {
    ctaStatus = spx ? 'ok' : 'insufficient_data';
  }
  // V3 Rule: The module must be 'insufficient_data' if any of the assets return 'missing_data'
  if (ctaAssets.some(a => a.status === 'missing_data')) {
    ctaStatus = 'insufficient_data';
  }
"""
content = content.replace(old_cta_status, new_cta_status)

# Predictive eligibility CTA ETF bug:
old_cta_etf_pred = """          if (ctaEtfProxy.status === 'ok') {
            if (ctaEtfProxy.aggregateDirection !== 'neutral') {
              if (ctaEtfProxy.aggregateDirection === 'buy') buyVotes++; else sellVotes++;
              mechanisms.push('ctaEtfProxy');
            }
          }"""
new_cta_etf_pred = """          if (ctaEtfProxy.status === 'ok' && ctaEtfProxy.predictiveSummaryEligible) {
            if (ctaEtfProxy.aggregateDirection !== 'neutral') {
              if (ctaEtfProxy.aggregateDirection === 'buy') buyVotes++; else sellVotes++;
              mechanisms.push('ctaEtfProxy');
            }
          }"""
content = content.replace(old_cta_etf_pred, new_cta_etf_pred)

# Risk parity broad_deleveraging bug
old_rp_broad = """    if (delevPress === 'high') {
      deRisking.push('Stress deleveraging — high');
      hasTotalDeRisking = true;
    } else if (delevPress === 'moderate') {
      deRisking.push('Stress deleveraging — moderate');
    }"""
new_rp_broad = """    if (delevPress === 'broad_deleveraging') {
      deRisking.push('Stress deleveraging — high');
      hasTotalDeRisking = true;
    } else if (delevPress === 'moderate_deleveraging') {
      deRisking.push('Stress deleveraging — moderate');
    }"""
content = content.replace(old_rp_broad, new_rp_broad)

# Pension 3/5/2 days logic
old_pen = """  const daysInMonth = new Date(todayDate.getFullYear(), todayDate.getMonth() + 1, 0).getDate();
  const daysLeft = daysInMonth - todayDate.getDate();
  const isRebalanceWindow = daysLeft <= 4;"""
new_pen = """  // True window: month end (last 3 trading sessions), quarter end (last 5 trading sessions), post month end (first 2 trading sessions).
  // Calculate relative to the usEquityCalendar.
  let isRebalanceWindow = false;
  let isQuarterEnd = false;
  let daysLeft = null;
  const dIdx = usEquityCalendar.indexOf(commonAsOfDate);
  if (dIdx !== -1) {
    const todayStr = commonAsOfDate;
    const [y, m, d] = todayStr.split('-');
    
    // Check if within last 5 days of quarter, last 3 of month, or first 2 of new month
    // Easiest heuristic: look forward 3-5 sessions and backwards 2 sessions to see if the month changed.
    if (dIdx + 5 < usEquityCalendar.length) {
      const future3 = usEquityCalendar[dIdx + 3].split('-')[1];
      const future5 = usEquityCalendar[dIdx + 5].split('-')[1];
      if (future3 !== m) {
          isRebalanceWindow = true; // Last 3 sessions of month
      }
      if (future5 !== m && ['03', '06', '09', '12'].includes(m)) {
          isRebalanceWindow = true; // Last 5 sessions of quarter end
          isQuarterEnd = true;
      }
    }
    if (dIdx >= 2) {
      const past2 = usEquityCalendar[dIdx - 2].split('-')[1];
      if (past2 !== m) {
          isRebalanceWindow = true; // First 2 sessions of new month
      }
    }
  }
"""
content = content.replace(old_pen, new_pen)

with open('lib/flow_engine.js', 'w') as f:
    f.write(content)
