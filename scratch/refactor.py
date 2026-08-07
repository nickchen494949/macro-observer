import json
import re
import sys

def modify_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Add commonAsOfDate logic
    
    # We will find the part where spx is fetched and insert commonAsOfDate logic
    common_date_logic = """
  const getLatestDate = (arr) => (arr && arr.length > 0) ? arr[arr.length - 1][0] : null;

  // Enforce Common As-Of Date
  const crossAssetSeries = [
    (store.yahoo && store.yahoo['^GSPC']) ? store.yahoo['^GSPC'] : null,
    (store.yahoo && store.yahoo['^IXIC']) ? store.yahoo['^IXIC'] : null,
    (store.yahoo && store.yahoo['SOXX']) ? store.yahoo['SOXX'] : null,
    (store.fred && store.fred['DGS10']) ? store.fred['DGS10'] : null,
    (store.fred && store.fred['BAMLH0A0HYM2']) ? store.fred['BAMLH0A0HYM2'] : null,
    (store.yahoo && store.yahoo['CL=F']) ? store.yahoo['CL=F'] : null,
    (store.yahoo && store.yahoo['GC=F']) ? store.yahoo['GC=F'] : null,
    (store.yahoo && store.yahoo['HG=F']) ? store.yahoo['HG=F'] : null
  ];
  
  let commonAsOfDate = null;
  let isSeriesTooStale = false;
  
  const latestDates = crossAssetSeries.filter(s => s && s.length > 0).map(s => s[s.length - 1][0]).sort();
  if (latestDates.length > 0) {
      commonAsOfDate = latestDates[0]; // min of the latest dates
      const maxDate = latestDates[latestDates.length - 1];
      const getBusinessDays = (d1, d2) => {
          let count = 0;
          let cur = new Date(d1);
          const end = new Date(d2);
          while (cur < end) {
              cur.setDate(cur.getDate() + 1);
              if (cur.getDay() !== 0 && cur.getDay() !== 6) count++;
          }
          return count;
      };
      if (getBusinessDays(commonAsOfDate, maxDate) > 2) {
          isSeriesTooStale = true;
      }
  }

  const truncateToCommon = (arr) => {
    if (!arr || !commonAsOfDate) return null;
    const truncated = arr.filter(pt => pt[0] <= commonAsOfDate);
    return truncated.length > 0 ? truncated : null;
  };

  const spx = truncateToCommon((store.yahoo && store.yahoo['^GSPC']) ? store.yahoo['^GSPC'] : null);
  const vix = truncateToCommon((store.yahoo && store.yahoo['^VIX']) ? store.yahoo['^VIX'] : null);
  const ndx = truncateToCommon((store.yahoo && store.yahoo['^IXIC']) ? store.yahoo['^IXIC'] : null);
  const sox = truncateToCommon((store.yahoo && store.yahoo['SOXX']) ? store.yahoo['SOXX'] : null);
  const dgs10 = truncateToCommon((store.fred && store.fred['DGS10']) ? store.fred['DGS10'] : null);
  const hyOasData = truncateToCommon(store.fred && store.fred['BAMLH0A0HYM2'] ? store.fred['BAMLH0A0HYM2'] : null);
  
  const spxDate = commonAsOfDate; // Using common date everywhere
"""
    # Find insertion point
    target = r"  const spx = \(store.yahoo && store.yahoo\['\^GSPC'\]\) \? store.yahoo\['\^GSPC'\] : null;\n  const vix = .*?  const spxDate = getLatestDate\(spx\);"
    content = re.sub(target, common_date_logic, content, flags=re.DOTALL)

    # Replace volControl return wrapper
    vol_status = """
  let vcStatus = isSeriesTooStale ? 'series_too_stale' : (spx ? 'ok' : 'insufficient_data');
  const volControl = {
    status: vcStatus,
    targetExposureToday: vcStatus === 'ok' ? Number(targetExposureToday.toFixed(4)) : null,
    actualExposureYesterday: vcStatus === 'ok' ? Number(actualExposureYesterday.toFixed(4)) : null,
    actualExposureToday: vcStatus === 'ok' ? Number(actualExposureToday.toFixed(4)) : null,
    dailyPositionChange: vcStatus === 'ok' ? Number(dailyPositionChange.toFixed(4)) : null,
    fiveDayActualChange: vcStatus === 'ok' ? Number(fiveDayActualChange.toFixed(4)) : null,
    remainingExposureGap: vcStatus === 'ok' ? Number(remainingExposureGap.toFixed(4)) : null,
    estimatedDailyFlowUsd: vcStatus === 'ok' ? estimatedDailyFlowUsd : null,
    estimatedFlowRange: vcStatus === 'ok' ? estimatedFlowRange : null,
    nextDayEstimateIfTargetUnchanged: vcStatus === 'ok' ? nextDayEstimateIfTargetUnchanged : null
  };
"""
    content = re.sub(r"  const volControl = \{.*?    frequency: 'daily'\n  \};\n", vol_status, content, flags=re.DOTALL)

    # Add back the internal properties needed by summary
    vol_status = vol_status.strip() + "\n  volControl.flowPressure = vcStatus === 'ok' ? flowPressure : 'none';\n  volControl.aggregateDirection = vcStatus === 'ok' ? (dailyPositionChange > 0 ? 'buy' : 'sell') : 'neutral';\n"
    content = content.replace(vol_status.strip(), vol_status)

    # Leveraged ETF
    letf_status = """
  let letfStatus = isSeriesTooStale ? 'series_too_stale' : (spx ? 'ok' : 'insufficient_data');
  const leveragedEtf = {
    status: letfStatus,
    totalGrossRebalanceUsd: letfStatus === 'ok' ? totalGrossRebalance : null,
    estimateRange: letfStatus === 'ok' ? { low: totalGrossRebalance * 0.6, high: totalGrossRebalance * 1.2 } : null
  };
  leveragedEtf.aggregateDirection = letfStatus === 'ok' ? letfAggDir : 'neutral';
"""
    content = re.sub(r"  const leveragedEtf = \{.*?    frequency: 'daily'\n  \};\n", letf_status, content, flags=re.DOTALL)

    # CTA Trend
    cta_status = """
  let ctaStatus = isSeriesTooStale ? 'series_too_stale' : (spx ? 'ok' : 'insufficient_data');
  const ctaTrend = {
    status: ctaStatus,
    positionRegime: ctaStatus === 'ok' ? ctaPositionRegime : null,
    flowPressure: ctaStatus === 'ok' ? ctaFlowPressure : null,
    aggregatePositionChange: ctaStatus === 'ok' ? ctaAggregateChange : null,
    assets: ctaStatus === 'ok' ? ctaAssets : null,
    commonAsOfDate: ctaStatus === 'ok' ? commonAsOfDate : null
  };
"""
    content = re.sub(r"  const ctaTrend = \{.*?    frequency: 'daily'\n  \};\n", cta_status, content, flags=re.DOTALL)

    # Risk Parity
    rp_status = """
  let rpStatus = isSeriesTooStale ? 'series_too_stale' : (spx && dgs10 ? 'ok' : 'insufficient_data');
  const riskParityProxy = {
    status: rpStatus,
    equityAllocationChange5d: rpStatus === 'ok' ? equityAllocationChange5d : null,
    bondAllocationChange5d: rpStatus === 'ok' ? bondAllocationChange5d : null,
    modelLeverageChange5d: rpStatus === 'ok' ? modelLeverageChange5d : null,
    allocationDirection: rpStatus === 'ok' ? allocationDirection : null,
    deleveragingPressure: rpStatus === 'ok' ? deleveragingPressure : null,
    commonAsOfDate: rpStatus === 'ok' ? commonAsOfDate : null
  };
"""
    content = re.sub(r"  const riskParityProxy = \{.*?    frequency: 'daily'\n  \};\n", rp_status, content, flags=re.DOTALL)

    # Pension Rebalance
    pension_status = """
  let penStatus = spx && dgs10 ? 'ok' : 'insufficient_data';
  if (penStatus === 'ok' && !isRebalanceWindow) penStatus = 'not_in_window';
  
  const pensionRebalance = {
    status: penStatus,
    currentEquityWeight: (spx && dgs10) ? currentEquityWeight : null,
    targetEquityWeight: (spx && dgs10) ? targetEquityWeight : null,
    equityOverweightPct: (spx && dgs10) ? equityOverweightPct : null,
    daysToMonthEnd: (spx && dgs10) ? daysToMonthEnd : null,
    isRebalanceWindow: (spx && dgs10) ? isRebalanceWindow : null
  };
  pensionRebalance.expectedFlow = (spx && dgs10) ? expectedFlow : 'none';
"""
    content = re.sub(r"  const pensionRebalance = \{.*?    frequency: 'daily'\n  \};\n", pension_status, content, flags=re.DOTALL)

    # Stress Conditions
    # Fix the missingInputs array
    content = content.replace("indicators.push('Missing inputs: VIX, HY OAS')", "missingInputs.push('VIX', 'HY_OAS')")
    content = content.replace("indicators.push('Missing inputs: VIX')", "missingInputs.push('VIX')")
    content = content.replace("indicators.push('Missing inputs: HY OAS')", "missingInputs.push('HY_OAS')")

    stress_logic = """
  let stressScore = null, indicators = [], missingInputs = [], stressStatus = 'insufficient_data';
  if (vixLatest == null || Number.isNaN(vixLatest)) missingInputs.push('VIX');
  if (hyOasBp == null || Number.isNaN(hyOasBp)) missingInputs.push('HY_OAS');
  
  if (missingInputs.length === 0) {
    stressScore = 0;
    if (vixLatest > 40) { stressScore += 40; indicators.push('VIX > 40'); }
    else if (vixLatest > 30) { stressScore += 30; indicators.push('VIX > 30'); }
    else if (vixLatest > 25) { stressScore += 20; indicators.push('VIX > 25'); }

    if (vixChange5d > 5) { stressScore += 15; indicators.push('VIX spiked'); }

    if (hyOasBp > 400) { stressScore += 40; indicators.push('HY OAS > 400bp'); }
    else if (hyOasBp > 300) { stressScore += 20; indicators.push('HY OAS > 300bp'); }

    if (hyOasChange5d > 50) { stressScore += 20; indicators.push('HY OAS spiked'); }

    if (crossAssetCorr > 0.4) { stressScore += 15; indicators.push('High Cross-Asset Corr'); }

    if (stressScore >= 70) stressStatus = 'crisis';
    else if (stressScore >= 50) stressStatus = 'stress';
    else if (stressScore >= 30) stressStatus = 'elevated';
    else if (stressScore >= 15) stressStatus = 'watch';
    else stressStatus = 'calm';
  }
"""
    content = re.sub(r"  let stressScore = null, indicators = \[\], stressStatus = 'insufficient_data';\n  if \(vixLatest != null && !Number.isNaN\(vixLatest\) && hyOasBp != null && !Number.isNaN\(hyOasBp\)\) \{.*?  \}(?=  const stressConditions = \{)", stress_logic, content, flags=re.DOTALL)

    stress_status = """
  const stressConditions = {
    status: isSeriesTooStale ? 'series_too_stale' : stressStatus,
    stressScore: missingInputs.length === 0 ? stressScore : null,
    vix: missingInputs.length === 0 ? vixLatest : null,
    hyOas: missingInputs.length === 0 ? hyOasBp : null,
    estimatedFlowUsd: null,
    missingInputs: missingInputs.length > 0 ? missingInputs : undefined
  };
"""
    content = re.sub(r"  const stressConditions = \{.*?    frequency: 'daily'\n  \};\n", stress_status, content, flags=re.DOTALL)


    # Flow Timeline & Summary
    summary_logic = """
  const excludedModules = [];
  if (volControl.status !== 'ok') excludedModules.push('volControl');
  if (leveragedEtf.status !== 'ok') excludedModules.push('leveragedEtf');
  if (ctaTrend.status !== 'ok') excludedModules.push('ctaTrend');
  if (riskParityProxy.status !== 'ok') excludedModules.push('riskParityProxy');
  if (stressConditions.status === 'insufficient_data' || stressConditions.status === 'series_too_stale') excludedModules.push('stressConditions');

  let snapshotQuality = excludedModules.length > 0 ? 'partial' : 'complete';

  const rpSummary = riskParityProxy.status === 'ok' ? (
    riskParityProxy.deleveragingPressure !== 'none' ? riskParityProxy.deleveragingPressure : 
    (riskParityProxy.allocationDirection !== 'stable' ? 'rotation_' + riskParityProxy.allocationDirection : 'none')
  ) : 'unavailable';

  const summary = {
    trendAmplifiers: { 
      volControl: volControl.status === 'ok' ? volControl.flowPressure : 'unavailable', 
      leveragedEtf: leveragedEtf.status === 'ok' ? leveragedEtf.aggregateDirection : 'unavailable', 
      cta: ctaTrend.status === 'ok' ? ctaTrend.flowPressure : 'unavailable'
    },
    crossAssetDeRisking: { 
      riskParity: rpSummary, 
      stressLevel: stressConditions.status === 'insufficient_data' || stressConditions.status === 'series_too_stale' ? 'unavailable' : stressConditions.status 
    },
    counterCyclicalFlows: { 
      pension: pensionRebalance.status === 'ok' || pensionRebalance.status === 'not_in_window' ? pensionRebalance.expectedFlow : 'unavailable' 
    },
    dominantRegime,
    mechanismCount,
    driverCount: independentDataDomains.length,
    duplicatedDriverCount,
    independentDataDomains,
    confidence: snapshotQuality === 'partial' ? 'reduced' : (duplicatedDriverCount > 0 ? 'medium_low' : 'high'),
    excludedModules,
    flowTimeline,
    narrative: { 
      en: `Proxy models identify ${mechanismCount} active mechanism(s) across ${independentDataDomains.length} data domain(s), consistent with ${dominantRegime.replace(/_/g, ' ')} positioning pressure.${duplicatedDriverCount > 0 ? ` Note: ${equityPriceDrivenCount} mechanisms share equity price as common driver.` : ''}`,
      zh: `代理模型识别 ${mechanismCount} 个活跃机制，跨 ${independentDataDomains.length} 个数据域，与${dominantRegime === 'procyclical_sell' ? '顺周期卖出' : dominantRegime === 'procyclical_buy' ? '顺周期买入' : '冲突'}压力一致。${duplicatedDriverCount > 0 ? `注：${equityPriceDrivenCount} 个机制共享股价为共同驱动因素。` : ''}`
    }
  };

  return { 
    status: 'ok',
    schemaVersion: 1,
    snapshotQuality,
    marketDataAsOf: commonAsOfDate,
    snapshotGeneratedAt: new Date().toISOString(),
    summary, 
    volControl, 
    leveragedEtf, 
    ctaTrend, 
    riskParityProxy, 
    pensionRebalance, 
    stressConditions 
  };
"""
    content = re.sub(r"  const rpSummary = riskParityProxy\.deleveragingPressure.*?\};\n\n  return \{ volControl.*?\}\n", summary_logic, content, flags=re.DOTALL)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

modify_file('lib/flow_engine.js')
