import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / "backtest/phase4/composite_panel.parquet"
REGISTRY = ROOT / "test/phase4_composite_validation/config/composite_registry.json"
OUT = ROOT / "test/phase4_composite_validation/output/04_composite_robustness.json"


def main():
    with REGISTRY.open() as f:
        reg = json.load(f)
    df = pd.read_parquet(PANEL)
    dev = df[df["period"] == "development"].dropna(subset=["compositeScore", "return5d"]).copy()
    dev["year"] = pd.to_datetime(dev["compositeFirstTradableSession"]).dt.year
    direction = reg["outcomes"]["primary"]["expectedDirection"]
    min_n = reg["statistics"]["minimumN"]
    annual_min = reg["robustness"]["annualMinimumN"]

    result = {"valid": False, "N": int(len(dev))}
    if len(dev) < min_n or dev["compositeScore"].nunique() < 2:
        result["failure_reason"] = "insufficient_development_data_or_constant_signal"
    else:
        agg_rho, _ = spearmanr(dev["compositeScore"], dev["return5d"])
        agg_correct = bool(agg_rho > 0) if direction == 1 else bool(agg_rho < 0)

        annual = {}
        eligible = []
        for year, ydf in dev.groupby("year"):
            if len(ydf) < annual_min or ydf["compositeScore"].nunique() < 2:
                annual[int(year)] = {"N": int(len(ydf)), "eligible": False, "IC": None}
                continue
            rho, _ = spearmanr(ydf["compositeScore"], ydf["return5d"])
            if not np.isfinite(rho):
                annual[int(year)] = {"N": int(len(ydf)), "eligible": False, "IC": None}
                continue
            eligible.append(int(year))
            annual[int(year)] = {"N": int(len(ydf)), "eligible": True, "IC": float(rho)}

        if not eligible:
            result["failure_reason"] = "no_eligible_years"
        else:
            n_total = sum(annual[y]["N"] for y in eligible)
            correct = sum(1 for y in eligible if (annual[y]["IC"] > 0 if direction == 1 else annual[y]["IC"] < 0))
            pct_correct = correct / len(eligible)
            pct_pass = pct_correct >= reg["robustness"]["eligibleYearsSameDirectionMinPct"]

            contributions = {}
            abs_sum = 0.0
            for y in eligible:
                c = (annual[y]["N"] / n_total) * annual[y]["IC"]
                contributions[y] = c
                abs_sum += abs(c)
            if abs_sum == 0:
                max_share = None
                max_share_pass = False
            else:
                shares = {y: abs(c) / abs_sum for y, c in contributions.items()}
                max_share = max(shares.values())
                max_share_pass = max_share <= reg["robustness"]["maxYearContributionShare"]

            catastrophic = 0
            for y in eligible:
                ic_y = annual[y]["IC"]
                if np.sign(ic_y) != np.sign(agg_rho) and abs(ic_y) >= 0.5 * abs(agg_rho):
                    catastrophic += 1
            reversal_pass = catastrophic <= reg["robustness"]["maxCatastrophicSignReversals"]

            loyo = {}
            loyo_values = []
            for y in eligible:
                tmp = dev[dev["year"] != y]
                if len(tmp) < min_n or tmp["compositeScore"].nunique() < 2:
                    loyo[y] = None
                    continue
                rho, _ = spearmanr(tmp["compositeScore"], tmp["return5d"])
                if np.isfinite(rho):
                    loyo[y] = float(rho)
                    loyo_values.append(float(rho))
                else:
                    loyo[y] = None
            loyo_median = float(np.median(loyo_values)) if loyo_values else np.nan
            loyo_pass = bool(loyo_median > 0) if direction == 1 and np.isfinite(loyo_median) else (
                bool(loyo_median < 0) if direction == -1 and np.isfinite(loyo_median) else False
            )

            regime_pass = bool(agg_correct and pct_pass and max_share_pass and reversal_pass and loyo_pass)
            result.update({
                "valid": True,
                "aggregateIC": float(agg_rho),
                "aggregateDirectionPass": agg_correct,
                "eligibleYears": eligible,
                "annual": annual,
                "pctEligibleYearsCorrectDirection": float(pct_correct),
                "pctDirectionPass": bool(pct_pass),
                "yearContributions": {str(k): float(v) for k, v in contributions.items()},
                "maxYearContributionShare": None if max_share is None else float(max_share),
                "maxContributionPass": bool(max_share_pass),
                "catastrophicSignReversals": int(catastrophic),
                "catastrophicReversalPass": bool(reversal_pass),
                "leaveOneYearOutIC": {str(k): v for k, v in loyo.items()},
                "leaveOneYearOutMedianIC": None if not np.isfinite(loyo_median) else float(loyo_median),
                "leaveOneYearOutPass": bool(loyo_pass),
                "regime_pass": regime_pass,
            })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
