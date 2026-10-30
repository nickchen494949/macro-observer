/**
 * legacy_adapter.js
 * 
 * Takes the V2 diagnostic engine output and formats it 
 * to strictly match the legacy macro_engine.js output schema.
 * 
 * Legacy schema per cluster:
 * {
 *   status: 'red' | 'yellow' | 'green' | 'unknown',
 *   score: float,
 *   value: float,
 *   coverage: int (0-100),
 *   confidence: int (0-100),
 *   freshnessDays: int,
 *   obsDate: string (YYYY-MM-DD),
 *   evidence: string[],
 *   counterEvidence: string[],
 *   missing: string[]
 * }
 */

function adaptModuleToLegacy(moduleName, diagResult, rawV2Output) {
  // Translate the V2 output (Pressure -> Transmission -> Damage) 
  // into the old flattened cluster view for dual-track testing.
  
  // This adapter provides a generic translation. 
  // The UI currently expects specific keys like 'layoffs', 'hours', 'income', etc.
  // Wait, if the UI expects specific keys, we need to map our V2 modules back to the 22 old clusters.
  // For the dual-track run, we will output BOTH under the API so the frontend can still use the old one,
  // or we can just replace the API response fields when USE_RULE_ENGINE_V2 is true.
  
  // Actually, the most robust dual track for Phase 2 is to have the API return:
  // {
  //   diagnostics: { ... legacy ... },
  //   v2: {
  //      classified: { ... rule_engine output ... },
  //      diagnostics: { ... diagnostic_engine output ... }
  //   }
  // }
  // This way the frontend doesn't break at all, and we can start building the new UI components alongside the old ones.
  return {}; 
}

module.exports = {
  adaptModuleToLegacy
};
