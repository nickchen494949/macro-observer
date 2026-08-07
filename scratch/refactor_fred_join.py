import re

with open('lib/flow_engine.js', 'r') as f:
    content = f.read()

old_align = """  const alignToCalendar = (symbol, arr, purpose, calendar) => {
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
      aligned.push([date, val]);
    }
    return aligned;
  };"""

new_align = """  const alignToCalendar = (symbol, arr, purpose, calendar, forwardFill = false) => {
    if (!arr || !calendar || calendar.length === 0) return null;
    const aligned = [];
    
    // Sort array by date for correct forward filling
    const sortedArr = [...arr].sort((a, b) => a[0].localeCompare(b[0]));
    const sourceMap = new Map();
    for (const pt of sortedArr) {
       sourceMap.set(pt[0], pt[1]);
    }
    
    let lastKnownVal = null;
    // For forward fill, we need the latest value BEFORE the calendar starts
    if (forwardFill && sortedArr.length > 0) {
      for (const pt of sortedArr) {
        if (pt[0] <= calendar[0]) lastKnownVal = pt[1];
      }
    }
    
    for (const date of calendar) {
      if (date > marketDataAsOf) break;
      let val = sourceMap.has(date) ? sourceMap.get(date) : null;
      
      if (forwardFill) {
        if (val !== null) lastKnownVal = val;
        val = lastKnownVal;
      }
      
      if (val != null && typeof val === 'object' && purpose) {
        val = getFieldForPurpose(symbol, val, purpose);
      }
      aligned.push([date, val]);
    }
    return aligned;
  };"""

content = content.replace(old_align, new_align)

# Fix FRED DGS10 call to use forwardFill = true
old_dgs10 = """  const dgs10 = alignToCalendar('DGS10', fred, 'riskParity', usEquityCalendar);"""
new_dgs10 = """  const fredArr = store.fred ? store.fred['DGS10'] : fred; // backwards compatibility if fred passed directly
  const dgs10 = alignToCalendar('DGS10', fredArr, 'riskParity', usEquityCalendar, true);"""
content = content.replace(old_dgs10, new_dgs10)


with open('lib/flow_engine.js', 'w') as f:
    f.write(content)
