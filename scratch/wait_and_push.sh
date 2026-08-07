#!/bin/bash
echo "Waiting for build_historical_snapshots.js to finish..."
while pgrep -f "build_historical_snapshots.js" > /dev/null; do
    sleep 2
done
echo "Waiting for run_fred_sensitivity.js to finish..."
while pgrep -f "run_fred_sensitivity.js" > /dev/null; do
    sleep 2
done
echo "All tasks finished. Committing and pushing..."
git add backtest/model_states.jsonl backtest/forward_labels.json backtest/snapshots.json backtest/fred_sensitivity_report.json || true
git commit -m "[Data] Regenerate model_states, forward_labels, and fred_sensitivity" || true
git push origin main || true
