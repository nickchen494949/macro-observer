const holidays2025_2026 = new Set([
  '2025-01-01', '2025-01-20', '2025-02-17', '2025-04-18', '2025-05-26', '2025-06-19', '2025-07-04', '2025-09-01', '2025-11-27', '2025-12-25',
  '2026-01-01', '2026-01-19', '2026-02-16', '2026-04-03', '2026-05-25', '2026-06-19', '2026-07-03', '2026-09-07', '2026-11-26', '2026-12-25'
]);

const daysInMonth = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

function isLeapYear(year) {
  return (year % 4 === 0 && year % 100 !== 0) || (year % 400 === 0);
}

// Convert YYYY-MM-DD to days since 1970-01-00 (using simple date logic)
function dateToDays(dateStr) {
  const [year, month, day] = dateStr.split('-').map(Number);
  let days = day;
  for (let y = 1970; y < year; y++) {
    days += isLeapYear(y) ? 366 : 365;
  }
  for (let m = 1; m < month; m++) {
    if (m === 2 && isLeapYear(year)) {
      days += 29;
    } else {
      days += daysInMonth[m];
    }
  }
  return days;
}

// Convert days since 1970-01-00 to YYYY-MM-DD
function daysToDate(days) {
  let year = 1970;
  while (true) {
    const leap = isLeapYear(year);
    const yearDays = leap ? 366 : 365;
    if (days <= yearDays) break;
    days -= yearDays;
    year++;
  }
  let month = 1;
  while (true) {
    const mDays = (month === 2 && isLeapYear(year)) ? 29 : daysInMonth[month];
    if (days <= mDays) break;
    days -= mDays;
    month++;
  }
  const yStr = year.toString();
  const mStr = month.toString().padStart(2, '0');
  const dStr = days.toString().padStart(2, '0');
  return `${yStr}-${mStr}-${dStr}`;
}

function addDays(dateStr, delta) {
  return daysToDate(dateToDays(dateStr) + delta);
}

function getDayOfWeek(dateStr) {
  const d = dateToDays(dateStr);
  return (d + 3) % 7; // 1970-01-01 was Thursday (day 4). So day 1 + 3 = 4, % 7 = 4 (Thursday)
}

function isTradingDay(dateStr) {
  if (holidays2025_2026.has(dateStr)) return false;
  const dayOfWeek = getDayOfWeek(dateStr);
  if (dayOfWeek === 0 || dayOfWeek === 6) return false;
  return true;
}

function previousTradingDay(dateStr, maxGap = 7) {
  let current = dateStr;
  let gap = 0;
  while (gap < maxGap) {
    current = addDays(current, -1);
    if (isTradingDay(current)) return current;
    gap++;
  }
  return null;
}

function nextTradingDay(dateStr, maxGap = 7) {
  let current = dateStr;
  let gap = 0;
  while (gap < maxGap) {
    current = addDays(current, 1);
    if (isTradingDay(current)) return current;
    gap++;
  }
  return null;
}

function plusTradingDays(dateStr, n) {
  let current = dateStr;
  let i = 0;
  while (i < n) {
    current = addDays(current, 1);
    if (isTradingDay(current)) {
      i++;
    }
  }
  return current;
}

function resolveWindowDate(windowRef, eventDate) {
  switch (windowRef) {
    case 'previous_close':
      return previousTradingDay(eventDate, 7);
    case 'same_day_close':
      return isTradingDay(eventDate) ? eventDate : previousTradingDay(eventDate, 7);
    case 'next_trading_day_close':
      return nextTradingDay(eventDate, 7);
    case 'plus_3_trading_days_close':
      return plusTradingDays(eventDate, 3);
    case 'plus_5_trading_days_close':
      return plusTradingDays(eventDate, 5);
    default:
      return null;
  }
}

function findClosestDataPoint(dataValues, targetDate, direction, maxGapDays = 5) {
  if (!dataValues || !Array.isArray(dataValues)) return null;

  let closest = null;
  let minGap = Infinity;
  const targetDays = dateToDays(targetDate);

  for (const item of dataValues) {
    if (!item || item.length < 2) continue;
    const date = item[0];
    const value = item[1];

    if (direction === 'before' && date > targetDate) continue;
    if (direction === 'after' && date < targetDate) continue;

    const itemDays = dateToDays(date);
    const gapDays = Math.abs(itemDays - targetDays);

    if (gapDays <= maxGapDays) {
      if (gapDays < minGap) {
        minGap = gapDays;
        closest = { date, value, gapDays };
      }
    }
  }

  return closest;
}

module.exports = {
  isTradingDay,
  previousTradingDay,
  nextTradingDay,
  plusTradingDays,
  resolveWindowDate,
  findClosestDataPoint
};
