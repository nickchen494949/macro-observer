import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "test/phase5_exploratory/output"

def bootstrap_ic(df, iterations=5000, seed=20260807, block_length=20):
    rng = np.random.default_rng(seed)
    n = len(df)
    ics = []
    
    score_arr = df["score"].values
    fwd_arr = df["fwd"].values
    
    for _ in range(iterations):
        indices = []
        while len(indices) < n:
            start = rng.integers(0, max(1, n - block_length + 1))
            indices.extend(range(start, start + block_length))
        indices = indices[:n]
        
        samp_score = score_arr[indices]
        samp_fwd = fwd_arr[indices]
        
        # fallback to pearson on ranks if needed, spearman is slower in loop, but let's just use scipy
        r, _ = spearmanr(samp_score, samp_fwd)
        if np.isfinite(r):
            ics.append(r)
            
    if not ics:
        return np.nan, np.nan
    return np.percentile(ics, 2.5), np.percentile(ics, 97.5)

def eval_structure(df_struct, sid, h):
    df_struct = df_struct.dropna(subset=["score", "fwd"]).copy()
    n = len(df_struct)
    if n < 60 or df_struct["score"].nunique() < 2:
        return {"id": sid, "valid": False, "reason": "insufficient_data"}
        
    rho, _ = spearmanr(df_struct["score"], df_struct["fwd"])
    direction = 1
    direction_pass = bool(rho > 0)
    
    rank_s = df_struct["score"].rank(method="average")
    rank_y = df_struct["fwd"].rank(method="average")
    x = sm.add_constant(rank_s)
    maxlag = max(h - 1, int(math.floor(4 * ((n / 100.0) ** (2.0 / 9.0)))))
    hac = sm.OLS(rank_y, x).fit(cov_type="HAC", cov_kwds={"maxlags": maxlag})
    pval = float(hac.pvalues.iloc[1])
    
    ci_low, ci_high = bootstrap_ic(df_struct)
    
    # Partial Rank IC
    cc = df_struct.dropna(subset=["score", "fwd", "mom", "vol"]).copy()
    partial_rho = np.nan
    if len(cc) >= 60 and cc["score"].nunique() >= 2:
        rs = cc["score"].rank(method="average")
        ry = cc["fwd"].rank(method="average")
        rm = cc["mom"].rank(method="average")
        rv = cc["vol"].rank(method="average")
        controls = sm.add_constant(pd.DataFrame({"mom": rm, "vol": rv}))
        resid_s = sm.OLS(rs, controls).fit().resid
        resid_y = sm.OLS(ry, controls).fit().resid
        partial_rho = float(resid_s.corr(resid_y))
        
    # Annual and Robustness
    df_struct["year"] = pd.to_datetime(df_struct["t_date"]).dt.year
    annual = {}
    years = sorted(df_struct["year"].unique())
    eligible_years = []
    
    for y in years:
        dy = df_struct[df_struct["year"] == y]
        ny = len(dy)
        if ny >= 30 and dy["score"].nunique() >= 2:
            y_rho, _ = spearmanr(dy["score"], dy["fwd"])
            annual[str(y)] = {"N": ny, "IC": float(y_rho)}
            eligible_years.append(y)
    
    direction_years = sum(1 for y in eligible_years if annual[str(y)]["IC"] > 0)
    pct_direction = direction_years / len(eligible_years) if eligible_years else 0.0
    
    catastrophic = sum(1 for y in eligible_years if annual[str(y)]["IC"] < 0 and abs(annual[str(y)]["IC"]) >= 0.5 * abs(rho))
    
    loyo = {}
    for y in eligible_years:
        dy = df_struct[df_struct["year"] != y]
        if len(dy) >= 60 and dy["score"].nunique() >= 2:
            y_rho, _ = spearmanr(dy["score"], dy["fwd"])
            loyo[str(y)] = float(y_rho)
            
    loyo_med = float(np.median(list(loyo.values()))) if loyo else np.nan
    
    # Correlations
    score_cols = [c for c in df_struct.columns if c.startswith("score_")]
    corr_matrix = df_struct[score_cols].corr(method="spearman").to_dict()
    
    res = {
        "id": sid,
        "valid": True,
        "N": n,
        "spearman_rho": float(rho),
        "direction_pass": direction_pass,
        "hac_p": pval,
        "bootstrap_ci_low": ci_low,
        "bootstrap_ci_high": ci_high,
        "partial_rank_ic": partial_rho,
        "annual_ic": annual,
        "pct_eligible_years_expected_direction": pct_direction,
        "leave_one_year_out_median_ic": loyo_med,
        "catastrophic_sign_reversals": catastrophic,
        "component_correlations": corr_matrix
    }
    
    if sid == "ShortFlow_1D":
        # sub diagnostics
        p_act = df_struct[df_struct["pension_active"] == True]
        p_inact = df_struct[df_struct["pension_active"] == False]
        
        act_ic = spearmanr(p_act["score"], p_act["fwd"])[0] if len(p_act) > 2 else np.nan
        inact_ic = spearmanr(p_inact["score"], p_inact["fwd"])[0] if len(p_inact) > 2 else np.nan
        
        res["shortflow_pension_diagnostic"] = {
            "active_N": len(p_act),
            "active_IC": float(act_ic),
            "inactive_N": len(p_inact),
            "inactive_IC": float(inact_ic),
            "pct_active": len(p_act) / n
        }
        
    return res

def main():
    panel = pd.read_parquet(OUT_DIR / "phase5_multi_horizon_panel.parquet")
    registry = json.loads((ROOT / "test/phase5_exploratory/config/phase5_registry.json").read_text())
    
    results = {}
    for struct in registry["composites"]:
        sid = struct["id"]
        h = struct["target_horizon"]
        df_struct = panel[panel["structure_id"] == sid]
        results[sid] = eval_structure(df_struct, sid, h)
        
    with (OUT_DIR / "phase5_ic_results.json").open("w") as f:
        json.dump(results, f, indent=2)
        
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
