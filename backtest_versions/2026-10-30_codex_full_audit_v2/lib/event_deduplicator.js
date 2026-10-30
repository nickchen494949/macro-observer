/**
 * Event Deduplicator
 * Deduplicates identical events across multiple sources (Headline echo control)
 */
class EventDeduplicator {
  constructor(timeWindowMs = 1000 * 60 * 60) { // Default 1 hour clustering window
    this.timeWindowMs = timeWindowMs;
  }

  deduplicate(events) {
    if (!events || !Array.isArray(events)) return [];
    
    const sorted = [...events].sort((a, b) => a.timestamp - b.timestamp);
    const clusters = [];
    
    for (const event of sorted) {
      let foundCluster = false;
      for (const cluster of clusters) {
        const primary = cluster[0];
        if (event.type === primary.type && Math.abs(event.timestamp - primary.timestamp) <= this.timeWindowMs) {
          cluster.push(event);
          foundCluster = true;
          break;
        }
      }
      if (!foundCluster) {
        clusters.push([event]);
      }
    }
    
    return clusters.map(cluster => {
      const primary = cluster[0];
      return {
        ...primary,
        relatedSources: cluster.map(e => e.source),
        echoCount: cluster.length
      };
    });
  }
}

module.exports = EventDeduplicator;
