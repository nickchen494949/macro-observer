const fs = require('fs');
const path = require('path');

/**
 * Event Attribution Engine
 * Compares market realities against event expectations from the taxonomy.
 */
class EventAttributionEngine {
  constructor() {
    this.taxonomy = {};
    this.loadTaxonomy();
  }

  loadTaxonomy() {
    try {
      const p = path.join(__dirname, '../config/event_taxonomy.json');
      if (fs.existsSync(p)) {
        this.taxonomy = JSON.parse(fs.readFileSync(p, 'utf-8'));
      }
    } catch (e) {
      console.error("Failed to load event taxonomy", e);
    }
  }

  attribute(event, marketContext, isIntraday = false) {
    if (!event || !this.taxonomy[event.type]) {
      return { tier: "No identifiable driver", score: 0, penalty: 0 };
    }

    const rules = this.taxonomy[event.type];
    const signals = marketContext.signals || [];
    
    let score = 0;
    let hasRequired = false;
    let hasContradicting = false;
    let penalty = 0;

    if (rules.requiredSignals && rules.requiredSignals.length > 0) {
      const match = rules.requiredSignals.some(req => signals.includes(req));
      if (match) {
        hasRequired = true;
        score += 5;
      }
    } else {
      hasRequired = true;
    }

    if (rules.supportingSignals) {
      rules.supportingSignals.forEach(sup => {
        if (signals.includes(sup)) score += 2;
      });
    }

    if (rules.optionalSignals) {
      rules.optionalSignals.forEach(opt => {
        if (signals.includes(opt)) score += 1;
      });
    }

    if (rules.contradictingSignals) {
      rules.contradictingSignals.forEach(contra => {
        if (signals.includes(contra)) {
          hasContradicting = true;
          const weight = (rules.penaltyWeights && rules.penaltyWeights[contra]) !== undefined ? rules.penaltyWeights[contra] : 1;
          penalty += weight * 5; 
        }
      });
    }

    const finalScore = score - penalty;
    let tier = "No identifiable driver";

    if (hasContradicting && finalScore < 0) {
      tier = "Rejected by data";
    } else if (finalScore >= 5 && hasRequired) {
      tier = "Probable main driver";
    } else if (finalScore >= 2) {
      tier = "Contributing factor";
    } else if (finalScore > 0) {
      tier = "Plausible but unconfirmed";
    }

    // Apply Daily-data attribution ceiling
    if (!isIntraday) {
      if (tier === "Probable main driver") {
        tier = "Contributing factor";
      }
    }

    return { tier, finalScore, penalty };
  }
}

module.exports = EventAttributionEngine;
