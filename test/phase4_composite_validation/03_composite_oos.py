import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / "backtest/phase4/composite_panel.parquet"
REGISTRY = ROOT / "test/phase4_composite_validation/config/composite_registry.json"
OUT = ROOT / "test/phase4_composite_validation/output/03_composite_oos.json"


def bootstrap_mean(values, iterations, seed, block_length):
    values = np.asarray(values, dtype=float)
    n = len(values)
    if n < block_length:
        return np.nan, np.nan
    blocks = [values[i:i + block_length] for i in range(n - block_length + 1)]
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(iterations):
        sample = []
        while len(sample) < n:
            b = blocks[int(rng.integers(0, len(blocks)))]
            sample.extend(b.tolist())
        means.append(float(np.mean(sample[:n])))
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def main():
    with REGISTRY.open() as f:
        reg = json.load(f)
    df = pd.read_parquet(PANEL)
    df["compositeFirstTradableSession"] = pd.to_datetime(df["compositeFirstTradableSession"])
    df["lastLabelSession5d"] = pd.to_datetime(df["lastLabelSession5d"])
    df["year"] = df["compositeFirstTradableSession"].dt.year
    df = df.sort_values(["compositeFirstTradableSession", "decisionDate"]).reset_index(drop=True)

    folds = []
    pooled = []
    required_years = reg["oos"]["requiredHoldoutYears"]
    min_n = reg["statistics"]["minimumN"]

    for year in required_years:
        test = df[(df["period"] == "holdout") & (df["year"] == year)].copy()
        if test.empty:
            folds.append({"year": year, "valid": False, "reason": "missing_test_year"})
            continue
        first_test = test["compositeFirstTradableSession"].min()
        train = df[df["lastLabelSession5d"] < first_test].copy()

        common_cols = ["return5d", "momentumRaw", "vol20Raw", "compositeScore"]
        train = train.dropna(subset=common_cols)
        test = test.dropna(subset=common_cols)

        if len(train) < min_n or len(test) == 0:
            folds.append({"year": year, "valid": False, "reason": "insufficient_common_sample", "N_train": len(train), "N_test": len(test)})
            continue

        mom_mean = train["momentumRaw"].mean()
        mom_std = train["momentumRaw"].std(ddof=1)
        vol_mean = train["vol20Raw"].mean()
        vol_std = train["vol20Raw"].std(ddof=1)
        if not np.isfinite(mom_std) or not np.isfinite(vol_std) or mom_std == 0 or vol_std == 0:
            folds.append({"year": year, "valid": False, "reason": "insufficient_training_variation", "N_train": len(train), "N_test": len(test)})
            continue

        train_baseline = (train["momentumRaw"] - mom_mean) / mom_std - (train["vol20Raw"] - vol_mean) / vol_std
        test_baseline = (test["momentumRaw"] - mom_mean) / mom_std - (test["vol20Raw"] - vol_mean) / vol_std

        y_train = train["return5d"]
        xb = sm.add_constant(pd.DataFrame({"baseline": train_baseline}, index=train.index))
        xe = sm.add_constant(pd.DataFrame({"baseline": train_baseline, "composite": train["compositeScore"]}, index=train.index))
        mb = sm.OLS(y_train, xb).fit()
        me = sm.OLS(y_train, xe).fit()

        xb_test = sm.add_constant(pd.DataFrame({"baseline": test_baseline}, index=test.index), has_constant="add")
        xe_test = sm.add_constant(pd.DataFrame({"baseline": test_baseline, "composite": test["compositeScore"]}, index=test.index), has_constant="add")
        pred_b = mb.predict(xb_test)
        pred_e = me.predict(xe_test)

        for idx in test.index:
            y = float(test.at[idx, "return5d"])
            eb = y - float(pred_b.loc[idx])
            ee = y - float(pred_e.loc[idx])
            pooled.append({
                "decisionDate": test.at[idx, "decisionDate"],
                "firstTradableSession": test.at[idx, "compositeFirstTradableSession"].strftime("%Y-%m-%d"),
                "year": year,
                "y": y,
                "errBaseline": eb,
                "errEnhanced": ee,
                "d": eb * eb - ee * ee,
            })

        folds.append({
            "year": year,
            "valid": True,
            "N_train": int(len(train)),
            "N_test": int(len(test)),
            "firstTestTradableSession": first_test.strftime("%Y-%m-%d"),
            "trainLastLabelSessionMax": train["lastLabelSession5d"].max().strftime("%Y-%m-%d"),
            "baselineCoefficients": {k: float(v) for k, v in mb.params.items()},
            "enhancedCoefficients": {k: float(v) for k, v in me.params.items()},
        })

    valid_years = {f["year"] for f in folds if f.get("valid")}
    required_set = set(required_years)
    result = {"valid": False, "folds": folds, "requiredHoldoutYears": required_years}
    if valid_years != required_set:
        result["failure_reason"] = f"required holdout folds not all valid: valid={sorted(valid_years)}"
    else:
        pooled_df = pd.DataFrame(pooled).sort_values(["firstTradableSession", "decisionDate"]).reset_index(drop=True)
        n = len(pooled_df)
        if n < min_n:
            result["failure_reason"] = f"pooled holdout N={n} < minimumN={min_n}"
        else:
            d = pooled_df["d"]
            mean_d = float(d.mean())
            maxlag = max(4, int(math.floor(4 * ((n / 100.0) ** (2.0 / 9.0)))))
            hac = sm.OLS(d, np.ones(n)).fit(cov_type="HAC", cov_kwds={"maxlags": maxlag})
            pval = float(hac.pvalues.iloc[0])
            ci_low, ci_high = bootstrap_mean(
                d.values,
                iterations=reg["statistics"]["bootstrapIterations"],
                seed=reg["statistics"]["bootstrapSeed"],
                block_length=reg["statistics"]["bootstrapBlockLength"],
            )
            delta_mae = float(pooled_df["errBaseline"].abs().mean() - pooled_df["errEnhanced"].abs().mean())
            y = pooled_df["y"]
            ss_tot = float(((y - y.mean()) ** 2).sum())
            delta_r2 = np.nan
            if ss_tot > 0:
                r2_b = 1 - float((pooled_df["errBaseline"] ** 2).sum()) / ss_tot
                r2_e = 1 - float((pooled_df["errEnhanced"] ** 2).sum()) / ss_tot
                delta_r2 = r2_e - r2_b

            gate = bool(mean_d > 0 and pval < 0.05 and np.isfinite(ci_low) and ci_low > 0)
            result.update({
                "valid": True,
                "N_pooled": int(n),
                "mean_d": mean_d,
                "hac_p_two_sided": pval,
                "hac_maxlag": int(maxlag),
                "bootstrap_ci_low": ci_low,
                "bootstrap_ci_high": ci_high,
                "oos_loss_bootstrap_pass": bool(np.isfinite(ci_low) and ci_low > 0),
                "delta_mae": delta_mae,
                "delta_r2": None if not np.isfinite(delta_r2) else float(delta_r2),
                "squared_error_pass": gate,
            })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
