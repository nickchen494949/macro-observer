import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / "backtest/phase4/composite_panel.parquet"
REGISTRY = ROOT / "test/phase4_composite_validation/config/composite_registry.json"
OUT = ROOT / "test/phase4_composite_validation/output/02_composite_ic.json"


def bootstrap_ic(df, iterations, seed, block_length):
    df = df.sort_values(["compositeFirstTradableSession", "decisionDate"]).reset_index(drop=True)
    n = len(df)
    if n < block_length:
        return np.nan, np.nan
    blocks = [df.iloc[i:i + block_length] for i in range(n - block_length + 1)]
    rng = np.random.default_rng(seed)
    samples = []
    for _ in range(iterations):
        pieces = []
        total = 0
        while total < n:
            b = blocks[int(rng.integers(0, len(blocks)))]
            pieces.append(b)
            total += block_length
        bs = pd.concat(pieces, ignore_index=True).iloc[:n]
        rho, _ = spearmanr(bs["compositeScore"], bs["return5d"])
        if np.isfinite(rho):
            samples.append(float(rho))
    if not samples:
        return np.nan, np.nan
    return float(np.percentile(samples, 2.5)), float(np.percentile(samples, 97.5))


def main():
    with REGISTRY.open() as f:
        reg = json.load(f)
    df = pd.read_parquet(PANEL)
    dev = df[df["period"] == "development"].copy()
    dev = dev.dropna(subset=["compositeScore", "return5d"])
    n = len(dev)
    min_n = reg["statistics"]["minimumN"]
    direction = reg["outcomes"]["primary"]["expectedDirection"]

    result = {"hypothesis_id": "systematicFlowComposite_5d", "N": int(n), "valid": False}
    if n < min_n or dev["compositeScore"].nunique() < 2:
        result.update({
            "failure_reason": "insufficient_data_or_constant_signal",
            "direction_pass": False,
            "hac_pass": False,
            "ic_bootstrap_pass": False,
            "partial_ic_pass": False,
        })
    else:
        rho, _ = spearmanr(dev["compositeScore"], dev["return5d"])
        rank_s = dev["compositeScore"].rank(method="average")
        rank_y = dev["return5d"].rank(method="average")
        x = sm.add_constant(rank_s)
        maxlag = max(4, int(math.floor(4 * ((n / 100.0) ** (2.0 / 9.0)))))
        hac = sm.OLS(rank_y, x).fit(cov_type="HAC", cov_kwds={"maxlags": maxlag})
        beta = float(hac.params.iloc[1])
        pval = float(hac.pvalues.iloc[1])

        ci_low, ci_high = bootstrap_ic(
            dev,
            iterations=reg["statistics"]["bootstrapIterations"],
            seed=reg["statistics"]["bootstrapSeed"],
            block_length=reg["statistics"]["bootstrapBlockLength"],
        )
        direction_pass = bool(rho > 0) if direction == 1 else bool(rho < 0)
        bootstrap_pass = bool(ci_low > 0) if direction == 1 and np.isfinite(ci_low) else (
            bool(ci_high < 0) if direction == -1 and np.isfinite(ci_high) else False
        )

        cc = dev.dropna(subset=["compositeScore", "return5d", "momentumRaw", "vol20Raw"]).copy()
        partial_rho = np.nan
        partial_pass = False
        if len(cc) >= min_n and cc["compositeScore"].nunique() >= 2:
            rs = cc["compositeScore"].rank(method="average")
            ry = cc["return5d"].rank(method="average")
            rm = cc["momentumRaw"].rank(method="average")
            rv = cc["vol20Raw"].rank(method="average")
            controls = sm.add_constant(pd.DataFrame({"momentum": rm, "vol": rv}))
            resid_s = sm.OLS(rs, controls).fit().resid
            resid_y = sm.OLS(ry, controls).fit().resid
            partial_rho = float(resid_s.corr(resid_y))
            if np.isfinite(partial_rho) and partial_rho != 0:
                partial_pass = bool(partial_rho > 0) if direction == 1 else bool(partial_rho < 0)

        result.update({
            "valid": True,
            "spearman_rho": float(rho),
            "direction_pass": direction_pass,
            "hac_beta": beta,
            "hac_p_two_sided": pval,
            "hac_maxlag": int(maxlag),
            "hac_pass": bool(pval < 0.05 and ((beta > 0) if direction == 1 else (beta < 0))),
            "bootstrap_ci_low": ci_low,
            "bootstrap_ci_high": ci_high,
            "ic_bootstrap_pass": bootstrap_pass,
            "partial_rank_ic": partial_rho,
            "partial_ic_pass": partial_pass,
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
