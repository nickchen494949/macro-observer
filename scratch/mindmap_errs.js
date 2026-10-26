const { chromium } = require('/Users/happygolucky/projects/宏观观察器/node_modules/playwright');
(async () => {
  for (const url of ['file:///Users/happygolucky/projects/宏观观察器/scratch/mindmap_orig/index.html', 'file:///Users/happygolucky/Desktop/系统图app/index.html']) {
    const b = await chromium.launch({ headless: true });
    const p = await b.newPage();
    const errs = [];
    p.on('pageerror', e => errs.push(e.message + ' @ ' + (e.stack || '').split('\n')[1]));
    await p.goto(url, { waitUntil: 'load' });
    await p.waitForTimeout(3000);
    console.log(url.includes('mindmap_orig') ? 'ORIGINAL:' : 'MODIFIED:', errs.length ? errs.join(' | ') : 'no errors');
    await b.close();
  }
})();
