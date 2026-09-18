'use strict';

const path = require('path');
const { spawnSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');

const dl = spawnSync(process.execPath, [path.join(ROOT, 'download_yahoo.js')], {
  cwd: ROOT,
  encoding: 'utf8',
  timeout: 240000,
  maxBuffer: 4 * 1024 * 1024,
});

process.stdout.write(dl.stdout || '');
process.stderr.write(dl.stderr || '');
if (dl.status !== 0) {
  console.error(`download_yahoo.js failed with exit ${dl.status}`);
  process.exit(dl.status || 1);
}

const uid = process.getuid ? process.getuid() : Number(process.env.UID);
const restart = spawnSync('launchctl', ['kickstart', '-k', `gui/${uid}/com.macro-observer.dashboard`], {
  cwd: ROOT,
  encoding: 'utf8',
  timeout: 30000,
});

if (restart.status !== 0) {
  process.stderr.write(restart.stderr || '');
  console.error('Yahoo refresh succeeded, but dashboard restart failed.');
  process.exit(restart.status || 1);
}

console.log('PASS: Yahoo canary/CTA data refreshed and dashboard restart requested.');
