import re
import sys

with open('backtest/build_historical_snapshots.js', 'r') as f:
    content = f.read()

# 1. Add getNYCloseTime
ny_close_func = """function getNYCloseTime(dateStr) {
  const dt = new Date(dateStr + 'T12:00:00Z'); 
  const nyString = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    timeZoneName: 'shortOffset'
  }).format(dt);
  const offset = nyString.split('GMT')[1]; // -5 or -4
  const offsetStr = offset.length === 2 ? offset.slice(0,1) + '0' + offset.slice(1) + ':00' : offset + ':00';
  return new Date(dateStr + 'T17:00:00' + offsetStr).getTime();
}

function sliceData(dataObj, maxDate, isFred = false, lagOffset = 0) {"""
content = content.replace("function sliceData(dataObj, maxDate, isFred = false, lagOffset = 0) {", ny_close_func)

# 2. Fix sliceData signalAvailableAt
old_slice = "  const signalAvailableAt = new Date(maxDate + 'T18:00:00Z').getTime();"
new_slice = "  const signalAvailableAt = getNYCloseTime(maxDate);"
content = content.replace(old_slice, new_slice)

# 3. Change previousState loop vars
old_vars = """  let previousState = null;
  let previousStateHash = null;
  let previousModelStateHash = null;"""
new_vars = """  let previousModelState = null;
  let previousStateHash = null;
  let previousModelStateHash = null;"""
content = content.replace(old_vars, new_vars)

# 4. Extract { snapshot, nextModelState }
old_loop_1 = """    const signalTime = currentDate + 'T18:00:00Z';
    
    const summary = runReplayFlows({ fred: slicedFred, yahoo: slicedYahoo, valuation }, currentDate, signalTime, currentDate, previousState);
    
    const outputStateHash = hashState(summary);
    const modelState = summary.modules && summary.modules.volControl && summary.modules.volControl.actualExpHistory ? summary.modules.volControl.actualExpHistory : null;
    const outputModelStateHash = hashState(modelState);
    
    // Only store snapshots if within the view window
    if (t >= VIEW_START_DATE) {
      summary.meta = summary.meta || {};
      summary.meta.replayGenesisDate = relevantTradingDays[0];
      summary.meta.viewStartDate = VIEW_START_DATE;
      summary.meta.viewEndDate = VIEW_END_DATE;
      summary.meta.warmupTradingDays = c - 1;
      summary.meta.previousStateHash = previousStateHash;
      summary.meta.outputStateHash = outputStateHash;
      summary.meta.previousModelStateHash = previousModelStateHash;
      summary.meta.outputModelStateHash = outputModelStateHash;
      summary.meta.stateChainBreaks = 0; // Strictly enforced by the sequential loop
      
      snapshots[t] = summary;
    }
    
    // Roll forward
    previousState = summary;
    previousStateHash = outputStateHash;
    previousModelStateHash = outputModelStateHash;
  }"""
new_loop_1 = """    const signalTime = new Date(getNYCloseTime(currentDate)).toISOString();
    
    const { snapshot, nextModelState } = runReplayFlows({ fred: slicedFred, yahoo: slicedYahoo, valuation }, currentDate, signalTime, currentDate, previousModelState);
    
    const outputStateHash = hashState(snapshot);
    const outputModelStateHash = hashState(nextModelState);
    
    // Only store snapshots if within the view window
    if (t >= VIEW_START_DATE) {
      snapshot.meta = snapshot.meta || {};
      snapshot.meta.replayGenesisDate = relevantTradingDays[0];
      snapshot.meta.viewStartDate = VIEW_START_DATE;
      snapshot.meta.viewEndDate = VIEW_END_DATE;
      snapshot.meta.warmupTradingDays = c - 1;
      snapshot.meta.previousStateHash = previousStateHash;
      snapshot.meta.outputStateHash = outputStateHash;
      snapshot.meta.previousModelStateHash = previousModelStateHash;
      snapshot.meta.outputModelStateHash = outputModelStateHash;
      snapshot.meta.stateChainBreaks = 0; // Strictly enforced by the sequential loop
      
      snapshots[t] = snapshot;
    }
    
    // Roll forward
    previousModelState = nextModelState;
    previousStateHash = outputStateHash;
    previousModelStateHash = outputModelStateHash;
  }"""
content = content.replace(old_loop_1, new_loop_1)

with open('backtest/build_historical_snapshots.js', 'w') as f:
    f.write(content)
