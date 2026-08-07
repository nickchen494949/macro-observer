import re

with open('backtest/run_fred_sensitivity.js', 'r') as f:
    content = f.read()

# Replace riskParityProxy with riskParity
content = content.replace("riskParityProxy", "riskParity")

# Add actual PIT selection logging!
old_compare = """    const bRP = JSON.stringify(b.modules?.riskParity || {});
    const tRP = JSON.stringify(t.modules?.riskParity || {});
    if (bRP !== tRP) riskParityNumDiffs++;"""

new_compare = """    const bRP = JSON.stringify(b.modules?.riskParity || {});
    const tRP = JSON.stringify(t.modules?.riskParity || {});
    if (bRP !== tRP) riskParityNumDiffs++;
    
    // Also track status changes
    if (b.modules?.riskParity?.status !== t.modules?.riskParity?.status) statusDiffs++;
    if (b.modules?.riskParity?.allocationDirection !== t.modules?.riskParity?.allocationDirection) directionDiffs++;
"""
content = content.replace(old_compare, new_compare)

with open('backtest/run_fred_sensitivity.js', 'w') as f:
    f.write(content)
