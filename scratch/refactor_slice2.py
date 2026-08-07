import re

with open('backtest/build_historical_snapshots.js', 'r') as f:
    content = f.read()

old_slice = """function sliceData(dataObj, maxDate, isFred = false, lagOffset = 0) {
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

new_slice = """function sliceData(dataObj, maxDate, isFred = false, lagOffset = 0) {
  const sliced = {};
  const signalAvailableAt = getNYCloseTime(maxDate);
  
  for (const [key, arr] of Object.entries(dataObj)) {
    if (Array.isArray(arr)) {
      let low = 0;
      let high = arr.length - 1;
      let endIdx = -1;
      
      while (low <= high) {
         let mid = Math.floor((low + high) / 2);
         const d = arr[mid];
         const dateStr = Array.isArray(d) ? d[0] : d.date;
         
         let isAvailable = false;
         if (isFred) {
             const availableAtTime = new Date(getFredAvailableAt(key, dateStr, lagOffset)).getTime();
             isAvailable = availableAtTime <= signalAvailableAt;
         } else {
             isAvailable = dateStr <= maxDate;
         }
         
         if (isAvailable) {
             endIdx = mid;
             low = mid + 1; // Try to find a later one
         } else {
             high = mid - 1; // Need an earlier one
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
