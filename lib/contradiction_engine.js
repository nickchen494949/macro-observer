// lib/contradiction_engine.js

function identifyContradictions(macroData) {
    const contradictions = [];

    // Output-Labor Divergence
    if (macroData.output === 'strong' && macroData.labor === 'weak') {
        contradictions.push({
            name: "Output-Labor Divergence",
            description: "Economic output is strong while labor market is weak."
        });
    }

    // Broad Ease-Long Rate Tightness
    if (macroData.financialConditions === 'easy' && macroData.longRates === 'tight') {
        contradictions.push({
            name: "Broad Ease-Long Rate Tightness",
            description: "Broad financial conditions are easy but long-term rates indicate tightness."
        });
    }

    // Vulnerability-Complacency Gap
    if (macroData.vulnerability === 'high' && macroData.marketComplacency === 'high') {
        contradictions.push({
            name: "Vulnerability-Complacency Gap",
            description: "High systemic vulnerability met with high market complacency."
        });
    }

    return contradictions;
}

module.exports = {
    identifyContradictions
};
