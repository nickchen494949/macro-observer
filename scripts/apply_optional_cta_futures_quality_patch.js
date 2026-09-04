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
if (src.includes('qualityRelevantExcludedModules')) {
  console.log('Optional CTA Futures quality semantics already patched.');
  process.exit(0);
}

const oldQuality = `  const excludedModules = [];
  if (volControl.status !== 'ok') excludedModules.push('volControl');
  if (leveragedEtf.status !== 'ok') excludedModules.push('leveragedEtf');
  if (ctaFuturesProxy.status !== 'ok') excludedModules.push('ctaFuturesProxy');
  if (ctaEtfProxy.status !== 'ok') excludedModules.push('ctaEtfProxy');
  if (riskParityProxy.status !== 'ok') excludedModules.push('riskParityProxy');
  if (stressConditions.status === 'insufficient_data' || stressConditions.status === 'series_too_stale') excludedModules.push('stressConditions');

  let snapshotQuality = excludedModules.length > 0 ? 'partial' : 'complete';`;

const newQuality = `  const excludedModules = [];
  const qualityRelevantExcludedModules = [];
  const excludeModule = (name, affectsQuality = true) => {
    excludedModules.push(name);
    if (affectsQuality) qualityRelevantExcludedModules.push(name);
  };
  if (volControl.status !== 'ok') excludeModule('volControl');
  if (leveragedEtf.status !== 'ok') excludeModule('leveragedEtf');
  // CTA Futures is research/descriptive-only. Keep its unavailability visible,
  // but do not downgrade the quality of the formal production snapshot.
  if (ctaFuturesProxy.status !== 'ok') excludeModule('ctaFuturesProxy', false);
  if (ctaEtfProxy.status !== 'ok') excludeModule('ctaEtfProxy');
  if (riskParityProxy.status !== 'ok') excludeModule('riskParityProxy');
  if (stressConditions.status === 'insufficient_data' || stressConditions.status === 'series_too_stale') excludeModule('stressConditions');

  let snapshotQuality = qualityRelevantExcludedModules.length > 0 ? 'partial' : 'complete';`;

if (!src.includes(oldQuality)) throw new Error('Expected snapshot-quality block not found exactly; refusing patch');
src = src.replace(oldQuality, newQuality);

const oldTiming = `    signalAvailableAt: [
      volControl.signalAvailableAt, 
      leveragedEtf.signalAvailableAt, 
      ctaFuturesProxy.signalAvailableAt, 
      ctaEtfProxy.signalAvailableAt, 
      riskParityProxy.signalAvailableAt, 
      pensionRebalance.signalAvailableAt
    ].reduce((a, b) => (a > b ? a : b)),
    firstTradableSession: [
      volControl.firstTradableSession, 
      leveragedEtf.firstTradableSession, 
      ctaFuturesProxy.firstTradableSession, 
      ctaEtfProxy.firstTradableSession, 
      riskParityProxy.firstTradableSession, 
      pensionRebalance.firstTradableSession
    ].reduce((a, b) => (a > b ? a : b)),`;

const newTiming = `    signalAvailableAt: [
      volControl.signalAvailableAt, 
      leveragedEtf.signalAvailableAt, 
      ctaEtfProxy.signalAvailableAt, 
      riskParityProxy.signalAvailableAt, 
      pensionRebalance.signalAvailableAt
    ].filter(Boolean).reduce((a, b) => (a > b ? a : b), null),
    firstTradableSession: [
      volControl.firstTradableSession, 
      leveragedEtf.firstTradableSession, 
      ctaEtfProxy.firstTradableSession, 
      riskParityProxy.firstTradableSession, 
      pensionRebalance.firstTradableSession
    ].filter(Boolean).reduce((a, b) => (a > b ? a : b), null),`;

if (!src.includes(oldTiming)) throw new Error('Expected formal timing block not found exactly; refusing patch');
src = src.replace(oldTiming, newTiming);

fs.writeFileSync(FILE, src);
run(process.execPath, ['--check', FILE]);
run('git', ['add', '--', 'lib/flow_engine.js']);
run('git', ['commit', '-m', 'Keep research CTA Futures outside snapshot quality', '--', 'lib/flow_engine.js']);
run('git', ['push', 'origin', `HEAD:${BRANCH}`], 60000);

const uid = process.getuid ? process.getuid() : Number(process.env.UID);
spawnSync('launchctl', ['kickstart', '-k', `gui/${uid}/com.macro-observer.dashboard`], { cwd: ROOT, encoding: 'utf8', timeout: 30000 });
console.log('PASS: CTA Futures remains visible but no longer downgrades formal snapshot quality/timing.');
