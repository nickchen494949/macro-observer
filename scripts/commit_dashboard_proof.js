const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const repo = path.resolve(__dirname, '..');
const files = [
  'remote_results/captures/stocks_recovered.jpg',
  'remote_results/captures/commodities_recovered.jpg'
];
for (const rel of files) {
  if (!fs.existsSync(path.join(repo, rel))) throw new Error(`missing ${rel}`);
}
execFileSync('git', ['add', ...files], { cwd: repo, stdio: 'inherit' });
const staged = execFileSync('git', ['diff', '--cached', '--name-only'], { cwd: repo, encoding: 'utf8' }).trim();
if (staged) {
  execFileSync('git', ['commit', '-m', 'Add live dashboard recovery proof screenshots'], { cwd: repo, stdio: 'inherit' });
  execFileSync('git', ['push', 'origin', 'agent/phase4-composite-validation'], { cwd: repo, stdio: 'inherit' });
}
console.log(execFileSync('git', ['rev-parse', 'HEAD'], { cwd: repo, encoding: 'utf8' }).trim());
