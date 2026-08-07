import re

with open('lib/flow_engine.js', 'r') as f:
    content = f.read()

# I will find the calendar logic and replace it with per-module calendars.
old_cal = """  // --- V3: Module-Specific Availability & Market Calendar ---
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
  const isSeriesTooStale = isStale(commonAsOfDate);"""


new_cal = """  // --- V3.1: Strict Module-Specific Calendars ---
  // US Equity Calendar (for VolControl, CTA ETF, Pension, RiskParity Equity)
  const equityCalSource = (store.yahoo && store.yahoo['^GSPC']) ? store.yahoo['^GSPC'] : [];
  const usEquityCalendar = equityCalSource.map(pt => pt[0]).sort();

  // Futures Calendar (for CTA Futures)
  const futuresCalSource = (store.yahoo && store.yahoo['CL=F']) ? store.yahoo['CL=F'] : [];
  let futuresCalendar = futuresCalSource.map(pt => pt[0]).sort();
  if (futuresCalendar.length === 0) futuresCalendar = usEquityCalendar; // fallback

  // PIT Calendar (for FRED observation dates up to availableAt cutoff)
  const getPitCalendar = (fredSeries) => {
    if (!fredSeries) return [];
    return fredSeries.map(pt => pt[0]).sort();
  };

  const alignToCalendar = (symbol, arr, purpose, calendar) => {
    if (!arr || !calendar || calendar.length === 0) return null;
    const aligned = [];
    const sourceMap = new Map();
    for (const pt of arr) {
       sourceMap.set(pt[0], pt[1]);
    }
    
    for (const date of calendar) {
      if (date > marketDataAsOf) break;
      let val = sourceMap.has(date) ? sourceMap.get(date) : null;
      if (val != null && typeof val === 'object' && purpose) {
        val = getFieldForPurpose(symbol, val, purpose);
      }
      aligned.push([date, val]); // explicit missing-session insertion
    }
    return aligned.length > 0 ? aligned : null;
  };

  // Pre-aligned assets
  const spx = alignToCalendar('^GSPC', (store.yahoo && store.yahoo['^GSPC']) ? store.yahoo['^GSPC'] : null, 'cta_close', usEquityCalendar);
  const vix = alignToCalendar('^VIX', (store.yahoo && store.yahoo['^VIX']) ? store.yahoo['^VIX'] : null, 'cta_close', usEquityCalendar);
  const ndx = alignToCalendar('^IXIC', (store.yahoo && store.yahoo['^IXIC']) ? store.yahoo['^IXIC'] : null, 'cta_close', usEquityCalendar);
  const sox = alignToCalendar('SOXX', (store.yahoo && store.yahoo['SOXX']) ? store.yahoo['SOXX'] : null, 'cta_close', usEquityCalendar);
  
  // Risk Parity FRED Leg uses PIT, but joined strictly by date downstream in RiskParity.
  // Actually, Risk Parity logic computes bond returns daily. So we must align DGS10 to usEquityCalendar so arr1 (equity) and arr2 (bond) match exactly!
  const dgs10 = alignToCalendar('DGS10', (store.fred && store.fred['DGS10']) ? store.fred['DGS10'] : null, null, usEquityCalendar);
  const hyOasData = alignToCalendar('BAMLH0A0HYM2', store.fred && store.fred['BAMLH0A0HYM2'] ? store.fred['BAMLH0A0HYM2'] : null, null, usEquityCalendar);
  
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
  };"""

content = content.replace(old_cal, new_cal)

# Find runCtaModule and inject specific calendars
old_cta_run = """    for (const cfg of assetsConfig) {
      let rawArr = cfg.src ? cfg.src[cfg.key] : null;
      let arr = alignToCalendar(cfg.key, rawArr, 'cta_close');"""
new_cta_run = """    const cal = assetsConfig === ctaFuturesAssetsConfig ? futuresCalendar : usEquityCalendar;
    for (const cfg of assetsConfig) {
      let rawArr = cfg.src ? cfg.src[cfg.key] : null;
      let arr = alignToCalendar(cfg.key, rawArr, 'cta_close', cal);"""
content = content.replace(old_cta_run, new_cta_run)

# Assign module-specific timings
# Vol Control
old_vol_c = """    nextDayEstimateIfTargetUnchanged: nextDayFlowIfTargetUnchanged,
    estimatedFlowRange: { low: Number(lowEst.toFixed(2)), high: Number(highEst.toFixed(2)) }
  };"""
new_vol_c = """    nextDayEstimateIfTargetUnchanged: nextDayFlowIfTargetUnchanged,
    estimatedFlowRange: { low: Number(lowEst.toFixed(2)), high: Number(highEst.toFixed(2)) },
    signalAvailableAt: getNYCloseTime(commonAsOfDate),
    firstTradableSession: getFirstTradable(getNYCloseTime(commonAsOfDate), usEquityCalendar)
  };"""
content = content.replace(old_vol_c, new_vol_c)

# Leveraged ETF
old_letf = """  const leveragedEtf = {
    status: letfStatus,
    totalGrossRebalanceUsd: totalLetfFlow !== null ? Number(totalLetfFlow.toFixed(2)) : null,
    estimateRange: totalLetfFlow !== null ? { low: Number((totalLetfFlow * 0.9).toFixed(2)), high: Number((totalLetfFlow * 1.1).toFixed(2)) } : null,
    funds: letfFundsOut
  };"""
new_letf = """  const leveragedEtf = {
    status: letfStatus,
    totalGrossRebalanceUsd: totalLetfFlow !== null ? Number(totalLetfFlow.toFixed(2)) : null,
    estimateRange: totalLetfFlow !== null ? { low: Number((totalLetfFlow * 0.9).toFixed(2)), high: Number((totalLetfFlow * 1.1).toFixed(2)) } : null,
    funds: letfFundsOut,
    signalAvailableAt: getNYCloseTime(commonAsOfDate),
    firstTradableSession: getFirstTradable(getNYCloseTime(commonAsOfDate), usEquityCalendar)
  };"""
content = content.replace(old_letf, new_letf)

# CTA Futures
old_cta_f = """      aggregatePositionChange: ctaStatus === 'ok' ? aggregatePositionChange : null,
      assets: ctaStatus === 'ok' ? ctaAssets : null,
      commonAsOfDate: ctaStatus === 'ok' ? commonAsOfDate : null
    };
  }

  const ctaFuturesProxy = runCtaModule(ctaFuturesAssetsConfig);"""
new_cta_f = """      aggregatePositionChange: ctaStatus === 'ok' ? aggregatePositionChange : null,
      assets: ctaStatus === 'ok' ? ctaAssets : null,
      commonAsOfDate: ctaStatus === 'ok' ? commonAsOfDate : null,
      signalAvailableAt: getNYCloseTime(commonAsOfDate), // Futures settle approx 17:00 EST
      firstTradableSession: getFirstTradable(getNYCloseTime(commonAsOfDate), assetsConfig === ctaFuturesAssetsConfig ? futuresCalendar : usEquityCalendar)
    };
  }

  const ctaFuturesProxy = runCtaModule(ctaFuturesAssetsConfig);"""
content = content.replace(old_cta_f, new_cta_f)

# Risk Parity
old_rp = """  const riskParityProxy = {
    status: rpStatus,
    equityAllocationChange5d: rpStatus === 'ok' ? Number(eqAllocChange.toFixed(4)) : null,
    bondAllocationChange5d: rpStatus === 'ok' ? Number(bondAllocChange.toFixed(4)) : null,
    modelLeverageChange5d: rpStatus === 'ok' ? Number(levChange.toFixed(4)) : null,
    allocationDirection: rpStatus === 'ok' ? allocDir : null,
    deleveragingPressure: rpStatus === 'ok' ? delevPress : null,
    commonAsOfDate
  };"""
new_rp = """  const rpSignalIso = new Date(commonAsOfDate + 'T18:30:00Z').toISOString(); // hypothetical later close
  const riskParityProxy = {
    status: rpStatus,
    equityAllocationChange5d: rpStatus === 'ok' ? Number(eqAllocChange.toFixed(4)) : null,
    bondAllocationChange5d: rpStatus === 'ok' ? Number(bondAllocChange.toFixed(4)) : null,
    modelLeverageChange5d: rpStatus === 'ok' ? Number(levChange.toFixed(4)) : null,
    allocationDirection: rpStatus === 'ok' ? allocDir : null,
    deleveragingPressure: rpStatus === 'ok' ? delevPress : null,
    commonAsOfDate,
    signalAvailableAt: rpSignalIso,
    firstTradableSession: getFirstTradable(rpSignalIso, usEquityCalendar)
  };"""
content = content.replace(old_rp, new_rp)

# Pension Rebalance
old_pen = """  const pensionRebalance = {
    status: 'ok',
    currentEquityWeight: Number(currentWeight.toFixed(4)),
    targetEquityWeight: Number(targetWeight.toFixed(4)),
    equityOverweightPct: Number(overweight.toFixed(4)),
    daysToMonthEnd: daysLeft,
    isRebalanceWindow
  };"""
new_pen = """  const pensionRebalance = {
    status: 'ok',
    currentEquityWeight: Number(currentWeight.toFixed(4)),
    targetEquityWeight: Number(targetWeight.toFixed(4)),
    equityOverweightPct: Number(overweight.toFixed(4)),
    daysToMonthEnd: daysLeft,
    isRebalanceWindow,
    signalAvailableAt: getNYCloseTime(commonAsOfDate),
    firstTradableSession: getFirstTradable(getNYCloseTime(commonAsOfDate), usEquityCalendar)
  };"""
content = content.replace(old_pen, new_pen)

# Summary Builder max() signalAvailableAt
# Replace old signalAvailableAt calculation
old_sig = """    decisionDate,
    signalAvailableAt,
    engineVersion: "flow-engine-v3.0.0","""
new_sig = """    decisionDate,
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
    engineVersion: "flow-engine-v3.0.0","""
content = content.replace(old_sig, new_sig)

with open('lib/flow_engine.js', 'w') as f:
    f.write(content)
