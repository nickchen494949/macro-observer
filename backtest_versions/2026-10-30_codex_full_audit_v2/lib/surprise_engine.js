/**
 * Surprise Engine
 * Calculates Actual vs Expected Consensus -> Surprise
 */
class SurpriseEngine {
  calculateSurprise(eventData) {
    if (!eventData || typeof eventData.actual === 'undefined' || typeof eventData.consensus === 'undefined') {
      return null;
    }
    
    const { actual, consensus } = eventData;
    
    const surpriseValue = actual - consensus;
    let surpriseDirection = "inline";
    if (surpriseValue > 0) surpriseDirection = "positive";
    else if (surpriseValue < 0) surpriseDirection = "negative";
    
    let surpriseMagnitude = 0;
    if (consensus !== 0) {
      surpriseMagnitude = Math.abs(surpriseValue / consensus);
    }
    
    return {
      surpriseValue,
      surpriseDirection,
      surpriseMagnitude
    };
  }
}

module.exports = SurpriseEngine;
