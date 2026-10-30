'use strict';

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const FILE = path.join(ROOT, 'lib', 'flow_engine.js');
const BRANCH = process.env.MACRO_BRANCH || 'agent/phase4-composite-validation';

function run(exe, args, timeout = 60000) {
  const r = spawnSync(exe, args, { cwd: ROOT, encoding: 'utf8', timeout });
  if (r.status !== 0) throw new Error(`${exe} ${args.join(' ')} failed\n${r.stdout || ''}\n${r.stderr || ''}`);
  return (r.stdout || '').trim();
}

let src = fs.readFileSync(FILE, 'utf8');
if (src.includes("dominantRegime === 'no_dominant_flow' ? '无明显主导资金流方向'")) {
  console.log('Summary narrative mapping already patched.');
  process.exit(0);
}

const oldText = "      zh: `代理模型识别${activeFlowMechanismCount}个活跃的前瞻资金流机制和${activeRotationMechanismCount}个近期轮动机制，整体资金压力${dominantRegime === 'conflicting' ? '互相冲突' : '偏向' + (dominantRegime === 'procyclical_buy' ? '买入' : '卖出')}。`";
const newText = "      zh: `代理模型识别${activeFlowMechanismCount}个活跃的前瞻资金流机制和${activeRotationMechanismCount}个近期轮动机制，${dominantRegime === 'conflicting' ? '资金流方向互相冲突' : dominantRegime === 'procyclical_buy' ? '整体资金压力偏向买入' : dominantRegime === 'procyclical_sell' ? '整体资金压力偏向卖出' : dominantRegime === 'no_dominant_flow' ? '无明显主导资金流方向' : '资金流方向未定'}。`";

if (!src.includes(oldText)) throw new Error('Expected Chinese summary narrative line not found exactly; refusing patch');
src = src.replace(oldText, newText);
fs.writeFileSync(FILE, src);
run(process.execPath, ['--check', FILE]);
run('git', ['add', '--', 'lib/flow_engine.js']);
run('git', ['commit', '-m', 'Fix no-dominant-flow Chinese narrative', '--', 'lib/flow_engine.js']);
run('git', ['push', 'origin', `HEAD:${BRANCH}`], 60000);

const uid = process.getuid ? process.getuid() : Number(process.env.UID);
spawnSync('launchctl', ['kickstart', '-k', `gui/${uid}/com.macro-observer.dashboard`], { cwd: ROOT, encoding: 'utf8', timeout: 30000 });
console.log('PASS: Chinese summary narrative now maps no_dominant_flow correctly.');
