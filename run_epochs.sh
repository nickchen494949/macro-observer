#!/bin/bash

echo "Running Warm-up period 2017-2018 -> 2019 View"
node backtest/build_historical_snapshots.js 2017-01-01 2019-12-31 snapshots_2017_2019.json

echo "Running Crisis period: COVID Crash (Feb-Apr 2020)"
node backtest/build_historical_snapshots.js 2020-02-01 2020-04-30 snapshots_covid.json

echo "Running Crisis period: 2022 Shock (Jan-Dec 2022)"
node backtest/build_historical_snapshots.js 2022-01-01 2022-12-31 snapshots_2022.json

echo "Done."
