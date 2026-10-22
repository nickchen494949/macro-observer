p = 'server.js'
s = open(p, encoding='utf-8').read()
a = s.index('// ============================================\n// PRE-MARKET SNAPSHOT (manual button only')
b = s.index('// ============================================\n// METRICS CALCULATION')
new = open('scratch/live_block.js', encoding='utf-8').read()
s = s[:a] + new + '\n' + s[b:]

# remove manual refresh endpoint (fully automatic now)
a = s.index("  } else if (p === '/api/premarket/refresh') {")
b = s.index("  } else if (p === '/api/news') {", a)
s = s[:a] + s[b:]
open(p, 'w', encoding='utf-8').write(s)
print('ok')
