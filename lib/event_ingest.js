/**
 * Event Ingest Engine
 * Phase 4.4: Event Data Foundation
 * Ensure failure isolation: Catch errors and output status: "unavailable".
 */
class EventIngest {
  constructor() {
    this.events = [];
  }
  
  ingest(rawData) {
    try {
      if (!rawData) {
        throw new Error("No data provided");
      }
      if (!Array.isArray(rawData)) {
        throw new Error("Invalid raw data format");
      }
      this.events = rawData.map(this.parseEvent).filter(e => e !== null);
      return { status: "ok", data: this.events };
    } catch (error) {
      return { status: "unavailable", reason: "暂无足够事件数据，不强行归因", error: error.message };
    }
  }

  parseEvent(rawEvent) {
    if (!rawEvent.id || !rawEvent.timestamp) return null;
    return {
      id: rawEvent.id,
      timestamp: new Date(rawEvent.timestamp).getTime(),
      type: rawEvent.type || "UNKNOWN",
      source: rawEvent.source || "UNKNOWN",
      headline: rawEvent.headline || "",
      data: rawEvent.data || {}
    };
  }
}

module.exports = EventIngest;
