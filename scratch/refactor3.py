import re
import sys

with open('backtest/build_historical_snapshots.js', 'r') as f:
    content = f.read()

# 1. We no longer use `snapshots[t] = snapshot`, instead we stream it out or build two objects
# and write `snapshots.json` (just UI) and `model_states.jsonl`.
old_dict = "  const snapshots = {};"
new_dict = """  const snapshots = {};
  const modelStates = []; // to write to model_states.jsonl"""
content = content.replace(old_dict, new_dict)

old_write = """    // Only store snapshots if within the view window
    if (t >= VIEW_START_DATE) {
      snapshot.meta = snapshot.meta || {};
      snapshot.meta.replayGenesisDate = relevantTradingDays[0];
      snapshot.meta.viewStartDate = VIEW_START_DATE;
      snapshot.meta.viewEndDate = VIEW_END_DATE;
      snapshot.meta.warmupTradingDays = c - 1;
      snapshot.meta.previousStateHash = previousStateHash;
      snapshot.meta.outputStateHash = outputStateHash;
      snapshot.meta.previousModelStateHash = previousModelStateHash;
      snapshot.meta.outputModelStateHash = outputModelStateHash;
      snapshot.meta.stateChainBreaks = 0; // Strictly enforced by the sequential loop
      
      snapshots[t] = snapshot;
    }"""
new_write = """    // Only store snapshots if within the view window
    if (t >= VIEW_START_DATE) {
      snapshot.meta = snapshot.meta || {};
      snapshot.meta.replayGenesisDate = relevantTradingDays[0];
      snapshot.meta.viewStartDate = VIEW_START_DATE;
      snapshot.meta.viewEndDate = VIEW_END_DATE;
      snapshot.meta.warmupTradingDays = c - 1;
      snapshot.meta.previousStateHash = previousStateHash;
      snapshot.meta.outputStateHash = outputStateHash;
      snapshot.meta.previousModelStateHash = previousModelStateHash;
      snapshot.meta.outputModelStateHash = outputModelStateHash;
      snapshot.meta.stateChainBreaks = 0; // Strictly enforced by the sequential loop
      
      snapshots[t] = snapshot;
      modelStates.push({
        decisionDate: t,
        nextModelState
      });
    }"""
content = content.replace(old_write, new_write)

old_output = "  fs.writeFileSync(path.join(__dirname, 'snapshots.json'), JSON.stringify(snapshots, null, 2));"
new_output = """  fs.writeFileSync(path.join(__dirname, 'snapshots.json'), JSON.stringify(snapshots, null, 2));
  
  // Write separated recursive mathematical states
  const msLines = modelStates.map(ms => JSON.stringify(ms)).join('\\n');
  fs.writeFileSync(path.join(__dirname, 'model_states.jsonl'), msLines);
"""
content = content.replace(old_output, new_output)

# Update state chain verification logic in the loop: "Genesis之后 null modelStateHash = 0"
old_val = """  let modelStateBreaks = 0;
  for (let i = 1; i < snapKeys.length; i++) {
    if (snapshots[snapKeys[i]].meta.previousModelStateHash !== snapshots[snapKeys[i-1]].meta.outputModelStateHash) {
      modelStateBreaks++;
    }
  }"""
new_val = """  let modelStateBreaks = 0;
  let nullModelStateHashes = 0;
  for (let i = 1; i < snapKeys.length; i++) {
    const curPrevHash = snapshots[snapKeys[i]].meta.previousModelStateHash;
    const prevOutHash = snapshots[snapKeys[i-1]].meta.outputModelStateHash;
    if (curPrevHash !== prevOutHash) {
      modelStateBreaks++;
    }
    // Check for "null === null" trap post-genesis
    if (curPrevHash === null || curPrevHash === hashState(null)) {
      nullModelStateHashes++;
    }
  }"""
content = content.replace(old_val, new_val)

old_log = "  console.log(`Model-state chain breaks: ${modelStateBreaks}`);"
new_log = """  console.log(`Model-state chain breaks: ${modelStateBreaks}`);
  console.log(`Null model-state hashes post-genesis: ${nullModelStateHashes}`);"""
content = content.replace(old_log, new_log)

with open('backtest/build_historical_snapshots.js', 'w') as f:
    f.write(content)
