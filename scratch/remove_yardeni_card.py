import re
p = 'index.html'
s = open(p, encoding='utf-8').read()
a = s.index('  <!-- HIDDEN until complete data found: remove display:none to restore -->\n  <section class="card" id="yardeniEpsSection"')
b = s.index('  </section>\n', a) + len('  </section>\n')
removed = s[a:b]
assert 'yardeniEpsSection' in removed and removed.count('<section') == 1
s = s[:a] + s[b:].lstrip('\n')
open(p, 'w', encoding='utf-8').write(s)
print('removed', len(removed), 'chars')
