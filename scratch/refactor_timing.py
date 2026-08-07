import re

with open('lib/flow_engine.js', 'r') as f:
    content = f.read()

# VolControl
old_vc = """    missingSessionsSinceLastUpdate,
    amountConfidence: stateUpdateStr === 'resumed_after_missing_data' ? 'unavailable' : undefined
  };"""

new_vc = """    missingSessionsSinceLastUpdate,
    amountConfidence: stateUpdateStr === 'resumed_after_missing_data' ? 'unavailable' : undefined,
    signalAvailableAt: vcStatus === 'ok' ? new Date(getNYCloseTime(commonAsOfDate)).toISOString() : null,
    firstTradableSession: vcStatus === 'ok' ? getFirstTradable(getNYCloseTime(commonAsOfDate), usEquityCalendar) : null
  };"""
content = content.replace(old_vc, new_vc)

# RiskParity
old_rp = """    totalDeRisking: rpStatus === 'ok' ? (dp === 'high') : null,
    commonAsOfDate: rpStatus === 'ok' ? commonAsOfDate : null
  };"""

new_rp = """    totalDeRisking: rpStatus === 'ok' ? (dp === 'high') : null,
    commonAsOfDate: rpStatus === 'ok' ? commonAsOfDate : null,
    signalAvailableAt: rpStatus === 'ok' ? new Date(getNYCloseTime(commonAsOfDate)).toISOString() : null,
    firstTradableSession: rpStatus === 'ok' ? getFirstTradable(getNYCloseTime(commonAsOfDate), usEquityCalendar) : null
  };"""
content = content.replace(old_rp, new_rp)

# PensionRebalance
old_pen = """    daysToMonthEnd: (spx && dgs10) ? daysLeft : null,
    isRebalanceWindow: (spx && dgs10) ? isRebalanceWindow : null,
    expectedFlow: (spx && dgs10) ? expectedFlow : 'none'
  };"""

new_pen = """    daysToMonthEnd: (spx && dgs10) ? daysLeft : null,
    isRebalanceWindow: (spx && dgs10) ? isRebalanceWindow : null,
    expectedFlow: (spx && dgs10) ? expectedFlow : 'none',
    signalAvailableAt: (spx && dgs10) ? new Date(getNYCloseTime(commonAsOfDate)).toISOString() : null,
    firstTradableSession: (spx && dgs10) ? getFirstTradable(getNYCloseTime(commonAsOfDate), usEquityCalendar) : null
  };"""
content = content.replace(old_pen, new_pen)

# Add Leveraged ETF just in case
old_letf = """  const leveragedEtf = {
    status: letfStatus,
    targetExposureToday: letfStatus === 'ok' ? 3.0 : null,
    estimatedDailyFlowUsd: letfStatus === 'ok' ? letfFlow : null,
    flowPressure: letfStatus === 'ok' ? letfPressure : 'none'
  };"""

new_letf = """  const leveragedEtf = {
    status: letfStatus,
    targetExposureToday: letfStatus === 'ok' ? 3.0 : null,
    estimatedDailyFlowUsd: letfStatus === 'ok' ? letfFlow : null,
    flowPressure: letfStatus === 'ok' ? letfPressure : 'none',
    signalAvailableAt: letfStatus === 'ok' ? new Date(getNYCloseTime(commonAsOfDate)).toISOString() : null,
    firstTradableSession: letfStatus === 'ok' ? getFirstTradable(getNYCloseTime(commonAsOfDate), usEquityCalendar) : null
  };"""
content = content.replace(old_letf, new_letf)

with open('lib/flow_engine.js', 'w') as f:
    f.write(content)
