const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

(async () => {
  const repo = path.resolve(__dirname, '..');
  const outDir = path.join(repo, 'remote_results/captures');
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage({ viewport: { width: 1000, height: 720 }, deviceScaleFactor: 1 });
  await page.goto('http://localhost:8765', { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(1200);

  async function shot(text, name, h) {
    const loc = page.getByText(text, { exact: false }).first();
    await loc.scrollIntoViewIfNeeded();
    await page.waitForTimeout(250);
    const b = await loc.boundingBox();
    if (!b) throw new Error('missing ' + text);
    const p = path.join(outDir, name);
    await page.screenshot({path:p,type:'jpeg',quality:16,clip:{x:0,y:Math.max(0,b.y-45),width:680,height:h}});
    return p;
  }
  await shot('股票板块 Stock Sectors','stocks_chat_proof.jpg',300);
  await shot('大宗商品期货 Commodities','commodities_chat_proof.jpg',240);
  await browser.close();

  const rels = ['remote_results/captures/stocks_chat_proof.jpg','remote_results/captures/commodities_chat_proof.jpg'];
  execFileSync('git',['add',...rels],{cwd:repo,stdio:'inherit'});
  const staged=execFileSync('git',['diff','--cached','--name-only'],{cwd:repo,encoding:'utf8'}).trim();
  if(staged){
    execFileSync('git',['commit','-m','Add compact live dashboard proof images'],{cwd:repo,stdio:'inherit'});
    execFileSync('git',['push','origin','agent/phase4-composite-validation'],{cwd:repo,stdio:'inherit'});
  }
  console.log(execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8'}).trim());
})().catch(e=>{console.error(e.stack||e.message);process.exit(1);});
