/**
 * Action Context Engine
 * Translates macro environment for side-by-side display with QQQ Strategy.
 * This does NOT alter the legacy QQQ strategy logic, but acts as an environmental classifier.
 *
 * CRITICAL: Fail-closed behavior — incomplete diagnostics → "unknown", never "supportive".
 * 
 * Messages describe observed conditions only — no speculative predictions about
 * future volatility or returns, because the engine has no forecasting capability.
 */

function generateActionContext(macroDiagnosis) {
  const { maxRiskSeverity, hasDamage, hasContradiction, diagnosticCoverage } = macroDiagnosis;

  // Fail-closed: if core diagnostics are incomplete, refuse to classify as supportive
  if (diagnosticCoverage != null && diagnosticCoverage < 1.0) {
    return {
      environment: 'unknown',
      message: `Insufficient diagnostic coverage (${Math.round(diagnosticCoverage * 100)}%). Cannot determine macro environment.`,
      timestamp: new Date().toISOString()
    };
  }

  let environment = 'neutral';
  let message = 'No elevated macro pressure or damage detected across diagnostic modules.';

  if (maxRiskSeverity >= 3 && hasDamage) {
    environment = 'systemic_stress';
    message = 'Severe pressure with confirmed damage cascade in growth or financial system. Systemic risk is elevated.';
  } else if (maxRiskSeverity >= 3) {
    environment = 'adverse';
    message = 'Elevated structural pressure (real yields, valuations, or long-end financing) without confirmed damage to credit, growth, or market functioning.';
  } else if (maxRiskSeverity >= 2) {
    environment = 'adverse';
    message = 'Elevated macro headwinds detected across one or more diagnostic modules, but realized damage remains unconfirmed.';
  } else if (maxRiskSeverity <= 1 && !hasContradiction) {
    environment = 'supportive';
    message = 'No significant macro pressure detected. Diagnostic modules show low risk across growth, inflation, financial system, and market conditions.';
  }

  return {
    environment,
    structuralPressure: maxRiskSeverity >= 2 ? 'elevated' : 'low',
    marketTrend: 'supportive',
    growthDamage: hasDamage ? 'confirmed' : 'not_confirmed',
    creditDamage: hasDamage ? 'confirmed' : 'not_confirmed',
    marketFunctioningDamage: 'unknown',
    systemicStress: hasDamage ? 'confirmed' : 'not_confirmed',
    confidence: diagnosticCoverage > 0.8 ? 'medium' : 'low',
    message,
    timestamp: new Date().toISOString()
  };
}

module.exports = {
  generateActionContext
};
