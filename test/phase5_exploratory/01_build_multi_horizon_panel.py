import bisect
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "test/phase5_exploratory/config/phase5_registry.json"
OUT_DIR = ROOT / "test/phase5_exploratory/output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def calc_vol20(spx_arr, idx_t):
    if idx_t < 20:
        return np.nan
    log_rets = []
    for j in range(idx_t - 19, idx_t + 1):
        prev = spx_arr[j - 1]["adjClose"]
        log_rets.append(math.log(spx_arr[j]["adjClose"] / prev))
    return math.sqrt(np.var(log_rets, ddof=1) * 252)

def baseline_stats(spx_arr, spx_map, fts):
    idx_f = spx_map.get(fts)
    if idx_f is None or idx_f == 0:
        return None, np.nan, np.nan
    idx_t = idx_f - 1
    t_date = spx_arr[idx_t]["date"] if "date" in spx_arr[idx_t] else spx_arr[idx_t][0]
    mom = np.nan
    if idx_t >= 252:
        mom = spx_arr[idx_t]["adjClose"] / spx_arr[idx_t - 252]["adjClose"] - 1
    return t_date, mom, calc_vol20(spx_arr, idx_t)

def forward_return(spx_arr, spx_map, fts, h):
    idx_f = spx_map.get(fts)
    if idx_f is None or idx_f + h - 1 >= len(spx_arr):
        return np.nan, None
    entry = spx_arr[idx_f]["adjOpen"]
    exit_row = spx_arr[idx_f + h - 1]
    if entry is None or exit_row.get("adjClose") is None:
        return np.nan, None
    exit_date = exit_row["date"] if "date" in exit_row else exit_row[0]
    return exit_row["adjClose"] / entry - 1, exit_date

def expanding_ecdf_scores(obs_df):
    if obs_df.empty:
        return obs_df.assign(moduleScore=np.nan)
    obs_df = obs_df.copy()
    obs_df["moduleScore"] = np.nan
    for module_name, module_df in obs_df.groupby("module", sort=False):
        module_df = module_df.sort_values(["firstTradableSession", "decisionDate"])
        history = []
        for fts, same_fts in module_df.groupby("firstTradableSession", sort=True):
            n_hist = len(history)
            for idx, row in same_fts.iterrows():
                if n_hist > 0:
                    x = row["signedRawSignal"]
                    ecdf = bisect.bisect_right(history, x) / n_hist
                    obs_df.at[idx, "moduleScore"] = 2.0 * ecdf - 1.0
            for x in same_fts["signedRawSignal"].tolist():
                bisect.insort(history, float(x))
    return obs_df

def build_panel():
    registry = load_json(REGISTRY_PATH)
    
    dev_snaps = load_json(ROOT / "backtest/phase3/snapshots_phase3.json")
    holdout_snaps = load_json(ROOT / "backtest/phase4/snapshots_phase4_holdout.json")
    
    all_snaps = dict(dev_snaps)
    all_snaps.update(holdout_snaps)
    
    spx_data = load_json(ROOT / "data/yahoo/_GSPC.json")
    spx_arr = spx_data.get("values", spx_data)
    spx_map = {row["date"] if "date" in row else row[0]: i for i, row in enumerate(spx_arr)}

    rows = []
    # Hardcoded module paths
    paths = {
        "volControl": "nextDayEstimateIfTargetUnchanged",
        "ctaEtfProxy": "equityAggregatePositionChange",
        "riskParity": "equityAllocationChange5d",
        "pensionRebalance": "equityOverweightPct"
    }
    
    for decision_date, snap in all_snaps.items():
        modules = snap.get("modules", {})
        for mod, path in paths.items():
            m = modules.get(mod)
            if not m or m.get("status") != "ok":
                continue
            if mod == "pensionRebalance" and m.get("isRebalanceWindow") is not True:
                continue
            raw = m.get(path)
            fts = m.get("firstTradableSession")
            if raw is None or fts is None or not np.isfinite(float(raw)):
                continue
            rows.append({
                "decisionDate": decision_date,
                "module": mod,
                "firstTradableSession": fts,
                "rawSignal": float(raw),
            })
    obs = pd.DataFrame(rows)
    
    # Apply signs based on registry to signedRawSignal
    obs["signedRawSignal"] = obs["rawSignal"]
    # pensionRebalance gets sign -1 across all composites
    obs.loc[obs["module"] == "pensionRebalance", "signedRawSignal"] *= -1
    
    obs = expanding_ecdf_scores(obs)
    obs_lookup = {(r.decisionDate, r.module): r for r in obs.itertuples()}

    panel_rows = []
    
    for struct in registry["composites"]:
        sid = struct["id"]
        h = struct["target_horizon"]
        for decision_date in sorted(all_snaps):
            snap = all_snaps[decision_date]
            modules = snap.get("modules", {})
            
            valid = True
            active_scores = []
            active_fts = []
            
            pension_active = False
            pension_score = None
            
            for c in struct["components"]:
                mod = c["module"]
                cond = c["condition"]
                
                m = modules.get(mod)
                scored = obs_lookup.get((decision_date, mod))
                
                is_pension = (mod == "pensionRebalance")
                is_active = False
                
                if m and m.get("status") == "ok":
                    if is_pension:
                        if m.get("isRebalanceWindow") is True:
                            is_active = True
                    else:
                        is_active = True
                
                if cond == "always" and not is_active:
                    valid = False
                    break
                    
                if is_active:
                    if scored is None or np.isnan(scored.moduleScore):
                        valid = False
                        break
                    active_scores.append(scored.moduleScore)
                    active_fts.append(scored.firstTradableSession)
                    if is_pension:
                        pension_active = True
                        pension_score = scored.moduleScore

            if not valid or not active_scores:
                continue
                
            comp_score = np.mean(active_scores)
            comp_fts = max(active_fts)
            
            t_date, mom, vol = baseline_stats(spx_arr, spx_map, comp_fts)
            if t_date is None:
                continue
                
            fwd, exit_date = forward_return(spx_arr, spx_map, comp_fts, h)
            if np.isnan(fwd):
                continue
                
            # Component scores for correlations
            # We save individual scores to compute correlation later
            comp_row = {
                "decisionDate": decision_date,
                "structure_id": sid,
                "score": comp_score,
                "fts": comp_fts,
                "t_date": t_date,
                "fwd": fwd,
                "pension_active": pension_active,
                "vol": vol,
                "mom": mom
            }
            # Record individual component scores
            for mod in paths.keys():
                scored = obs_lookup.get((decision_date, mod))
                comp_row[f"score_{mod}"] = scored.moduleScore if (scored and not np.isnan(scored.moduleScore)) else np.nan
                
            panel_rows.append(comp_row)
            
    panel = pd.DataFrame(panel_rows)
    panel.to_parquet(OUT_DIR / "phase5_multi_horizon_panel.parquet")
    print(f"Wrote Phase 5 Panel. Total rows: {len(panel)}")
    for sid, group in panel.groupby("structure_id"):
        print(f"  {sid}: {len(group)} rows")

if __name__ == "__main__":
    build_panel()
