import re

with open("lib/flow_engine.js", "r") as f:
    text = f.read()

# Remove the broken block
broken_block = """  let rpStatus = isSeriesTooStale ? 'series_too_stale' : (spx && dgs10 ? 'ok' : 'insufficient_data');
  const riskParityProxy = {
    status: rpStatus,
    equityAllocationChange5d: rpStatus === 'ok' ? equityAllocationChange5d : null,
    bondAllocationChange5d: rpStatus === 'ok' ? bondAllocationChange5d : null,
    modelLeverageChange5d: rpStatus === 'ok' ? modelLeverageChange5d : null,
    allocationDirection: rpStatus === 'ok' ? allocationDirection : null,
    deleveragingPressure: rpStatus === 'ok' ? deleveragingPressure : null,
    totalDeRisking: rpStatus === 'ok' ? (deleveragingPressure === 'broad_deleveraging') : null,
    commonAsOfDate: rpStatus === 'ok' ? commonAsOfDate : null
  };;"""

text = text.replace(broken_block, "")

# Add totalDeRisking correctly to riskParityProxy down below
rp_target = """  const riskParityProxy = {
    status: rpStatus,
    equityAllocationChange5d: rpStatus === 'ok' ? equityAllocationChange5d : null,
    bondAllocationChange5d: rpStatus === 'ok' ? bondAllocationChange5d : null,
    modelLeverageChange5d: rpStatus === 'ok' ? modelLeverageChange5d : null,
    allocationDirection: rpStatus === 'ok' ? allocationDirection : null,
    deleveragingPressure: rpStatus === 'ok' ? deleveragingPressure : null,
    commonAsOfDate: rpStatus === 'ok' ? commonAsOfDate : null
  };"""

rp_fix = """  const riskParityProxy = {
    status: rpStatus,
    equityAllocationChange5d: rpStatus === 'ok' ? equityAllocationChange5d : null,
    bondAllocationChange5d: rpStatus === 'ok' ? bondAllocationChange5d : null,
    modelLeverageChange5d: rpStatus === 'ok' ? modelLeverageChange5d : null,
    allocationDirection: rpStatus === 'ok' ? allocationDirection : null,
    deleveragingPressure: rpStatus === 'ok' ? deleveragingPressure : null,
    totalDeRisking: rpStatus === 'ok' ? (deleveragingPressure === 'broad_deleveraging') : null,
    commonAsOfDate: rpStatus === 'ok' ? commonAsOfDate : null
  };"""

text = text.replace(rp_target, rp_fix)

with open("lib/flow_engine.js", "w") as f:
    f.write(text)
