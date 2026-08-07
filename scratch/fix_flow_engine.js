const fs = require('fs');
let code = fs.readFileSync('lib/flow_engine.js', 'utf8');

// 1. Rename riskParityProxy to riskParity
code = code.replace(/riskParityProxy/g, 'riskParity');

// 2. Fix NaNpp bug in timeline string (though we'll remove it, it's good to fix)
code = code.replace(/allocationChange5d/g, 'equityAllocationChange5d');

// 3. Remove flowTimeline string formatting and create timelinePressures
code = code.replace(/const flowTimeline = \{[\s\S]*?(?=\/\/ 7\. Summary)/, `
  const timelinePressures = {
    retrospectiveSameDay: { status: 'ok', direction: 'none', mechanisms: [], confidence: 'low' },
    ongoing1To5Days: { status: 'ok', direction: 'none', mechanisms: [], confidence: 'low' },
    recent5To20Days: { status: 'ok', direction: 'none', mechanisms: [], confidence: 'low' },
    conditionalFuture: { status: 'ok', direction: 'none', mechanisms: [], confidence: 'low' }
  };

  if (leveragedEtf.status === 'ok') {
    timelinePressures.retrospectiveSameDay.mechanisms.push('leveragedEtf');
    timelinePressures.retrospectiveSameDay.direction = leveragedEtf.aggregateDirection;
    timelinePressures.retrospectiveSameDay.confidence = 'medium';
  } else {
    timelinePressures.retrospectiveSameDay.status = leveragedEtf.status === 'insufficient_data' ? 'partial' : 'error';
  }

  const ongoingMechs = [];
  let ongoingBuys = 0;
  let ongoingSells = 0;
  
  if (volControl.status === 'ok') {
    ongoingMechs.push('volControl');
    if (volControl.flowPressure === 'selling') ongoingSells++;
    else if (volControl.flowPressure === 'buying') ongoingBuys++;
  }
  if (ctaTrend.status === 'ok') {
    ongoingMechs.push('ctaTrend');
    if (ctaTrend.flowPressure === 'selling') ongoingSells++;
    else if (ctaTrend.flowPressure === 'buying') ongoingBuys++;
  }
  
  timelinePressures.ongoing1To5Days.mechanisms = ongoingMechs;
  if (ongoingBuys > 0 && ongoingSells > 0) timelinePressures.ongoing1To5Days.direction = 'conflicting';
  else if (ongoingBuys > 0) timelinePressures.ongoing1To5Days.direction = 'buy';
  else if (ongoingSells > 0) timelinePressures.ongoing1To5Days.direction = 'sell';
  
  if (volControl.status !== 'ok' || ctaTrend.status !== 'ok') {
    timelinePressures.ongoing1To5Days.status = 'partial';
  }

  if (riskParity.status === 'ok') {
    if (riskParity.allocationDirection && riskParity.allocationDirection !== 'stable') {
      timelinePressures.recent5To20Days.mechanisms.push('riskParity');
      timelinePressures.recent5To20Days.direction = riskParity.allocationDirection;
      timelinePressures.recent5To20Days.confidence = 'medium';
    }
  } else {
    timelinePressures.recent5To20Days.status = 'partial';
  }

  if (stressConditions.status === 'ok' || stressConditions.status === 'calm' || stressConditions.status === 'watch' || stressConditions.status === 'elevated' || stressConditions.status === 'stress' || stressConditions.status === 'crisis') {
    timelinePressures.conditionalFuture.mechanisms.push('stressConditions');
    if (stressConditions.stressScore >= 50) {
      timelinePressures.conditionalFuture.direction = 'selling';
    }
  } else {
    timelinePressures.conditionalFuture.status = 'partial';
  }

  // To maintain schema compatibility temporarily, we keep an empty flowTimeline object
  const flowTimeline = {};

`);

code = code.replace(/summary,\s*volControl,\s*leveragedEtf,\s*ctaTrend,\s*riskParity,\s*pensionRebalance,\s*stressConditions/, `
    summary,
    modules: {
      volControl,
      leveragedEtf,
      ctaTrend,
      riskParity,
      pensionRebalance,
      stressConditions
    }
`);

// Add timelinePressures to summary
code = code.replace(/const summary = \{/, `const summary = { timelinePressures,`);
code = code.replace(/schemaVersion: 1/, `schemaVersion: 2`);

fs.writeFileSync('lib/flow_engine.js', code);
