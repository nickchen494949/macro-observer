const SurpriseEngine = require('../lib/surprise_engine');

describe('Surprise Engine', () => {
  const engine = new SurpriseEngine();

  it('calculates positive surprise', () => {
    const result = engine.calculateSurprise({ actual: 5.5, consensus: 5.0 });
    expect(result.surpriseValue).toBeCloseTo(0.5);
    expect(result.surpriseDirection).toBe('positive');
    expect(result.surpriseMagnitude).toBeCloseTo(0.1);
  });

  it('calculates negative surprise', () => {
    const result = engine.calculateSurprise({ actual: 4.8, consensus: 5.0 });
    expect(result.surpriseValue).toBeCloseTo(-0.2);
    expect(result.surpriseDirection).toBe('negative');
    expect(result.surpriseMagnitude).toBeCloseTo(0.04);
  });

  it('calculates inline surprise', () => {
    const result = engine.calculateSurprise({ actual: 5.0, consensus: 5.0 });
    expect(result.surpriseValue).toBe(0);
    expect(result.surpriseDirection).toBe('inline');
    expect(result.surpriseMagnitude).toBe(0);
  });

  it('handles missing data', () => {
    const result = engine.calculateSurprise({ actual: 5.0 });
    expect(result).toBeNull();
  });
});
