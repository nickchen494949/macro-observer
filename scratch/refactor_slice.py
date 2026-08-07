import re

with open('backtest/build_historical_snapshots.js', 'r') as f:
    content = f.read()

old_slice = """function sliceData(dataObj, maxDate, isFred = false, lagOffset = 0) {
  const sliced = {};
  const signalAvailableAt = getNYCloseTime(maxDate);
  
  for (const [key, arr] of Object.entries(dataObj)) {
    if (Array.isArray(arr)) {
      const filtered = arr.filter(d => {
        const dateStr = Array.isArray(d) ? d[0] : d.date;
        if (isFred) {
          // Point-in-time quality: approximate (Conservative publication-lag)
          const availableAtTime = new Date(getFredAvailableAt(key, dateStr, lagOffset)).getTime();
          return availableAtTime <= signalAvailableAt;
        } else {
          return dateStr <= maxDate;
        }
      });
      sliced[key] = filtered;
    } else {
      sliced[key] = arr;
    }
  }
  return sliced;
}"""

new_slice = """function sliceData(dataObj, maxDate, isFred = false, lagOffset = 0) {
  const sliced = {};
  const signalAvailableAt = getNYCloseTime(maxDate);
  
  for (const [key, arr] of Object.entries(dataObj)) {
    if (Array.isArray(arr)) {
      // Find the slice index by going backwards
      let endIdx = -1;
      for (let i = arr.length - 1; i >= 0; i--) {
        const d = arr[i];
        const dateStr = Array.isArray(d) ? d[0] : d.date;
        
        if (isFred) {
           const availableAtTime = new Date(getFredAvailableAt(key, dateStr, lagOffset)).getTime();
           if (availableAtTime <= signalAvailableAt) {
               endIdx = i;
               break;
           }
        } else {
           if (dateStr <= maxDate) {
               endIdx = i;
               break;
           }
        }
      }
      sliced[key] = endIdx >= 0 ? arr.slice(0, endIdx + 1) : [];
    } else {
      sliced[key] = arr;
    }
  }
  return sliced;
}"""

content = content.replace(old_slice, new_slice)

with open('backtest/build_historical_snapshots.js', 'w') as f:
    f.write(content)
