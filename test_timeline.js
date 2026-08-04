const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const dates = [
  '2021-03-01',
  '2021-10-01',
  '2023-06-01'
];

let md = '# Inflation Audit Timeline\n\n';
md += 'This document contains the detailed evidence breakdown for the selected test dates to verify the stage mappings.\n\n';

function runTest(date) {
  console.log(`\n=== Testing Date: ${date} ===`);
  try {
    execSync('pkill -f "node server.js" 2>/dev/null || true');
    execSync(`TEST_DATE="${date}" node server.js > /dev/null 2>&1 &`);
    execSync('sleep 3');
    const out = execSync('curl -s http://localhost:8765/api/data').toString();
    const d = JSON.parse(out);
    
    const inf = d.diagnostics.inflation;
    
    md += `## ${date}\n\n`;
    
    for (const stage of ['pressure', 'transmission', 'damage']) {
      const s = inf[stage];
      md += `### ${stage.toUpperCase()} (${s.status})\n`;
      md += `**Score**: ${s.score}\n`;
      if (s.evidence && s.evidence.length > 0) {
        md += `**Evidence (Red)**:\n` + s.evidence.map(e => `- ${e}`).join('\n') + '\n\n';
      }
      if (s.counterEvidence && s.counterEvidence.length > 0) {
        md += `**Counter Evidence (Green)**:\n` + s.counterEvidence.map(e => `- ${e}`).join('\n') + '\n\n';
      }
      if (s.missing && s.missing.length > 0) {
        md += `**Missing**:\n` + s.missing.map(e => `- ${e}`).join('\n') + '\n\n';
      }
    }
    
  } catch(e) {
    console.log(`Error testing ${date}: ${e.message}`);
  } finally {
    execSync('pkill -f "node server.js" 2>/dev/null || true');
  }
}

for (const d of dates) {
  runTest(d);
}

const artifactPath = '/Users/happygolucky/.gemini/antigravity/brain/40f10927-316f-406a-9fef-af217128d198/audit_timeline.md';
fs.writeFileSync(artifactPath, md);
console.log(`Saved audit to ${artifactPath}`);
