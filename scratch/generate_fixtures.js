const fs = require('fs');

const baseSnapshot = {
  status: "ok",
  schemaVersion: 2,
  snapshotQuality: "complete",
  marketDataAsOf: "2026-08-04",
  snapshotGeneratedAt: "2026-08-06T18:00:00.000Z",
  summary: {
    dominantRegime: "conflicting",
    mechanismCount: 4,
    driverCount: 4,
    duplicatedDriverCount: 1,
    independentDataDomains: ["equity_price", "bond_market", "credit"],
    confidence: "medium",
    timelinePressures: {
      retrospectiveSameDay: { status: "ok", direction: "buy", mechanisms: ["leveragedEtf"], confidence: "medium" },
      ongoing1To5Days: { status: "ok", direction: "conflicting", mechanisms: ["volControl", "ctaTrend"], confidence: "medium_low" },
      recent5To20Days: { status: "ok", direction: "equity_to_bonds", mechanisms: ["riskParity"], confidence: "medium" },
      conditionalFuture: { status: "ok", direction: "selling", mechanisms: ["stressConditions"], confidence: "low" }
    },
    flowTimeline: {},
    narrative: { en: "Test", zh: "测试" },
    trendAmplifiers: {},
    crossAssetDeRisking: {},
    counterCyclicalFlows: {},
    excludedModules: []
  },
  modules: {
    volControl: {
      status: "ok",
      targetExposureToday: 0.65,
      actualExposureYesterday: 0.70,
      actualExposureToday: 0.68,
      dailyPositionChange: -0.02,
      fiveDayActualChange: -0.05,
      remainingExposureGap: -0.03,
      estimatedDailyFlowUsd: -8e9,
      nextDayEstimateIfTargetUnchanged: -2.4e9,
      estimatedFlowRange: { low: -12e9, high: -4e9 },
      flowPressure: "selling",
      aggregateDirection: "sell"
    },
    leveragedEtf: {
      status: "ok",
      totalGrossRebalanceUsd: 13.7e9,
      estimateRange: { low: 10e9, high: 16e9 },
      funds: [
        { name: "UPRO", grossRebalanceUsd: 5e9 },
        { name: "TQQQ", grossRebalanceUsd: 8.7e9 }
      ],
      aggregateDirection: "buy"
    },
    ctaTrend: {
      status: "ok",
      positionRegime: "buy",
      flowPressure: "buying",
      aggregatePositionChange: 0.15,
      assets: [],
      commonAsOfDate: "2026-08-04"
    },
    riskParity: {
      status: "ok",
      equityAllocationChange5d: -0.0375,
      bondAllocationChange5d: 0.0375,
      modelLeverageChange5d: 0,
      allocationDirection: "equity_to_bonds",
      deleveragingPressure: "none",
      commonAsOfDate: "2026-08-04"
    },
    pensionRebalance: {
      status: "not_in_window",
      currentEquityWeight: 0.61,
      targetEquityWeight: 0.60,
      equityOverweightPct: 1.0,
      daysToMonthEnd: 15,
      isRebalanceWindow: false,
      expectedFlow: "none"
    },
    stressConditions: {
      status: "stress",
      stressScore: 55,
      vix: 28.5,
      hyOas: 450,
      estimatedFlowUsd: null
    }
  }
};

fs.writeFileSync('test/fixtures/flow/real_mixed_snapshot.json', JSON.stringify(baseSnapshot, null, 2));

const buyingSnapshot = JSON.parse(JSON.stringify(baseSnapshot));
buyingSnapshot.summary.timelinePressures.ongoing1To5Days.direction = "buy";
buyingSnapshot.modules.volControl.flowPressure = "buying";
buyingSnapshot.modules.volControl.dailyPositionChange = 0.01;
buyingSnapshot.modules.volControl.estimatedDailyFlowUsd = 4e9;
buyingSnapshot.modules.volControl.remainingExposureGap = 0.05;
buyingSnapshot.modules.volControl.aggregateDirection = "buy";
buyingSnapshot.modules.riskParity.allocationDirection = "bonds_to_equity";
buyingSnapshot.summary.timelinePressures.recent5To20Days.direction = "bonds_to_equity";
fs.writeFileSync('test/fixtures/flow/real_buying_snapshot.json', JSON.stringify(buyingSnapshot, null, 2));

const partialSnapshot = JSON.parse(JSON.stringify(baseSnapshot));
partialSnapshot.snapshotQuality = "partial";
partialSnapshot.modules.ctaTrend = { status: "insufficient_data" };
partialSnapshot.modules.stressConditions = { status: "insufficient_data", missingInputs: ["VIX"] };
partialSnapshot.summary.excludedModules = ["ctaTrend", "stressConditions"];
partialSnapshot.summary.timelinePressures.ongoing1To5Days.status = "partial";
partialSnapshot.summary.timelinePressures.ongoing1To5Days.mechanisms = ["volControl"];
partialSnapshot.summary.timelinePressures.ongoing1To5Days.direction = "sell";
partialSnapshot.summary.timelinePressures.conditionalFuture.status = "partial";
partialSnapshot.summary.timelinePressures.conditionalFuture.mechanisms = [];
partialSnapshot.summary.timelinePressures.conditionalFuture.direction = "unavailable";
partialSnapshot.modules.leveragedEtf.totalGrossRebalanceUsd = 0;
partialSnapshot.modules.leveragedEtf.aggregateDirection = "neutral";
partialSnapshot.summary.timelinePressures.retrospectiveSameDay.direction = "neutral";
fs.writeFileSync('test/fixtures/flow/partial_unavailable_snapshot.json', JSON.stringify(partialSnapshot, null, 2));

console.log("Fixtures generated");
