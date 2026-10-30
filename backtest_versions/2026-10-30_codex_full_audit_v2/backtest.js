#!/usr/bin/env node
// Codex: legacy unsafe implementation archived under audit/legacy_source/.
// All supported invocations now share the corrected canonical implementation.
const {main}=require('./backtest_v3');
console.warn('Legacy entry point: using Codex canonical macro replay; see audit/CHANGELOG.txt.');
try { main(); } catch(e) { console.error(e.stack); process.exitCode=2; }
