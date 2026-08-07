const EventDeduplicator = require('../lib/event_deduplicator');

describe('Event Deduplicator', () => {
  it('groups duplicate events by type within time window', () => {
    const deduplicator = new EventDeduplicator(3600000); // 1 hour
    const events = [
      { id: '1', type: 'CPI_RELEASE', timestamp: 1000000, source: 'Reuters' },
      { id: '2', type: 'CPI_RELEASE', timestamp: 1001000, source: 'Bloomberg' },
      { id: '3', type: 'NFP_RELEASE', timestamp: 1000000, source: 'WSJ' },
      { id: '4', type: 'CPI_RELEASE', timestamp: 5000000, source: 'CNBC' } // outside window
    ];
    
    const result = deduplicator.deduplicate(events);
    
    expect(result.length).toBe(3); // 2 CPI clusters, 1 NFP cluster
    
    const cpiPrimary = result.find(e => e.id === '1');
    expect(cpiPrimary.echoCount).toBe(2);
    expect(cpiPrimary.relatedSources).toEqual(['Reuters', 'Bloomberg']);
  });
});
