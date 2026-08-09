// /Users/happygolucky/Desktop/宏观观察器/lib/flow_engine.js
const { getFieldForPurpose } = require('./data_validation');

function runFlowEngine(config) {
  const { decisionDate, signalAvailableAt, marketDataAsOf, inputsAsOfDecision, previousModelState, modelConfig } = config;
  const nextModelState = {};
  const store = inputsAsOfDecision;
  // Helpers
  const getLatest = (arr) => (arr && arr.length > 0) ? arr[arr.length - 1][1] : null;
  const getLatestDate = (arr) => (arr && arr.length > 0) ? arr[arr.length - 1][0] : null;
  const getValueAgo = (arr, days) => (arr && arr.length > days) ? arr[arr.length - 1 - days][1] : null;
  const getDateAgo = (arr, days) => (arr && arr.length > days) ? arr[arr.length - 1 - days][0] : null;

  const getDailyReturns = (arr, days) => {
    if (!arr || arr.length <= days) return [];
    const returns = [];
    const start = arr.length - days - 1;
    for (let i = start + 1; i < arr.length; i++) {
      // Missing data compression fix: refuse to calculate return across missing days
      if (arr[i][1] == null || arr[i - 1][1] == null) return null;
      returns.push(Math.log(arr[i][1] / arr[i - 1][1]));
    }
    return returns;
  };
  
  const getDailyChanges = (arr, days) => {
    if (!arr || arr.length <= days) return [];
    const changes = [];
    const start = arr.length - days - 1;
    for (let i = start + 1; i < arr.length; i++) {
      changes.push(arr[i][1] - arr[i - 1][1]);
    }
    return changes;
  };

  const calcStd = (arr) => {
    if (!arr || arr.length === 0) return null;
    const mean = arr.reduce((a, b) => a + b, 0) / arr.length;
    const variance = arr.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / (arr.length - 1 || 1);
    return Math.sqrt(variance);
  };

  const getVolEndingAt = (arr, endIndex, days) => {
    if (!arr || endIndex - days < 0) return null;
    const returns = [];
    for (let i = endIndex - days + 1; i <= endIndex; i++) {
      if (arr[i][1] == null || arr[i - 1][1] == null) return null;
      returns.push(Math.log(arr[i][1] / arr[i - 1][1]));
    }
    return calcStd(returns) * Math.sqrt(252) * 100;
  };

  const isStale = (dateStr) => {
    if (!dateStr) return true;
    const date = new Date(dateStr);
    // V3 constraint: Math core cannot rely on wall-clock time
    const anchor = new Date(decisionDate);
    const diffDays = (anchor - date) / (1000 * 60 * 60 * 24);
    return diffDays > 3;
  };


  
  // --- V3.1: Strict Module-Specific Calendars ---
  // US Equity Calendar (for VolControl, CTA ETF, Pension, RiskParity Equity)
  let usEquityCalendar = [];
  try {
    const fs = require('fs');
    const path = require('path');
    usEquityCalendar = JSON.parse(fs.readFileSync(path.join(__dirname, '../data/nyse_calendar.json'), 'utf-8'));
  } catch (err) {
    // Fallback if file missing (should not happen in prod after this batch)
    const equityCalSource = (store.yahoo && store.yahoo['^GSPC']) ? store.yahoo['^GSPC'] : [];
    usEquityCalendar = equityCalSource.map(pt => pt[0]).sort();
  }

  // Futures Calendar (for CTA Futures)
  const futuresCalSource = (store.yahoo && store.yahoo['CL=F']) ? store.yahoo['CL=F'] : [];
  let futuresCalendar = futuresCalSource.map(pt => pt[0]).sort();
  if (futuresCalendar.length === 0) futuresCalendar = usEquityCalendar; // fallback

  // FRED PIT Availability Policy Registry
  const FRED_AVAILABILITY_POLICY = {
    'DGS10': { method: 'fixed_business_day_lag', lagBusinessDays: 1, confidence: 'conservative_approximation' },
    'BAMLH0A0HYM2': { method: 'fixed_business_day_lag', lagBusinessDays: 1, confidence: 'conservative_approximation' }
  };

  const getPitCalendar = (seriesKey, fredSeries) => {
    if (!fredSeries) return [];
    // Currently, we just return observation dates because the lag logic was handled in sliceData upstream.
    // However, to enforce registry-based PIT, we define how it *would* be consumed.
    // The upstream sliceData in build_historical_snapshots.js should ideally use this registry.
    // For now, within flow_engine, we just sort dates.
    return fredSeries.map(pt => pt[0]).sort();
  };

  const alignToCalendar = (symbol, arr, purpose, calendar, carryForward = false) => {
    if (!arr || !calendar || calendar.length === 0) return null;
    const aligned = [];
    const sourceMap = new Map();
    for (const pt of arr) {
       sourceMap.set(pt[0], pt[1]);
    }
    
    let lastSeenVal = null;
    let lastSeenDate = null;
    for (const date of calendar) {
      if (date > marketDataAsOf) break;
      let val = sourceMap.has(date) ? sourceMap.get(date) : null;
      if (val != null) {
          lastSeenVal = val;
          lastSeenDate = date;
      } else if (carryForward && lastSeenVal != null) {
          val = lastSeenVal;
      }

      if (val != null && typeof val === 'object' && purpose) {
        val = getFieldForPurpose(symbol, val, purpose);
      }
      
      if (carryForward) {
          aligned.push([date, val, lastSeenDate]);
      } else {
          aligned.push([date, val]); // explicit missing-session insertion
      }
    }
    return aligned.length > 0 ? aligned : null;
  };

  // Pre-aligned assets
  const spx = alignToCalendar('^GSPC', (store.yahoo && store.yahoo['^GSPC']) ? store.yahoo['^GSPC'] : null, 'cta_close', usEquityCalendar);
  const vix = alignToCalendar('^VIX', (store.yahoo && store.yahoo['^VIX']) ? store.yahoo['^VIX'] : null, 'cta_close', usEquityCalendar);
  const ndx = alignToCalendar('^IXIC', (store.yahoo && store.yahoo['^IXIC']) ? store.yahoo['^IXIC'] : null, 'cta_close', usEquityCalendar);
  const sox = alignToCalendar('SOXX', (store.yahoo && store.yahoo['SOXX']) ? store.yahoo['SOXX'] : null, 'cta_close', usEquityCalendar);
  
  // Risk Parity FRED Leg uses PIT, joined strictly by date downstream in RiskParity.
  // Actually, Risk Parity logic computes bond returns daily. So we must align DGS10 to usEquityCalendar so arr1 (equity) and arr2 (bond) match exactly!
  const dgs10 = alignToCalendar('DGS10', (store.fred && store.fred['DGS10']) ? store.fred['DGS10'] : null, null, usEquityCalendar, true);
  const hyOasData = alignToCalendar('BAMLH0A0HYM2', store.fred && store.fred['BAMLH0A0HYM2'] ? store.fred['BAMLH0A0HYM2'] : null, null, usEquityCalendar, true);
  
  const commonAsOfDate = marketDataAsOf; // Anchorage
  const isSeriesTooStale = isStale(commonAsOfDate);

  // Timezones and signal times
  const getNYCloseTime = (dateStr) => {
    const dt = new Date(dateStr + 'T12:00:00Z'); 
    const nyString = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', timeZoneName: 'shortOffset' }).format(dt);
    const offset = nyString.split('GMT')[1]; // -5 or -4
    const offsetStr = offset.length === 2 ? offset.slice(0,1) + '0' + offset.slice(1) + ':00' : offset + ':00';
    return new Date(dateStr + 'T17:00:00' + offsetStr).toISOString();
  };
  const getFirstTradable = (availIso, cal) => {
    // first session whose open > signalAvailableAt
    // open is 09:30 NY time.
    for (const d of cal) {
      if (d > marketDataAsOf) {
        const dt = new Date(d + 'T12:00:00Z');
        const nyString = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', timeZoneName: 'shortOffset' }).format(dt);
        const offset = nyString.split('GMT')[1];
        const offsetStr = offset.length === 2 ? offset.slice(0,1) + '0' + offset.slice(1) + ':00' : offset + ':00';
        const openIso = new Date(d + 'T09:30:00' + offsetStr).toISOString();
        if (openIso > availIso) return d;
      }
    }
    return null; // out of bounds
  };

  // 1. Leveraged ETF
  const LETF_FUNDS = [
    { name: 'SPXL/UPRO', underlying: '^GSPC', leverage: 3, aum: 12e9, aumAsOf: '2026-08-01', source: 'estimate' },
    { name: 'SPXS/SDS', underlying: '^GSPC', leverage: -3, aum: 2e9, aumAsOf: '2026-08-01', source: 'estimate' },
    { name: 'SSO', underlying: '^GSPC', leverage: 2, aum: 8e9, aumAsOf: '2026-08-01', source: 'estimate' },
    { name: 'TQQQ', underlying: '^IXIC', leverage: 3, aum: 28e9, aumAsOf: '2026-08-01', source: 'estimate' },
    { name: 'SQQQ', underlying: '^IXIC', leverage: -3, aum: 5e9, aumAsOf: '2026-08-01', source: 'estimate' },
    { name: 'SOXL', underlying: 'SOXX', leverage: 3, aum: 10e9, aumAsOf: '2026-08-01', source: 'estimate' },
    { name: 'SOXS', underlying: 'SOXX', leverage: -3, aum: 2e9, aumAsOf: '2026-08-01', source: 'estimate' }
  ];

  const getReturn1d = (arr) => {
    if (!arr || arr.length < 2) return null;
    const curr = arr[arr.length - 1][1];
    const prev = arr[arr.length - 2][1];
    if (curr == null || prev == null || prev === 0) return null;
    const ret = (curr / prev) - 1;
    return Number.isFinite(ret) ? ret : null;
  };

  const spxRet = getReturn1d(spx);
  const ndxRet = getReturn1d(ndx);
  const soxRet = getReturn1d(sox);

  const returnsMap = { '^GSPC': spxRet, '^IXIC': ndxRet, 'SOXX': soxRet };

  let totalGrossRebalance = 0;
  const letfFundsResult = [];

  for (const fund of LETF_FUNDS) {
    const underlyingReturn = returnsMap[fund.underlying];
    if (underlyingReturn != null) {
      const grossRebalance = fund.aum * fund.leverage * (fund.leverage - 1) * underlyingReturn;
      totalGrossRebalance += grossRebalance;
      letfFundsResult.push({
        name: fund.name,
        leverage: fund.leverage,
        aum: fund.aum,
        aumAsOf: fund.aumAsOf,
        underlyingReturn,
        grossRebalanceUsd: grossRebalance,

        direction: grossRebalance > 0 ? 'buy' : (grossRebalance < 0 ? 'sell' : 'neutral'),
        confidence: 'medium',
        note: 'Gross mechanical estimate before ETF creations/redemptions'
      });
    }
  }

  let letfAggDir = 'neutral';
  if (totalGrossRebalance > 1e9) letfAggDir = 'buy';
  else if (totalGrossRebalance < -1e9) letfAggDir = 'sell';



  let letfStatus = isSeriesTooStale ? 'series_too_stale' : (spx ? 'ok' : 'insufficient_data');
  const leveragedEtf = {
    status: letfStatus,
    funds: letfStatus === 'ok' ? letfFundsResult : null,
    totalGrossRebalanceUsd: letfStatus === 'ok' ? totalGrossRebalance : null,
    estimateRange: letfStatus === 'ok' ? { low: totalGrossRebalance * 0.6, high: totalGrossRebalance * 1.2 } : null,
    executionTiming: 'Theoretical full-session gross rebalance | Closing residual: not estimable',
    aggregateDirection: letfStatus === 'ok' ? letfAggDir : 'neutral'
  };


  // 2. Vol-Control — True Stateful Recursive Implementation
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
  
  if (prevVC && prevVC.actualExposure != null) {
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
  let fiveDayHistory = prevVC?.fiveDayHistory ? [...prevVC.fiveDayHistory] : [];
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
  const targetExposure5dAgo = prevVC?.fiveDayHistory ? prevVC.fiveDayHistory[0] : null;

  const estimatedAum = 400e9;
  let estimatedFlowUsd = dailyPositionChange != null ? estimatedAum * dailyPositionChange : null;
  if (stateUpdateStr === 'resumed_after_missing_data') {
    estimatedFlowUsd = null;
  }

  // Remaining gap: how far actual is from target, in AUM terms. If actual is higher than target, gap is negative (need to reduce).
  const remainingGapPct = (actualExposureToday != null && targetExposureToday != null) ? targetExposureToday - actualExposureToday : null;
  const remainingGapUsd = remainingGapPct != null ? estimatedAum * remainingGapPct : null;

  let vcFlowPressure = 'neutral';
  if (estimatedFlowUsd != null && dailyPositionChange != null) {
    if (dailyPositionChange > 0.005) vcFlowPressure = 'buying';
    else if (dailyPositionChange < -0.005) vcFlowPressure = 'selling';
  }

  let regime_vc = 'normal';
  if (volForecastToday != null && volForecastToday < 10) regime_vc = 'low_vol_accumulating';
  else if (volForecastToday != null && volForecastToday >= 25) regime_vc = 'crisis_liquidating';
  else if (volForecastToday != null && volForecastToday >= 15) regime_vc = 'elevated_reducing';
  let vcStatus = isSeriesTooStale ? 'series_too_stale' : (spx ? 'ok' : 'insufficient_data');
  if (volControlPaused || targetExposureToday == null) vcStatus = 'insufficient_data';
  const volControl = {
    status: vcStatus,
    targetExposureToday: (vcStatus === 'ok' && targetExposureToday != null) ? Number(targetExposureToday.toFixed(4)) : null,
    actualExposureYesterday: (vcStatus === 'ok' && actualExposureYesterday != null) ? Number(actualExposureYesterday.toFixed(4)) : null,
    actualExposureToday: (vcStatus === 'ok' && actualExposureToday != null) ? Number(actualExposureToday.toFixed(4)) : null,
    dailyPositionChange: (vcStatus === 'ok' && dailyPositionChange != null) ? Number(dailyPositionChange.toFixed(4)) : null,
    fiveDayActualChange: (vcStatus === 'ok' && fiveDayActualChange != null) ? Number(fiveDayActualChange.toFixed(4)) : null,
    remainingExposureGap: (vcStatus === 'ok' && remainingGapPct != null) ? Number(remainingGapPct.toFixed(4)) : null,
    actualExpHistory: undefined,
    targetSeries: undefined,
    estimatedDailyFlowUsd: vcStatus === 'ok' ? estimatedFlowUsd : null,
    nextDayEstimateIfTargetUnchanged: (vcStatus === 'ok' && remainingGapUsd != null) ? remainingGapUsd * adjustmentSpeed : null,
    estimatedFlowRange: vcStatus === 'ok' && estimatedFlowUsd != null ? { low: estimatedFlowUsd * 0.5, high: estimatedFlowUsd * 1.5 } : null,
    dollarEstimateValidation: 'UNVALIDATED_DOLLAR_ESTIMATE',
    flowPressure: vcStatus === 'ok' ? vcFlowPressure : 'none',
    aggregateDirection: vcStatus === 'ok' ? ((dailyPositionChange || 0) > 0 ? 'buy' : 'sell') : 'neutral',
    stateUpdate: stateUpdateStr,
    missingSessionsSinceLastUpdate,
    amountConfidence: stateUpdateStr === 'resumed_after_missing_data' ? 'unavailable' : undefined,
    signalAvailableAt: vcStatus === 'ok' ? new Date(getNYCloseTime(commonAsOfDate)).toISOString() : null,
    firstTradableSession: vcStatus === 'ok' ? getFirstTradable(getNYCloseTime(commonAsOfDate), usEquityCalendar) : null
  };

  // 2b. VC Mechanical Pressure — S&P-style reference mechanics
  // Uses: max(vol20, vol40), 10% target, 100% cap, T-2 observation lag, instant snap
  // This is a standardised model-implied trading-pressure proxy,
  // NOT actual aggregate industry dollar flow.
  let vcMechPressure = { status: 'insufficient_data' };
  if (spx && spx.length > 42) {
    // T-2 observation lag: use vol ending 2 business days before latest
    const t2EndIndex = spx.length - 1 - 2; // T-2
    const mechVol20 = getVolEndingAt(spx, t2EndIndex, 20);
    const mechVol40 = getVolEndingAt(spx, t2EndIndex, 40);
    const mechSelectedVol = (mechVol20 != null && mechVol40 != null) ? Math.max(mechVol20, mechVol40) : (mechVol20 || mechVol40);
    const mechTargetVol = 10;
    const mechTargetExposure = mechSelectedVol ? Math.min(1.0, Math.max(0, mechTargetVol / mechSelectedVol)) : null;

    // Yesterday's mechanical target (T-3 observation)
    const t3EndIndex = spx.length - 1 - 3;
    const mechVol20Prev = getVolEndingAt(spx, t3EndIndex, 20);
    const mechVol40Prev = getVolEndingAt(spx, t3EndIndex, 40);
    const mechSelVolPrev = (mechVol20Prev != null && mechVol40Prev != null) ? Math.max(mechVol20Prev, mechVol40Prev) : (mechVol20Prev || mechVol40Prev);
    const mechTargetPrev = mechSelVolPrev ? Math.min(1.0, Math.max(0, mechTargetVol / mechSelVolPrev)) : null;

    const mechDelta = (mechTargetExposure != null && mechTargetPrev != null) ? mechTargetExposure - mechTargetPrev : null;
    let mechDirection = 'neutral';
    if (mechDelta != null) {
      if (mechDelta > 0.005) mechDirection = 'buying';
      else if (mechDelta < -0.005) mechDirection = 'selling';
    }

    // Extreme deleveraging: bottom 5% historically would be roughly delta < -0.05
    // Use a simple threshold since we don't have full history percentiles at runtime
    const extremeThreshold = -0.05;
    const isExtremeDelever = mechDelta != null && mechDelta < extremeThreshold;

    const mechObsDate = t2EndIndex >= 0 && spx[t2EndIndex] ? spx[t2EndIndex][0] : null;

    if (mechTargetExposure != null && !isSeriesTooStale) {
      vcMechPressure = {
        status: 'ok',
        targetExposure: Number(mechTargetExposure.toFixed(4)),
        deltaExposure: mechDelta != null ? Number(mechDelta.toFixed(4)) : null,
        pressureDirection: mechDirection,
        pressureMagnitudePct: mechDelta != null ? Number((Math.abs(mechDelta) * 100).toFixed(2)) : null,
        extremeDeleveraging: isExtremeDelever,
        selectedVol: mechSelectedVol != null ? Number(mechSelectedVol.toFixed(1)) : null,
        vol20: mechVol20 != null ? Number(mechVol20.toFixed(1)) : null,
        vol40: mechVol40 != null ? Number(mechVol40.toFixed(1)) : null,
        observationDate: mechObsDate,
        methodology: 'S&P Risk Control 10% reference mechanics',
        disclaimer: 'Model-implied pressure proxy. NOT actual industry dollar flow.'
      };
    }
  }

  // 3. CTA Trend
  const calcSma = (arr, days) => {
    if (!arr || arr.length < days) return null;
    let sum = 0;
    const start = arr.length - days;
    for (let i = start; i < arr.length; i++) {
      if (arr[i][1] == null || !Number.isFinite(arr[i][1])) return null;
      sum += arr[i][1];
    }
    return sum / days;
  };

  const getVolForAsset = (arr, days) => {
    if (!arr || arr.length <= days) return null;
    return calcStd(getDailyReturns(arr, days)) * Math.sqrt(252) * 100;
  };

  const ctaFuturesAssetsConfig = [
    { name: 'S&P 500', key: '^GSPC', type: 'price', src: store.yahoo },
    { name: 'Nasdaq', key: '^IXIC', type: 'price', src: store.yahoo },
    { name: 'Russell 2000', key: '^RUT', type: 'price', src: store.yahoo },
    { name: '10Y Yield Trend Signal (short-duration bias)', key: 'DGS10', type: 'yield', src: store.fred },
    { name: 'Oil', key: 'CL=F', type: 'price', src: store.yahoo },
    { name: 'Gold', key: 'GC=F', type: 'price', src: store.yahoo },
    { name: 'Natural Gas', key: 'NG=F', type: 'price', src: store.yahoo }
  ];

  const ctaEtfAssetsConfig = [
    { name: 'S&P 500 ETF', key: 'SPY', type: 'price', src: store.yahoo },
    { name: 'Nasdaq ETF', key: 'QQQ', type: 'price', src: store.yahoo },
    { name: 'Russell 2000 ETF', key: 'IWM', type: 'price', src: store.yahoo },
    { name: '7-10 Yr Treasury ETF', key: 'IEF', type: 'price', src: store.yahoo }, // Price type, not yield!
    { name: 'Oil ETF', key: 'USO', type: 'price', src: store.yahoo },
    { name: 'Gold ETF', key: 'GLD', type: 'price', src: store.yahoo }
  ];

  function runCtaModule(assetsConfig) {
    let aggScore = 0;
    let aggregatePositionChange = 0;
    let equityAggregatePositionChange = 0;
    const ctaAssets = [];
    
    const cal = assetsConfig === ctaFuturesAssetsConfig ? futuresCalendar : usEquityCalendar;
    for (const cfg of assetsConfig) {
      let rawArr = cfg.src ? cfg.src[cfg.key] : null;
      let arr = alignToCalendar(cfg.key, rawArr, 'cta_close', cal);
      if (!arr || arr.length < 201) {
        ctaAssets.push({ asset: cfg.name, status: 'missing_data' });
        continue;
      }
      const price = getLatest(arr);
      const sma50 = calcSma(arr, 50);
      const sma100 = calcSma(arr, 100);
      const sma200 = calcSma(arr, 200);
      if (price === null || sma50 === null || sma100 === null || sma200 === null) {
        ctaAssets.push({ asset: cfg.name, status: 'missing_data' });
        continue;
      }
      
      let score = 0;
      if (price > sma50) score += 1; else score -= 1;
      if (price > sma100) score += 1; else score -= 1;
      if (price > sma200) score += 1; else score -= 1;
      if (cfg.type === 'yield') score = -score;
      
      const assetVol = getVolForAsset(arr, 20);
      const volScaling = assetVol ? (targetVol / assetVol) : null;
      const positionStrength = volScaling ? (score / 3) * volScaling : null;
      
      // Yesterday
      const arrYest = arr.slice(0, arr.length - 1);
      const priceY = getLatest(arrYest);
      const sma50Y = calcSma(arrYest, 50);
      const sma100Y = calcSma(arrYest, 100);
      const sma200Y = calcSma(arrYest, 200);
      
      let scoreY = 0;
      if (priceY > sma50Y) scoreY += 1; else scoreY -= 1;
      if (priceY > sma100Y) scoreY += 1; else scoreY -= 1;
      if (priceY > sma200Y) scoreY += 1; else scoreY -= 1;
      if (cfg.type === 'yield') scoreY = -scoreY;
      
      const assetVolY = getVolForAsset(arrYest, 20);
      const volScalingY = assetVolY ? (targetVol / assetVolY) : null;
      const positionStrengthY = volScalingY ? (scoreY / 3) * volScalingY : null;
      
      const signalToday = score / 3;
      const signalYesterday = scoreY / 3;
      const volScaleToday = volScaling || 0;
      const volScaleYesterday = volScalingY || 0;
  
      const signalEffect = (volScalingY != null) ? (signalToday - signalYesterday) * volScalingY : 0;
      const volScalingEffect = (volScaling != null && volScalingY != null) ? signalToday * (volScaling - volScalingY) : 0;
      const positionChange = signalEffect + volScalingEffect;
      if (positionChange != null) aggregatePositionChange += positionChange;
      if (positionChange != null && ['SPY', 'QQQ', 'IWM'].includes(cfg.key)) {
        equityAggregatePositionChange += positionChange;
      }
      
      const distanceToSma50Pct = ((price - sma50) / price) * 100;
  
      aggScore += score;
      ctaAssets.push({
        asset: cfg.name,
        label: cfg.name,
        observationDate: commonAsOfDate,
        session: 'regular_close',
        isFinal: true,
        signalToday: Number(signalToday.toFixed(4)),
        signalYesterday: Number(signalYesterday.toFixed(4)),
        volScaleToday: Number(volScaleToday.toFixed(4)),
        volScaleYesterday: Number(volScaleYesterday.toFixed(4)),
        signalEffect: Number(signalEffect.toFixed(4)),
        volScalingEffect: Number(volScalingEffect.toFixed(4)),
        positionChange: Number(positionChange.toFixed(4)),
        distanceToSma50Pct: Number(distanceToSma50Pct.toFixed(2))
      });
    }
  
    let ctaRegime = 'neutral';
    if (aggScore >= 10) ctaRegime = 'strong_buy';
    else if (aggScore >= 4) ctaRegime = 'buy';
    else if (aggScore >= -3) ctaRegime = 'neutral';
    else if (aggScore >= -9) ctaRegime = 'sell';
    else ctaRegime = 'strong_sell';
  
    let ctaFlowPressure = 'neutral';
    if (aggregatePositionChange > 0.1) ctaFlowPressure = 'buying';
    else if (aggregatePositionChange < -0.1) ctaFlowPressure = 'selling';
  
    let ctaStatus = isSeriesTooStale ? 'series_too_stale' : (spx ? 'ok' : 'insufficient_data');
    if (ctaAssets.some(a => a.status === 'missing_data')) {
      ctaStatus = 'insufficient_data';
    }
    return {
      status: ctaStatus,
      positionRegime: ctaStatus === 'ok' ? ctaRegime : null,
      flowPressure: ctaStatus === 'ok' ? ctaFlowPressure : null,
      aggregatePositionChange: ctaStatus === 'ok' ? aggregatePositionChange : null,
      equityAggregatePositionChange: ctaStatus === 'ok' ? equityAggregatePositionChange : null,
      assets: ctaStatus === 'ok' ? ctaAssets : null,
      commonAsOfDate: ctaStatus === 'ok' ? commonAsOfDate : null,
      signalAvailableAt: getNYCloseTime(commonAsOfDate), // Futures settle approx 17:00 EST
      firstTradableSession: getFirstTradable(getNYCloseTime(commonAsOfDate), assetsConfig === ctaFuturesAssetsConfig ? futuresCalendar : usEquityCalendar)
    };
  }

  const ctaFuturesProxy = runCtaModule(ctaFuturesAssetsConfig);
  ctaFuturesProxy.predictiveSummaryEligible = false;
  ctaFuturesProxy.displayRole = 'descriptive_only';
  
  const ctaEtfProxy = runCtaModule(ctaEtfAssetsConfig);
  ctaEtfProxy.predictiveSummaryEligible = false;



  // 4. Risk Parity Proxy
  const getBondReturnsRP = (arr, days, duration) => {
    if (!arr || arr.length <= days) return [];
    const returns = [];
    const start = arr.length - days - 1;
    for (let i = start + 1; i < arr.length; i++) {
      if (arr[i][1] == null || arr[i - 1][1] == null) return null;
      returns.push(-duration * (arr[i][1] - arr[i - 1][1]) / 100);
    }
    return returns;
  };
  
  const eqRet20 = getDailyReturns(spx, 20);
  const bondRet20 = getBondReturnsRP(dgs10, 20, 8);
  const eqStd20 = calcStd(eqRet20);
  const bondStd20 = calcStd(bondRet20);
  const eqVol20d = eqStd20 != null ? eqStd20 * Math.sqrt(252) : null;
  const bondVol20d = bondStd20 != null ? bondStd20 * Math.sqrt(252) : null;

  const eqRet20_5d = getDailyReturns(spx ? spx.slice(0, spx.length - 5) : null, 20);
  const bondRet20_5d = getBondReturnsRP(dgs10 ? dgs10.slice(0, dgs10.length - 5) : null, 20, 8);
  const eqStd20_5d = calcStd(eqRet20_5d);
  const bondStd20_5d = calcStd(bondRet20_5d);
  const eqVol20d_5d = eqStd20_5d != null ? eqStd20_5d * Math.sqrt(252) : null;
  const bondVol20d_5d = bondStd20_5d != null ? bondStd20_5d * Math.sqrt(252) : null;

  const calcCorr = (arr1, arr2) => {
    if (!arr1 || !arr2 || arr1.length !== arr2.length || arr1.length === 0) return null;
    const mean1 = arr1.reduce((a,b)=>a+b,0)/arr1.length;
    const mean2 = arr2.reduce((a,b)=>a+b,0)/arr2.length;
    let num = 0, den1 = 0, den2 = 0;
    for(let i=0; i<arr1.length; i++){
      num += (arr1[i] - mean1) * (arr2[i] - mean2);
      den1 += Math.pow(arr1[i] - mean1, 2);
      den2 += Math.pow(arr2[i] - mean2, 2);
    }
    return num / Math.sqrt(den1 * den2 || 1);
  };
  
  const getAlignedReturns = (arr1, arr2, days, transform1, transform2) => {
    if(!arr1 || !arr2) return {ret1:[], ret2:[]};
    let i = arr1.length - 1, j = arr2.length - 1;
    const common = [];
    while(i > 0 && j > 0 && common.length <= days) {
      const d1 = arr1[i][0], d2 = arr2[j][0];
      if (d1 === d2) {
        common.unshift({ v1: arr1[i][1], prev1: arr1[i-1][1], v2: arr2[j][1], prev2: arr2[j-1][1] });
        i--; j--;
      } else if (d1 > d2) i--;
      else j--;
    }
    const ret1 = [], ret2 = [];
    for(let k = 0; k < common.length; k++) {
      ret1.push(transform1(common[k].v1, common[k].prev1));
      ret2.push(transform2(common[k].v2, common[k].prev2));
    }
    return { ret1: ret1.slice(-days), ret2: ret2.slice(-days) };
  };

  const aligned60 = getAlignedReturns(spx, dgs10, 60, (curr, prev) => Math.log(curr/prev), (curr, prev) => -8 * (curr - prev) / 100);
  const stockBondCorr60d = calcCorr(aligned60.ret1, aligned60.ret2);

  let estEqAlloc = null, estBondAlloc = null;
  if (eqVol20d != null && bondVol20d != null && eqVol20d > 0 && bondVol20d > 0) {
    estEqAlloc = (1/eqVol20d) / (1/eqVol20d + 1/bondVol20d);
    estBondAlloc = 1 - estEqAlloc;
  }
  
  let estEqAlloc_5d = null;
  if (eqVol20d_5d != null && bondVol20d_5d != null && eqVol20d_5d > 0 && bondVol20d_5d > 0) {
    estEqAlloc_5d = (1/eqVol20d_5d) / (1/eqVol20d_5d + 1/bondVol20d_5d);
  }
  
  const allocChange = (estEqAlloc != null && estEqAlloc_5d != null) ? estEqAlloc - estEqAlloc_5d : null;

  let dp = 'none';
  if (eqVol20d != null && bondVol20d != null && eqVol20d > 0.20 && bondVol20d > 0.15 && stockBondCorr60d > 0.3) dp = 'high';
  else if ((eqVol20d != null && eqVol20d > 0.20) || (bondVol20d != null && bondVol20d > 0.15)) dp = 'moderate';

  // Determine vol status for transparency
  const eqVolStatus = eqVol20d == null ? 'insufficient_history' : (eqVol20d === 0 ? 'valid_zero' : 'normal');
  const bondVolStatus = bondVol20d == null ? 'insufficient_history' : (bondVol20d === 0 ? 'valid_zero' : 'normal');
  const allocationDegenerate = (eqVol20d === 0 || bondVol20d === 0);

  let rpStatus = isSeriesTooStale ? 'series_too_stale' : (spx && dgs10 ? 'ok' : 'insufficient_data');
  const riskParityProxy = {
    status: rpStatus,
    equityAllocationChange5d: rpStatus === 'ok' ? (allocChange != null ? allocChange : null) : null,
    bondAllocationChange5d: rpStatus === 'ok' ? (allocChange != null ? -allocChange : null) : null,
    modelLeverageChange5d: rpStatus === 'ok' ? 0 : null,
    allocationDirection: rpStatus === 'ok' ? (allocChange != null ? (allocChange < -0.005 ? 'equity_to_bonds' : (allocChange > 0.005 ? 'bonds_to_equity' : 'stable')) : null) : null,
    deleveragingPressure: rpStatus === 'ok' ? (dp === 'high' ? 'broad_deleveraging' : (dp === 'moderate' ? 'moderate_deleveraging' : 'none')) : null,
    totalDeRisking: rpStatus === 'ok' ? (dp === 'high') : null,
    commonAsOfDate: rpStatus === 'ok' ? commonAsOfDate : null,
    signalAvailableAt: rpStatus === 'ok' ? new Date(getNYCloseTime(commonAsOfDate)).toISOString() : null,
    firstTradableSession: rpStatus === 'ok' ? getFirstTradable(getNYCloseTime(commonAsOfDate), usEquityCalendar) : null,
    dgs10ObservationDate: (dgs10 && dgs10.length > 0) ? (dgs10[dgs10.length - 1][2] || dgs10[dgs10.length - 1][0]) : null,
    dgs10Value: (dgs10 && dgs10.length > 0) ? dgs10[dgs10.length - 1][1] : null,
    pitAvailabilityQuality: 'conservative_approximation'
  };

  // 5. Pension Rebalance
  let equityReturnMtd = null, bondReturnMtd = null, currentEquityWeight = null, overweightPct = null;
  let isRebalanceWindow = false, daysLeft = 0;
  if (spx && spx.length > 0) {
    const todayStr = spx[spx.length - 1][0];
    const monthPrefix = todayStr.substring(0, 7);
    let mtdStartIdx = spx.length - 1;
    while(mtdStartIdx > 0 && spx[mtdStartIdx][0].substring(0, 7) === monthPrefix) mtdStartIdx--;
    const mtdStartValSpx = spx[mtdStartIdx][1];
    equityReturnMtd = getLatest(spx) / mtdStartValSpx - 1;
    
    if (dgs10) {
      let mtdStartIdxDgs = dgs10.length - 1;
      while(mtdStartIdxDgs > 0 && dgs10[mtdStartIdxDgs][0].substring(0, 7) === monthPrefix) mtdStartIdxDgs--;
      if (mtdStartIdxDgs >= 0) {
        const mtdStartValDgs = dgs10[mtdStartIdxDgs][1];
        bondReturnMtd = -8 * (getLatest(dgs10) - mtdStartValDgs) / 100;
        currentEquityWeight = (0.60 * (1 + equityReturnMtd)) / (0.60 * (1 + equityReturnMtd) + 0.40 * (1 + bondReturnMtd));
        overweightPct = currentEquityWeight - 0.60;
      }
    }
    // Find position in month using actual trading calendar
    if (usEquityCalendar && usEquityCalendar.length > 0) {
      const idx = usEquityCalendar.indexOf(todayStr);
      if (idx !== -1) {
        // Look forward for month boundary
        let daysToNextMonth = 0;
        for (let j = idx + 1; j < usEquityCalendar.length; j++) {
           if (usEquityCalendar[j].substring(0, 7) !== monthPrefix) {
               daysToNextMonth = j - idx;
               break;
           }
        }
        daysLeft = daysToNextMonth - 1; // 0 means today is last trading day

        // Look backward for start of month
        let daysFromStartOfMonth = 0;
        for (let j = idx - 1; j >= 0; j--) {
           if (usEquityCalendar[j].substring(0, 7) !== monthPrefix) {
               daysFromStartOfMonth = idx - j;
               break;
           }
        }
        
        const isQuarterEnd = ['03', '06', '09', '12'].includes(monthPrefix.substring(5, 7));
        
        if (daysToNextMonth > 0 && daysToNextMonth <= (isQuarterEnd ? 5 : 3)) {
            isRebalanceWindow = true; // Pre-month/quarter end
        } else if (daysFromStartOfMonth <= 2) {
            isRebalanceWindow = true; // Post-month end (first 2 sessions)
        }
      }
    }
  }
  let expectedFlow = 'balanced';
  if (overweightPct > 0.001) expectedFlow = 'sell_equities_buy_bonds';
  else if (overweightPct < -0.001) expectedFlow = 'buy_equities_sell_bonds';

  let penStatus = spx && dgs10 ? 'ok' : 'insufficient_data';
  if (penStatus === 'ok' && !isRebalanceWindow) penStatus = 'not_in_window';

  const pensionRebalance = {
    status: penStatus,
    currentEquityWeight: (spx && dgs10) ? Number(currentEquityWeight.toFixed(4)) : null,
    targetEquityWeight: (spx && dgs10) ? 0.60 : null,
    equityOverweightPct: (spx && dgs10) ? Number((overweightPct * 100).toFixed(4)) : null,
    daysToMonthEnd: (spx && dgs10) ? daysLeft : null,
    isRebalanceWindow: (spx && dgs10) ? isRebalanceWindow : null,
    expectedFlow: (spx && dgs10) ? expectedFlow : 'none',
    signalAvailableAt: (spx && dgs10) ? new Date(getNYCloseTime(commonAsOfDate)).toISOString() : null,
    firstTradableSession: (spx && dgs10) ? getFirstTradable(getNYCloseTime(commonAsOfDate), usEquityCalendar) : null
  };

  // 6. Stress Conditions
  const latestHy = hyOasData ? getLatest(hyOasData) : null;
  const hyOasBp = latestHy != null ? latestHy * 100 : null;
  const hyOas5dAgo = hyOasData ? getValueAgo(hyOasData, 5) : null;
  const hyOasChange5d = (latestHy != null && hyOas5dAgo != null) ? (latestHy - hyOas5dAgo) * 100 : null;

  const vixLatest = getLatest(vix);
  const vix5dAgo = vix ? getValueAgo(vix, 5) : null;
  const vixChange5d = vix5dAgo ? vixLatest - vix5dAgo : null;

  const getRetArr = (arr, days) => {
    if (!arr || arr.length <= days) return Array(days).fill(0);
    const r = [];
    for (let i = arr.length - days; i < arr.length; i++) r.push((arr[i][1] / arr[i - 1][1]) - 1);
    return r;
  };
  const spxRet20_flat = getRetArr(spx, 20);
  const goldRet20 = getRetArr(store.yahoo && store.yahoo['GC=F'], 20);
  const oilRet20 = getRetArr(store.yahoo && store.yahoo['CL=F'], 20);
  let bRet20_flat = [];
  if (dgs10 && dgs10.length > 20) {
    for (let i = dgs10.length - 20; i < dgs10.length; i++) bRet20_flat.push(-8 * (dgs10[i][1] - dgs10[i-1][1]) / 100);
  } else bRet20_flat = Array(20).fill(0);

  const c1 = calcCorr(spxRet20_flat, bRet20_flat) || 0;
  const c2 = calcCorr(spxRet20_flat, goldRet20) || 0;
  const c3 = calcCorr(spxRet20_flat, oilRet20) || 0;
  const c4 = calcCorr(bRet20_flat, goldRet20) || 0;
  const c5 = calcCorr(bRet20_flat, oilRet20) || 0;
  const c6 = calcCorr(goldRet20, oilRet20) || 0;
  const crossAssetCorr = (c1 + c2 + c3 + c4 + c5 + c6) / 6;

  let stressScore = null, missingInputs = [], stressStatus = 'insufficient_data';
  
  if (vixLatest == null || Number.isNaN(vixLatest)) missingInputs.push('VIX');
  if (hyOasBp == null || Number.isNaN(hyOasBp)) missingInputs.push('HY_OAS');
  
  if (missingInputs.length === 0) {
    stressScore = 0;
    if (vixLatest > 40) { stressScore += 40; }
    else if (vixLatest > 30) { stressScore += 30; }
    else if (vixLatest > 25) { stressScore += 20; }
    else if (vixLatest > 20) { stressScore += 10; }

    if (vixChange5d > 10) { stressScore += 30; }
    else if (vixChange5d > 5) { stressScore += 20; }
    else if (vixChange5d > 3) { stressScore += 10; }

    if (hyOasBp > 600) { stressScore += 30; }
    else if (hyOasBp > 500) { stressScore += 20; }
    else if (hyOasBp > 400) { stressScore += 10; }

    if (crossAssetCorr > 0.3) { stressScore += 10; }

    stressStatus = 'calm';
    if (stressScore >= 70) stressStatus = 'crisis';
    else if (stressScore >= 50) stressStatus = 'stress';
    else if (stressScore >= 30) stressStatus = 'elevated';
    else if (stressScore >= 15) stressStatus = 'watch';
  }
  
  if (isSeriesTooStale) {
    stressStatus = 'series_too_stale';
  }

  const stressConditions = {
    status: stressStatus,
    stressScore: missingInputs.length === 0 && !isSeriesTooStale ? stressScore : null,
    vix: missingInputs.length === 0 && !isSeriesTooStale ? Number(vixLatest.toFixed(4)) : null,
    hyOas: missingInputs.length === 0 && !isSeriesTooStale ? Number(hyOasBp.toFixed(4)) : null,
    estimatedFlowUsd: null
  };
  
  if (stressStatus === 'insufficient_data') {
    stressConditions.missingInputs = missingInputs.length > 0 ? missingInputs : ['VIX', 'HY_OAS'];
  }

  // 7. Summary — prevent double-counting common-driver signals
  // Group by data domain to identify truly independent evidence
  const mechanisms = [];
  const dataDomains = new Set();
  
  let activeFlowMechanismCount = 0;
  let activeRotationMechanismCount = 0;
  
  // Vol-control, LETF, CTA all depend on equity_price — same common driver
  let equityPriceDrivenCount = 0;
  let equityPriceDrivenDir = 0;
  
  if (volControl.flowPressure === 'buying') { equityPriceDrivenDir += 1; equityPriceDrivenCount++; mechanisms.push('vol_control_buy'); activeFlowMechanismCount++; }
  else if (volControl.flowPressure === 'selling') { equityPriceDrivenDir -= 1; equityPriceDrivenCount++; mechanisms.push('vol_control_sell'); activeFlowMechanismCount++; }

  // Use the eligible ETF proxy for forward-looking predictions
  if (ctaEtfProxy.predictiveSummaryEligible) {
    if (ctaEtfProxy.flowPressure === 'buying') { equityPriceDrivenDir += 1; equityPriceDrivenCount++; mechanisms.push('cta_buy'); activeFlowMechanismCount++; }
    else if (ctaEtfProxy.flowPressure === 'selling') { equityPriceDrivenDir -= 1; equityPriceDrivenCount++; mechanisms.push('cta_sell'); activeFlowMechanismCount++; }
  }
  
  if (equityPriceDrivenCount > 0) dataDomains.add('equity_price');

  // Risk parity uses both equity AND bond data — partially independent
  let crossAssetDir = 0;
  if (riskParityProxy.deleveragingPressure === 'broad_deleveraging' || riskParityProxy.deleveragingPressure === 'moderate_deleveraging') {
    crossAssetDir -= 1; mechanisms.push('risk_parity_deleverage');
    activeRotationMechanismCount++;
    dataDomains.add('bond_market');
  } else if (riskParityProxy.allocationDirection !== 'stable' && riskParityProxy.allocationDirection !== 'none') {
    activeRotationMechanismCount++;
  }

  // Pension rebalance — counter-cyclical, independent mechanism
  let counterCyclicalDir = 0;
  if (pensionRebalance.isRebalanceWindow) {
    if (pensionRebalance.expectedFlow === 'sell_equities_buy_bonds') { counterCyclicalDir -= 1; mechanisms.push('pension_sell'); activeRotationMechanismCount++; }
    else if (pensionRebalance.expectedFlow === 'buy_equities_sell_bonds') { counterCyclicalDir += 1; mechanisms.push('pension_buy'); activeRotationMechanismCount++; }
    dataDomains.add('rebalance_calendar');
  }

  // Stress conditions — market state, not flow
  if (stressConditions.stressScore >= 30) dataDomains.add('credit');

  // Common driver analysis: vol-control, LETF, CTA are all driven by equity price change
  const duplicatedDriverCount = equityPriceDrivenCount > 1 ? equityPriceDrivenCount - 1 : 0;
  const mechanismCount = mechanisms.length;
  // Independent = data domains that provide distinct information
  const independentDataDomains = [...dataDomains];

  const netDir = equityPriceDrivenDir + crossAssetDir + counterCyclicalDir;
  let dominantRegime = 'no_dominant_flow';
  if (netDir >= 2) dominantRegime = 'procyclical_buy';
  else if (netDir <= -2) dominantRegime = 'procyclical_sell';
  else if (mechanisms.length > 0 && netDir !== 0) dominantRegime = 'conflicting';
  else if (mechanisms.length > 0) dominantRegime = 'conflicting';

  // 8. Timeline Pressures (v2 Schema replacement for flowTimeline)
  const timelinePressures = {
    ongoing1To5Days: { status: 'ok', direction: 'none', mechanisms: [], confidence: 'low' },
    recent5To20Days: { status: 'ok', direction: 'none', mechanisms: [], confidence: 'low' },
    conditionalFuture: { status: 'ok', direction: 'none', mechanisms: [], confidence: 'low' }
  };


  // ongoing1To5Days (Vol-Control + CTA)
  let ongoingBuys = 0, ongoingSells = 0;
  if (volControl.status === 'ok') {
    if (volControl.flowPressure !== 'neutral') {
      timelinePressures.ongoing1To5Days.mechanisms.push('volControl');
      if (volControl.flowPressure === 'selling') ongoingSells++;
      else if (volControl.flowPressure === 'buying') ongoingBuys++;
    }
  } else {
    timelinePressures.ongoing1To5Days.status = 'partial';
  }
  
  if (ctaEtfProxy.status === 'ok') {
    if (ctaEtfProxy.predictiveSummaryEligible && ctaEtfProxy.flowPressure !== 'neutral') {
      timelinePressures.ongoing1To5Days.mechanisms.push('ctaEtfProxy');
      if (ctaEtfProxy.flowPressure === 'selling') ongoingSells++;
      else if (ctaEtfProxy.flowPressure === 'buying') ongoingBuys++;
    }
  } else {
    timelinePressures.ongoing1To5Days.status = 'partial';
  }

  if (timelinePressures.ongoing1To5Days.status === 'ok' || timelinePressures.ongoing1To5Days.mechanisms.length > 0) {
    if (ongoingBuys > 0 && ongoingSells > 0) timelinePressures.ongoing1To5Days.direction = 'conflicting';
    else if (ongoingBuys > 0) timelinePressures.ongoing1To5Days.direction = 'buying';
    else if (ongoingSells > 0) timelinePressures.ongoing1To5Days.direction = 'selling';
    timelinePressures.ongoing1To5Days.confidence = 'medium_low';
  } else if (timelinePressures.ongoing1To5Days.status !== 'ok') {
    timelinePressures.ongoing1To5Days.direction = 'unavailable';
  }

  // recent5To20Days (Risk Parity)
  if (riskParityProxy.status === 'ok') {
    if (riskParityProxy.allocationDirection && riskParityProxy.allocationDirection !== 'stable') {
      timelinePressures.recent5To20Days.mechanisms.push('riskParity');
      timelinePressures.recent5To20Days.direction = riskParityProxy.allocationDirection;
      timelinePressures.recent5To20Days.confidence = 'medium';
    }
  } else {
    timelinePressures.recent5To20Days.status = 'partial';
    timelinePressures.recent5To20Days.direction = 'unavailable';
  }

  // conditionalFuture (Pension + Stress)
  if (pensionRebalance.status === 'ok' || pensionRebalance.status === 'not_in_window') {
    if (pensionRebalance.expectedFlow !== 'balanced' && pensionRebalance.expectedFlow !== 'none') {
      timelinePressures.conditionalFuture.mechanisms.push('pensionRebalance');
    }
  } else {
    timelinePressures.conditionalFuture.status = 'partial';
  }

  if (stressConditions.status === 'insufficient_data' || stressConditions.status === 'series_too_stale' || stressConditions.status === 'calculation_error') {
    timelinePressures.conditionalFuture.status = 'partial';
  } else {
    timelinePressures.conditionalFuture.mechanisms.push('stressConditions');
    if (stressConditions.stressScore >= 50) {
      timelinePressures.conditionalFuture.direction = 'selling';
    }
  }
  
  if (timelinePressures.conditionalFuture.status !== 'ok' && timelinePressures.conditionalFuture.mechanisms.length === 0) {
    timelinePressures.conditionalFuture.direction = 'unavailable';
  }
  
  // Dummy flowTimeline for backwards compatibility
  const flowTimeline = {};


  const excludedModules = [];
  if (volControl.status !== 'ok') excludedModules.push('volControl');
  if (leveragedEtf.status !== 'ok') excludedModules.push('leveragedEtf');
  if (ctaFuturesProxy.status !== 'ok') excludedModules.push('ctaFuturesProxy');
  if (ctaEtfProxy.status !== 'ok') excludedModules.push('ctaEtfProxy');
  if (riskParityProxy.status !== 'ok') excludedModules.push('riskParityProxy');
  if (stressConditions.status === 'insufficient_data' || stressConditions.status === 'series_too_stale') excludedModules.push('stressConditions');

  let snapshotQuality = excludedModules.length > 0 ? 'partial' : 'complete';

  const rpSummary = riskParityProxy.status === 'ok' ? (
    riskParityProxy.deleveragingPressure !== 'none' ? riskParityProxy.deleveragingPressure : 
    (riskParityProxy.allocationDirection !== 'stable' ? 'rotation_' + riskParityProxy.allocationDirection : 'none')
  ) : 'unavailable';

  const summary = {
    trendAmplifiers: { 
      'Vol-control —': volControl.status === 'ok' ? volControl.flowPressure : 'unavailable', 
      'CTA trend (Futures) —': ctaFuturesProxy.status === 'ok' ? ctaFuturesProxy.flowPressure : 'unavailable',
      'CTA trend (ETF) —': ctaEtfProxy.status === 'ok' ? ctaEtfProxy.flowPressure : 'unavailable'
    },
    dominantRegime,
    activeFlowMechanismCount,
    activeRotationMechanismCount,
    primaryCommonDrivers: equityPriceDrivenCount > 0 ? ['equity_price'] : [],
    supportingDataDomains: ['rates', 'commodities', 'volatility', 'credit'],
    confidence: {
      mechanism: (activeFlowMechanismCount + activeRotationMechanismCount) >= 2 ? 'medium' : 'low',
      netDirection: dominantRegime === 'conflicting' || dominantRegime === 'no_dominant_flow' ? 'low' : ((activeFlowMechanismCount + activeRotationMechanismCount) >= 3 ? 'high' : 'medium'),
      amount: 'low'
    },
    excludedModules,
    timelinePressures,
    flowTimeline,
    crossAssetDeRisking: {
      'Risk parity —': rpSummary.replace('equity_to_bonds', 'equity to bonds rotation').replace('bonds_to_equity', 'bonds to equity rotation'),
      'Stress deleveraging —': stressConditions.status === 'triggered' ? 'triggered' : 'not triggered'
    },
    counterCyclicalFlows: {
      pension: pensionRebalance.status === 'not_in_window' 
               ? `outside window | bias: ${pensionRebalance.expectedFlow.replace('sell_equities_buy_bonds', 'sell equities / buy bonds').replace('buy_equities_sell_bonds', 'buy equities / sell bonds')} | current pressure: none`
               : (pensionRebalance.status === 'ok' ? pensionRebalance.expectedFlow : 'unavailable')
    },
    narrative: {
      en: `Proxy models identify ${activeFlowMechanismCount} active forward-looking flow mechanism(s) and ${activeRotationMechanismCount} recent rotation mechanism(s), consistent with ${dominantRegime.replace(/_/g, ' ')} pressure.`,
      zh: `代理模型识别${activeFlowMechanismCount}个活跃的前瞻资金流机制和${activeRotationMechanismCount}个近期轮动机制，整体资金压力${dominantRegime === 'conflicting' ? '互相冲突' : '偏向' + (dominantRegime === 'procyclical_buy' ? '买入' : '卖出')}。`
    }
  };

  const snapshot = { 
    status: 'ok',
    schemaVersion: 3,
    snapshotQuality,
    marketDataAsOf: commonAsOfDate,
    decisionDate,
    signalAvailableAt: [
      volControl.signalAvailableAt, 
      leveragedEtf.signalAvailableAt, 
      ctaFuturesProxy.signalAvailableAt, 
      ctaEtfProxy.signalAvailableAt, 
      riskParityProxy.signalAvailableAt, 
      pensionRebalance.signalAvailableAt
    ].reduce((a, b) => (a > b ? a : b)),
    firstTradableSession: [
      volControl.firstTradableSession, 
      leveragedEtf.firstTradableSession, 
      ctaFuturesProxy.firstTradableSession, 
      ctaEtfProxy.firstTradableSession, 
      riskParityProxy.firstTradableSession, 
      pensionRebalance.firstTradableSession
    ].reduce((a, b) => (a > b ? a : b)),
    engineVersion: "flow-engine-v3.0.0",
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
      vcMechanicalPressure: vcMechPressure,
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
}
module.exports = { runFlowEngine };
