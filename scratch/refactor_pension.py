import re

with open('lib/flow_engine.js', 'r') as f:
    content = f.read()

old_pension = """    const todayDate = new Date(todayStr);
    const daysInMonth = new Date(todayDate.getFullYear(), todayDate.getMonth() + 1, 0).getDate();
    daysLeft = daysInMonth - todayDate.getDate();
    isRebalanceWindow = daysLeft <= 4;
  }
  let expectedFlow = 'balanced';"""

new_pension = """    // Find position in month using actual trading calendar
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
  let expectedFlow = 'balanced';"""
content = content.replace(old_pension, new_pension)

with open('lib/flow_engine.js', 'w') as f:
    f.write(content)
