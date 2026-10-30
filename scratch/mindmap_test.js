const { chromium } = require('/Users/happygolucky/projects/宏观观察器/node_modules/playwright');
(async () => {
  const b = await chromium.launch({ headless: true });
  const p = await b.newPage({ viewport: { width: 1500, height: 900 } });
  const errs = [];
  p.on('pageerror', e => errs.push('pageerror: ' + e.message));
  p.on('dialog', d => d.accept('13'));
  await p.goto('file:///Users/happygolucky/Desktop/系统图app/index.html', { waitUntil: 'load' });
  await p.waitForTimeout(4000);
  const measure = () => p.evaluate(() => [...document.querySelectorAll('#node-layer .node')]
    .filter(e => !e.classList.contains('group-node') && !e.classList.contains('label-node') && !e.classList.contains('arrow-label-anchor'))
    .map(e => { const l = e.querySelector('.label'); const fs = parseFloat(getComputedStyle(e).fontSize);
      return { t: (l.innerText || '').slice(0, 14), fs, w: e.offsetWidth, lines: Math.round(l.getBoundingClientRect().height / (fs * 1.2)) }; }));
  const before = await measure();
  console.log('nodes', before.length, 'multi-line:', before.filter(x => x.lines > 1).map(x => x.t + '/' + x.lines));
  console.log('font sizes:', [...new Set(before.map(x => x.fs))].join(','));

  // Shift+Enter test on first regular node
  const first = await p.$('#node-layer .node:not(.group-node):not(.label-node):not(.arrow-label-anchor) .label');
  if (first) {
    await first.dblclick();
    await p.waitForTimeout(300);
    await p.keyboard.press('Control+A'); await p.keyboard.press('Meta+A');
    await p.keyboard.type('第一行');
    await p.keyboard.press('Shift+Enter');
    await p.keyboard.type('第二行');
    const mid = await first.evaluate(l => ({ edit: l.getAttribute('contenteditable'), txt: JSON.stringify(l.innerText) }));
    await p.keyboard.press('Enter');
    await p.waitForTimeout(300);
    const after = await first.evaluate(l => { const fs = parseFloat(getComputedStyle(l).fontSize); return { txt: JSON.stringify(l.innerText), lines: Math.round(l.getBoundingClientRect().height / (fs * 1.2)) }; });
    console.log('shift+enter:', JSON.stringify(mid), '->', JSON.stringify(after));
  }
  // Long single-line label stays one line
  const long = await p.evaluate(() => { const n = state.nodes.find(n => !n.isGroup && !n.isLabel && !n.isArrowLabel); if (!n) return null;
    n.label = '这是一个非常非常长的节点名称用来测试是否会自动换行的情况'; n.manualSize = false; n.nw = 80; rerenderNode(n);
    const el = document.querySelector(`#node-layer [data-id="${n.id}"]`); const l = el.querySelector('.label'); const fs = parseFloat(getComputedStyle(el).fontSize);
    return { lines: Math.round(l.getBoundingClientRect().height / (fs * 1.2)), w: el.offsetWidth }; });
  console.log('long label (legacy nw=80):', JSON.stringify(long));

  // Unify font
  await p.click('#btn-unify-font');
  await p.waitForTimeout(300);
  const after2 = await measure();
  console.log('after unify font sizes:', [...new Set(after2.map(x => x.fs))].join(','), '| status:', await p.textContent('#status-text'));
  console.log('errors:', errs.join('\n') || 'none');
  await p.screenshot({ path: '/Users/happygolucky/projects/宏观观察器/scratch/mindmap_test.png' });
  await b.close();
})();
