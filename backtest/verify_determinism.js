const { execSync } = require('child_process');
const fs = require('fs');
const crypto = require('crypto');
const path = require('path');

function hashFile(filePath) {
    let content = fs.readFileSync(filePath, 'utf8');
    try {
        if (filePath.endsWith('.json')) {
            const parsed = JSON.parse(content);
            for (const key of Object.keys(parsed)) {
                if (parsed[key]) delete parsed[key].snapshotGeneratedAt;
            }
            content = JSON.stringify(parsed);
        } else if (filePath.endsWith('.jsonl')) {
            content = content.split('\n').map(line => {
                if (!line) return line;
                const parsed = JSON.parse(line);
                return JSON.stringify(parsed);
            }).join('\n');
        }
    } catch(e) {}
    return crypto.createHash('sha256').update(content).digest('hex');
}

console.log("Starting Full Replay Determinism Test (2016-2024)");

// 1. Run Replay A
console.log("\nExecuting Replay A...");
execSync('node backtest/build_historical_snapshots.js 2016-01-01 2025-01-01 snapshots_test_A.json', { stdio: 'inherit', cwd: path.join(__dirname, '..') });
const snapA = path.join(__dirname, 'snapshots_test_A.json');
const stateA = path.join(__dirname, 'model_states_test_A.jsonl');

// 2. Run Replay B
console.log("\nExecuting Replay B...");
execSync('node backtest/build_historical_snapshots.js 2016-01-01 2025-01-01 snapshots_test_B.json', { stdio: 'inherit', cwd: path.join(__dirname, '..') });
const snapB = path.join(__dirname, 'snapshots_test_B.json');
const stateB = path.join(__dirname, 'model_states_test_B.jsonl');

// 3. Compare Hashes
console.log("\nVerifying Artifact Determinism...");
const hashSnapA = hashFile(snapA);
const hashSnapB = hashFile(snapB);
const hashStateA = hashFile(stateA);
const hashStateB = hashFile(stateB);

console.log(`Replay A Snapshots SHA256: ${hashSnapA}`);
console.log(`Replay B Snapshots SHA256: ${hashSnapB}`);
if (hashSnapA === hashSnapB) {
    console.log("✅ snapshot sequence SHA256 identical");
} else {
    console.error("❌ snapshot sequence SHA256 mismatch!");
    process.exit(1);
}

console.log(`Replay A Model States SHA256: ${hashStateA}`);
console.log(`Replay B Model States SHA256: ${hashStateB}`);
if (hashStateA === hashStateB) {
    console.log("✅ model_state sequence SHA256 identical");
} else {
    console.error("❌ model_state sequence SHA256 mismatch!");
    process.exit(1);
}

console.log("\n✅ Replay Determinism OK. mismatches = 0");
