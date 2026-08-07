const fs = require('fs');
const path = require('path');

// Load quantification rules
const rulesPath = path.join(__dirname, '..', 'config', 'quantification_rules.json');
let quantificationRules = {};
try {
  const fileContent = fs.readFileSync(rulesPath, 'utf8');
  quantificationRules = JSON.parse(fileContent).rules;
} catch (e) {
  console.error("Failed to load quantification_rules.json", e);
}

/**
 * Calculate the expanding historical percentile.
 * Only uses data up to the current observation date to prevent look-ahead bias.
 */
function calculateExpandingPercentile(series, currentValue, asOfDate) {
  if (!series || series.length === 0) return null;
  // Filter history strictly <= asOfDate (which is usually the last date in the series anyway, but strict for backtesting)
  const history = series.filter(obs => new Date(obs[0]) <= new Date(asOfDate)).map(obs => obs[1]);
  if (history.length === 0) return null;
  
  history.sort((a, b) => a - b);
  // Find index of currentValue
  let countBelow = 0;
  for (let i = 0; i < history.length; i++) {
    if (history[i] < currentValue) countBelow++;
    else break;
  }
  return (countBelow / history.length) * 100;
}

/**
 * Calculate the direction of the indicator over a specified window.
 * Default is to check the change compared to the value X months ago.
 */
function calculateDirection(series, asOfDate, windowStr) {
  if (!series || series.length < 2) return { direction: 'unknown', change: 0 };
  
  // Parse window string (e.g., '1m', '3m', '4w')
  let daysBack = 90; // default 3m
  if (windowStr) {
    const num = parseInt(windowStr.match(/\d+/)[0]);
    const unit = windowStr.slice(-1).toLowerCase();
    if (unit === 'm') daysBack = num * 30;
    else if (unit === 'w') daysBack = num * 7;
    else if (unit === 'd') daysBack = num;
  }
  
  const targetDate = new Date(asOfDate);
  targetDate.setDate(targetDate.getDate() - daysBack);
  
  // Find the closest observation on or before targetDate
  let pastValue = null;
  for (let i = series.length - 1; i >= 0; i--) {
    const obsDate = new Date(series[i][0]);
    if (obsDate <= targetDate) {
      pastValue = series[i][1];
      break;
    }
  }
  
  if (pastValue === null) {
    pastValue = series[0][1]; // fallback to oldest if window is too long
  }
  
  const current = series[series.length - 1][1];
  const change = current - pastValue;
  
  // Define direction string
  let direction = 'stable';
  if (change > 0.05) direction = 'rising';
  else if (change < -0.05) direction = 'falling';
  
  return { direction, change };
}

function evaluateCondition(value, conditionStr) {
  if (conditionStr === 'default') return true;
  
  const match = conditionStr.match(/(>=|<=|>|<|==)\s*(-?\d+(\.\d+)?)/);
  if (!match) return false;
  
  const operator = match[1];
  const threshold = parseFloat(match[2]);
  
  switch(operator) {
    case '>=': return value >= threshold;
    case '<=': return value <= threshold;
    case '>': return value > threshold;
    case '<': return value < threshold;
    case '==': return value === threshold;
    default: return false;
  }
}

/**
 * Evaluate a single indicator based on the rules engine.
 */
function evaluateIndicator(id, indicatorData) {
  if (!indicatorData || indicatorData.current === null) {
    return {
      value: null,
      unit: '',
      level: 'unknown',
      direction: 'unknown',
      reason: 'Data missing',
      ruleType: 'none',
      asOf: null,
      freshness: 'stale',
      confidence: 'low',
      legacyStatus: 'unknown'
    };
  }
  
  const current = indicatorData.current;
  const asOfDate = indicatorData.lastObsDate;
  const series = indicatorData.series || [];
  
  const rule = quantificationRules[id] || { type: 'unknown' };
  
  let level = 'normal';
  let color = 'gray';
  let implication = 'unknown';
  let reason = 'No specific rule defined';
  
  const directionData = calculateDirection(series, asOfDate, rule.direction_window || '3m');
  
  if (rule.type === 'official_anchor' || rule.type === 'economic_threshold' || rule.type === 'official_anchor_plus_band') {
    for (const thresh of rule.thresholds) {
      if (evaluateCondition(current, thresh.condition)) {
        level = thresh.level;
        color = thresh.color;
        implication = thresh.implication;
        reason = `Condition met: ${thresh.condition}`;
        break;
      }
    }
  } else if (rule.type === 'expanding_percentile') {
    const pct = calculateExpandingPercentile(series, current, asOfDate);
    if (pct !== null) {
      for (const pThresh of rule.percentiles) {
        if (evaluateCondition(pct, pThresh.condition)) {
          level = pThresh.level;
          color = pThresh.color;
          implication = pThresh.implication;
          reason = `Percentile ${pct.toFixed(1)}% met condition: ${pThresh.condition}`;
          break;
        }
      }
    } else {
      reason = "Insufficient history for percentile";
    }
  }
  
  // Legacy status mapping for backward compatibility
  let legacyStatus = 'green';
  if (color === 'red') legacyStatus = 'bad';
  else if (color === 'orange') legacyStatus = 'bad';
  else if (color === 'yellow') legacyStatus = 'yellow';
  else legacyStatus = 'good';
  
  return {
    value: current,
    unit: '', // Could be derived or added to rules
    level,
    direction: directionData.direction,
    change: directionData.change,
    color,
    implication,
    reason,
    ruleType: rule.type,
    asOf: asOfDate,
    freshness: indicatorData.daysSinceObs < 60 ? 'current' : 'stale',
    confidence: series.length > 30 ? 'high' : 'low',
    legacyStatus
  };
}

module.exports = {
  evaluateIndicator,
  calculateExpandingPercentile
};
