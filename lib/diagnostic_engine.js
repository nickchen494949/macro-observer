// lib/diagnostic_engine.js

/**
 * Enforces Non-compensatory aggregation: Pressure, Transmission, and Damage must NEVER be averaged.
 */
function evaluateDiagnostics(pressureState, transmissionState, damageState) {
    const riskSeverityMap = {
        'high': 3,
        'medium': 2,
        'low': 1,
        'extreme': 4,
        'normal': 0,
        'red': 3,
        'yellow': 2,
        'green': 1
    };

    const getRiskSeverity = (state) => {
        if (!state) return 0;
        if (typeof state === 'string') return riskSeverityMap[state.toLowerCase()] || 0;
        if (state.level && state.level.extremity !== undefined) return state.level.extremity;
        return 0;
    };

    const pressureSeverity = getRiskSeverity(pressureState);
    const transmissionSeverity = getRiskSeverity(transmissionState);
    const damageSeverity = getRiskSeverity(damageState);

    // Strict Non-compensatory output:
    return {
        pressure: {
            raw: pressureState,
            riskSeverity: pressureSeverity
        },
        transmission: {
            raw: transmissionState,
            riskSeverity: transmissionSeverity
        },
        damage: {
            raw: damageState,
            riskSeverity: damageSeverity
        },
        // We do NOT provide an 'average' score.
        // We provide a max riskSeverity or just the individual components.
        maxRiskSeverity: Math.max(pressureSeverity, transmissionSeverity, damageSeverity),
        isCompensated: false // explicit flag to show no averaging occurred
    };
}

module.exports = {
    evaluateDiagnostics
};
