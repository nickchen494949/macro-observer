"""Audit Yardeni sector EPS (chart-read) against the S&P DJI workbook values already in data/sector_eps."""
import csv, statistics as st, collections, math
import openpyxl

def corr(a, b):
    ma, mb = st.mean(a), st.mean(b)
    num = sum((x-ma)*(y-mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x-ma)**2 for x in a) * sum((y-mb)**2 for y in b))
    return num/den if den else float('nan')

# --- Yardeni
wb = openpyxl.load_workbook('scratch/Yardeni_Sector_Operating_EPS.xlsm', data_only=True)
Y, SENS, METH = {}, {}, {}
for r in wb['取值明细'].iter_rows(values_only=True):
    if isinstance(r[0], str) and len(r[0]) == 6 and r[0][4] == 'Q' and isinstance(r[3], (int, float)):
        Y[(r[1], r[0])] = r[3]; SENS[(r[1], r[0])] = r[5]; METH[(r[1], r[0])] = r[4]

# --- S&P DJI (existing)
S, SE = {}, {}
for r in csv.DictReader(open('data/sector_eps/sector_eps_quarterly.csv')):
    if r['index'] == 'S&P 500' and r['basis'] == 'operating':
        (S if r['status'] == 'actual' else SE)[(r['sector'], r['period'])] = float(r['eps'])
for k, v in {k: v for k, v in S.items()}.items(): pass
print('Yardeni n=%d  S&P actual n=%d  S&P estimate n=%d' % (len(Y), len(S), len(SE)))
print('S&P actual operating last:', max(p for _, p in S), ' est range:', min(p for _, p in SE), max(p for _, p in SE))

sectors = sorted({s for s, _ in Y})
print('\n== A. Level agreement vs S&P DJI operating actuals (overlap) ==')
print('%-24s %4s %8s %8s %8s %8s %7s %7s %7s' % ('sector', 'n', 'medAbs%', 'meanAbs%', 'max%', 'medRatio', 'corrLvl', 'corrYoY', 'dirAgr'))
allabs = []
for s in sectors:
    ps = sorted(p for (ss, p) in Y if ss == s and (s, p) in S)
    if not ps: print(s, 'no overlap'); continue
    y = [Y[(s, p)] for p in ps]; b = [S[(s, p)] for p in ps]
    pct = [abs(a/c-1)*100 for a, c in zip(y, b) if c > 0]
    allabs += pct
    ratio = st.median([a/c for a, c in zip(y, b) if c > 0])
    # yoy corr
    idx = {p: i for i, p in enumerate(ps)}
    yo_y, yo_b = [], []
    for p in ps:
        q = '%d%s' % (int(p[:4])-1, p[4:])
        if q in idx and S[(s, q)] > 0 and Y[(s, q)] > 0:
            yo_y.append(Y[(s, p)]/Y[(s, q)]-1); yo_b.append(S[(s, p)]/S[(s, q)]-1)
    # qoq direction agreement
    agr = tot = 0
    for i in range(1, len(ps)):
        dy, db = y[i]-y[i-1], b[i]-b[i-1]
        tot += 1; agr += (dy > 0) == (db > 0)
    print('%-24s %4d %8.2f %8.2f %8.2f %8.3f %7.4f %7.3f %6.0f%%' % (s, len(ps), st.median(pct), st.mean(pct), max(pct), ratio,
          corr(y, b), corr(yo_y, yo_b) if len(yo_y) > 3 else float('nan'), 100*agr/tot))
print('ALL: n=%d  median abs err %.2f%%  mean %.2f%%  p90 %.2f%%  max %.2f%%' % (len(allabs), st.median(allabs), st.mean(allabs),
      sorted(allabs)[int(.9*len(allabs))], max(allabs)))
print('share within 1%%: %.0f%%  within 3%%: %.0f%%  within 5%%: %.0f%%  within 10%%: %.0f%%' % tuple(100*sum(x <= t for x in allabs)/len(allabs) for t in (1, 3, 5, 10)))

print('\n== B. Worst 15 level mismatches ==')
rows = []
for (s, p), v in Y.items():
    if (s, p) in S and S[(s, p)] > 0:
        rows.append((abs(v/S[(s, p)]-1)*100, s, p, v, S[(s, p)], SENS[(s, p)]))
for r in sorted(rows, reverse=True)[:15]:
    print('%6.1f%%  %-24s %s  yardeni=%.3f  sp=%.3f  (2px sens=%.3f)' % r)

print('\n== C. Error vs Yardeni 2px sensitivity (is diff explained by pixel reading?) ==')
inpx = sum(1 for (e, s, p, y, b, sen) in rows if abs(y-b) <= 2*(sen or 0))
print('|diff| <= 2*sens(2px) in %d / %d (%.0f%%)' % (inpx, len(rows), 100*inpx/len(rows)))

print('\n== D. Error by era (mean abs %%) ==')
byyr = collections.defaultdict(list)
for e, s, p, y, b, sen in rows: byyr[p[:4]].append(e)
print(' '.join('%s:%.1f' % (k, st.mean(v)) for k, v in sorted(byyr.items())))

print('\n== E. Latest overlap + S&P estimate comparison (2025Q3 etc.; NOT actuals) ==')
for s in sectors:
    out = []
    for p in ('2025Q2', '2025Q3', '2025Q4', '2026Q1', '2026Q2'):
        y = Y.get((s, p)); b = S.get((s, p)) or SE.get((s, p)); tag = 'A' if (s, p) in S else 'E'
        out.append('%s y=%s sp=%s%s' % (p, '%.2f' % y if y else '-', '%.2f' % b if b else '-', tag if b else ''))
    print('%-24s' % s, ' | '.join(out))

print('\n== F. Internal checks ==')
# smoothness: abs QoQ jumps > 40%
jumps = []
for s in sectors:
    ps = sorted(p for (ss, p) in Y if ss == s)
    for a, c in zip(ps, ps[1:]):
        if Y[(s, a)] > 0 and abs(Y[(s, c)]/Y[(s, a)]-1) > .40: jumps.append((s, a, c, Y[(s, a)], Y[(s, c)]))
print('QoQ jumps >40%%: %d' % len(jumps))
for j in jumps[:12]: print('  ', j)
print('negative/zero values:', sum(1 for v in Y.values() if v <= 0))
print('2026Q2 printed vs 2026Q1 curve (discontinuity risk):')
for s in sectors:
    a, c = Y.get((s, '2026Q1')), Y.get((s, '2026Q2'))
    if a and c: print('  %-24s %.2f -> %.2f (%+.0f%%)' % (s, a, c, (c/a-1)*100))
