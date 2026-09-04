const fs = require('fs');
const path = require('path');
const { runFlowEngine } = require('./flow_engine');

function getNewYorkClock(now = new Date()) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23'
  }).formatToParts(now);
  const pick = (type) => parts.find(p => p.type === type)?.value;
  const year = pick('year');
  const month = pick('month');
  const day = pick('day');
  const hour = Number(pick('hour'));
  const minute = Number(pick('minute'));
  return {
    date: `${year}-${month}-${day}`,
    hour,
    minute,
    minutesSinceMidnight: hour * 60 + minute
  };
}

function hasValidYahooObservation(point) {
  if (!Array.isArray(point) || typeof point[0] !== 'string') return false;
  const value = point[1];
  if (Number.isFinite(value)) return true;
  if (value && typeof value === 'object') {
    return Number.isFinite(value.adjClose) || Number.isFinite(value.close);
  }
  return false;
}

function loadNyseCalendar() {
  try {
    const calendarPath = path.join(__dirname, '../data/nyse_calendar.json');
    const parsed = JSON.parse(fs.readFileSync(calendarPath, 'utf8'));
    return Array.isArray(parsed) ? parsed.filter(d => typeof d === 'string').sort() : [];
  } catch (_) {
    return [];
  }
}

function latestCompletedCalendarSession(now = new Date(), calendar = loadNyseCalendar()) {
  const ny = getNewYorkClock(now);
  // A regular NYSE session is considered complete at 16:00 New York time.
  // The actual market-data date is still capped by observed SPX data below,
  // so this cannot manufacture a session that the downloader has not received.
  const todayIsComplete = ny.minutesSinceMidnight >= 16 * 60;
  let latest = null;
  for (const date of calendar) {
    if (date < ny.date || (date === ny.date && todayIsComplete)) latest = date;
    else if (date > ny.date || (date === ny.date && !todayIsComplete)) break;
  }
  return latest;
}

function latestObservedSpxDate(store) {
  const series = store?.yahoo?.['^GSPC'];
  if (!Array.isArray(series)) return null;
  let latest = null;
  for (const point of series) {
    if (!hasValidYahooObservation(point)) continue;
    if (!latest || point[0] > latest) latest = point[0];
  }
  return latest;
}

function getLatestCompletedUsSessionDate(store, now = new Date()) {
  const observed = latestObservedSpxDate(store);
  const completed = latestCompletedCalendarSession(now);

  // Production marketDataAsOf must satisfy BOTH:
  // 1) the US session has actually completed, and
  // 2) SPX data for that date has actually been observed.
  if (observed && completed) return observed < completed ? observed : completed;

  // Conservative fallback if the NYSE calendar file is unavailable: never accept
  // a same-day SPX observation before the regular 16:00 New York close.
  if (observed) {
    const ny = getNewYorkClock(now);
    if (observed < ny.date) return observed;
    if (observed === ny.date && ny.minutesSinceMidnight >= 16 * 60) return observed;
  }

  return null;
}

function buildProductionEngineInputs(store, now = new Date()) {
  const ny = getNewYorkClock(now);
  const completedMarketDate = getLatestCompletedUsSessionDate(store, now);

  return {
    // Decision date is the current New York calendar date, not UTC/Malaysia date.
    decisionDate: ny.date,
    signalAvailableAt: now.toISOString(),
    // Never advance production market state beyond the latest completed US session
    // for which SPX data is actually present.
    marketDataAsOf: completedMarketDate || ny.date,
    inputsAsOfDecision: store,
    previousModelState: null,
    modelConfig: {
      useEtfProxy: false
    }
  };
}

function runProductionFlows(store) {
  const config = buildProductionEngineInputs(store);
  const { snapshot, nextModelState } = runFlowEngine(config);
  return snapshot; // Production API only needs snapshot currently
}

function buildReplayEngineInputs(storeSlice, decisionDate, signalAvailableAt, marketDataAsOf, previousModelState) {
  return {
    decisionDate,
    signalAvailableAt,
    marketDataAsOf,
    inputsAsOfDecision: storeSlice, // Contains only data available BEFORE signalAvailableAt
    previousModelState,
    modelConfig: {
      useEtfProxy: true // Phase 1 specifies backtest uses ETF proxy
    }
  };
}

function runReplayFlows(storeSlice, decisionDate, signalAvailableAt, marketDataAsOf, previousModelState) {
  const config = buildReplayEngineInputs(storeSlice, decisionDate, signalAvailableAt, marketDataAsOf, previousModelState);
  return runFlowEngine(config); // Returns { snapshot, nextModelState }
}

module.exports = {
  buildProductionEngineInputs,
  runProductionFlows,
  buildReplayEngineInputs,
  runReplayFlows,
  // Exported for deterministic tests.
  getNewYorkClock,
  getLatestCompletedUsSessionDate,
  latestCompletedCalendarSession,
  latestObservedSpxDate
};
