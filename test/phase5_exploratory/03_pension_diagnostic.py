import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "test/phase5_exploratory/output"

def get_pension_timing(date_str):
    dt = pd.to_datetime(date_str)
    day = dt.day
    month = dt.month
    
    if day >= 20:
        timing = "pre_month_end"
        target_month = month
    else:
        timing = "post_month_end"
        target_month = month - 1
        if target_month == 0:
            target_month = 12
            
    if target_month in [3, 6, 9, 12]:
        q_type = "quarter_end"
    else:
        q_type = "ordinary_month_end"
        
    return timing, q_type

def bootstrap_ic(df, col, fwd_col="fwd", iterations=5000, seed=20260807, block_length=20):
    rng = np.random.default_rng(seed)
    n = len(df)
    ics = []
    
    score_arr = df[col].values
    fwd_arr = df[fwd_col].values
    
    for _ in range(iterations):
        indices = []
        while len(indices) < n:
            start = rng.integers(0, max(1, n - block_length + 1))
            indices.extend(range(start, start + block_length))
        indices = indices[:n]
        
        samp_score = score_arr[indices]
        samp_fwd = fwd_arr[indices]
        
        r, _ = spearmanr(samp_score, samp_fwd)
        if np.isfinite(r):
            ics.append(r)
            
    if not ics:
        return np.nan, np.nan
    return np.percentile(ics, 2.5), np.percentile(ics, 97.5)

def calc_subgroup_ic(df, col, group_col):
    res = {}
    for g in sorted(df[group_col].unique()):
        dg = df[df[group_col] == g]
        if len(dg) > 2:
            r, _ = spearmanr(dg[col], dg["fwd"])
            res[str(g)] = {"N": len(dg), "IC": float(r)}
    return res

def main():
    panel = pd.read_parquet(OUT_DIR / "phase5_multi_horizon_panel.parquet")
    # Filter to active pension days
    df = panel[(panel["structure_id"] == "ShortFlow_1D") & (panel["pension_active"] == True)].copy()
    
    # 1. Tests A, B, C
    res = {}
    
    for label, col in [("A_Pension_Alone", "score_pensionRebalance"), 
                       ("B_VC_Alone", "score_volControl"),
                       ("C_Combined_ShortFlow", "score")]:
        df_clean = df.dropna(subset=[col, "fwd"])
        if len(df_clean) > 2:
            r, _ = spearmanr(df_clean[col], df_clean["fwd"])
            res[label] = float(r)
            
    # Pension detailed diagnostic
    col = "score_pensionRebalance"
    df_clean = df.dropna(subset=[col, "fwd"]).copy()
    n = len(df_clean)
    
    rank_s = df_clean[col].rank(method="average")
    rank_y = df_clean["fwd"].rank(method="average")
    x = sm.add_constant(rank_s)
    maxlag = max(1 - 1, int(math.floor(4 * ((n / 100.0) ** (2.0 / 9.0))))) # h=1
    hac = sm.OLS(rank_y, x).fit(cov_type="HAC", cov_kwds={"maxlags": maxlag})
    hac_p = float(hac.pvalues.iloc[1])
    
    ci_low, ci_high = bootstrap_ic(df_clean, col)
    
    cc = df_clean.dropna(subset=[col, "fwd", "mom", "vol"]).copy()
    partial_rho = np.nan
    if len(cc) > 2:
        rs = cc[col].rank(method="average")
        ry = cc["fwd"].rank(method="average")
        rm = cc["mom"].rank(method="average")
        rv = cc["vol"].rank(method="average")
        controls = sm.add_constant(pd.DataFrame({"mom": rm, "vol": rv}))
        resid_s = sm.OLS(rs, controls).fit().resid
        resid_y = sm.OLS(ry, controls).fit().resid
        partial_rho = float(resid_s.corr(resid_y))
        
    df_clean["year"] = pd.to_datetime(df_clean["t_date"]).dt.year
    annual = calc_subgroup_ic(df_clean, col, "year")
    
    df_clean[["timing", "q_type"]] = df_clean["decisionDate"].apply(lambda d: pd.Series(get_pension_timing(d)))
    timing_res = calc_subgroup_ic(df_clean, col, "timing")
    q_type_res = calc_subgroup_ic(df_clean, col, "q_type")
    
    pension_details = {
        "N": n,
        "spearman_rho": res["A_Pension_Alone"],
        "hac_p": hac_p,
        "bootstrap_ci_low": ci_low,
        "bootstrap_ci_high": ci_high,
        "partial_rank_ic": partial_rho,
        "annual_ic": annual,
        "timing": timing_res,
        "quarter_type": q_type_res
    }
    
    # Multivariate Regression
    df_multi = df.dropna(subset=["score_pensionRebalance", "score_volControl", "fwd"]).copy()
    if len(df_multi) > 2:
        ry = df_multi["fwd"].rank(method="average")
        rp = df_multi["score_pensionRebalance"].rank(method="average")
        rv = df_multi["score_volControl"].rank(method="average")
        
        X = sm.add_constant(pd.DataFrame({"rank_Pension": rp, "rank_VC": rv}))
        model = sm.OLS(ry, X).fit()
        
        multi_reg = {
            "beta_Pension": float(model.params["rank_Pension"]),
            "p_value_Pension": float(model.pvalues["rank_Pension"]),
            "beta_VC": float(model.params["rank_VC"]),
            "p_value_VC": float(model.pvalues["rank_VC"])
        }
    else:
        multi_reg = None
        
    final_output = {
        "baseline_tests": res,
        "pension_details": pension_details,
        "multivariate_regression": multi_reg
    }
    
    with (OUT_DIR / "phase5B_pension_diagnostic.json").open("w") as f:
        json.dump(final_output, f, indent=2)
        
    print(json.dumps(final_output, indent=2))

if __name__ == "__main__":
    main()
