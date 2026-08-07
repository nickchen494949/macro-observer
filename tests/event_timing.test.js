const EventTimelineEngine = require('../lib/event_timeline_engine');

describe('Event Timeline Engine', () => {
  const engine = new EventTimelineEngine(86400000); // 1 day window

  it('enforces temporal precedence', () => {
    const event = { timestamp: 10000 };
    const marketMoveValid = { timestamp: 20000 };
    const marketMoveTooEarly = { timestamp: 5000 };
    const marketMoveTooLate = { timestamp: 10000 + 86400000 + 1000 };

    expect(engine.validatePrecedence(event, marketMoveValid)).toBe(true);
    expect(engine.validatePrecedence(event, marketMoveTooEarly)).toBe(false);
    expect(engine.validatePrecedence(event, marketMoveTooLate)).toBe(false);
  });
});
