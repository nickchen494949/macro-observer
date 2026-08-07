// lib/confidence_engine.js

function evaluateConfidence(indicatorData, diagnosticData) {
    // indicatorConfidence: evaluates source/freshness quality
    let indicatorConfidence = 'high';
    if (indicatorData.freshness === 'stale') {
        indicatorConfidence = 'low';
    } else if (indicatorData.sourceQuality === 'unreliable') {
        indicatorConfidence = 'low';
    }

    // diagnosticConfidence: evaluates macro conflict/agreement (Critical Variable Overrides)
    let diagnosticConfidence = 'high';
    if (diagnosticData.missingCriticalVariables) {
        diagnosticConfidence = 'low';
    } else if (diagnosticData.macroConflict) {
        diagnosticConfidence = 'medium';
    }

    return {
        indicatorConfidence,
        diagnosticConfidence
    };
}

module.exports = {
    evaluateConfidence
};
