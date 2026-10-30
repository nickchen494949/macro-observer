/**
 * Event Timeline Engine
 * Enforces temporal precedence: publicSignalAt <= marketMoveStartedAt <= publicSignalAt + attributionWindow
 */
class EventTimelineEngine {
  constructor(defaultAttributionWindowMs = 1000 * 60 * 60 * 24 * 2) { // Default 2 days
    this.defaultAttributionWindowMs = defaultAttributionWindowMs;
  }

  validatePrecedence(event, marketMove) {
    if (!event || !marketMove) return false;
    
    const publicSignalAt = event.timestamp;
    const marketMoveStartedAt = marketMove.timestamp;
    const window = event.attributionWindowMs || this.defaultAttributionWindowMs;

    return publicSignalAt <= marketMoveStartedAt && marketMoveStartedAt <= (publicSignalAt + window);
  }

  filterValidAttributions(events, marketMoves) {
    const validLinks = [];
    
    for (const move of marketMoves) {
      for (const event of events) {
        if (this.validatePrecedence(event, move)) {
          validLinks.push({
            event,
            marketMove: move,
            lagMs: move.timestamp - event.timestamp
          });
        }
      }
    }
    
    return validLinks;
  }
}

module.exports = EventTimelineEngine;
