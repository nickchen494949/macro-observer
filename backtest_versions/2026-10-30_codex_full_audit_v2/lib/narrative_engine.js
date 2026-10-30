// lib/narrative_engine.js

function generateNarrative(context) {
    // Strict string templates (no LLMs)
    const templates = {
        growth_strong: "Economic growth remains robust.",
        growth_weak: "Economic growth is slowing down.",
        inflation_high: "Inflation pressures persist.",
        inflation_low: "Inflation is cooling.",
        default: "Macro conditions are mixed."
    };

    let narrativeParts = [];

    if (context.growth === 'strong') {
        narrativeParts.push(templates.growth_strong);
    } else if (context.growth === 'weak') {
        narrativeParts.push(templates.growth_weak);
    }

    if (context.inflation === 'high') {
        narrativeParts.push(templates.inflation_high);
    } else if (context.inflation === 'low') {
        narrativeParts.push(templates.inflation_low);
    }

    if (narrativeParts.length === 0) {
        return templates.default;
    }

    return narrativeParts.join(" ");
}

module.exports = {
    generateNarrative
};
