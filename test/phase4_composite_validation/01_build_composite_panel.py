import bisect
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "test/phase4_composite_validation/config/composite_registry.json"
OUT_DIR = ROOT / "test/phase4_composite_validation/output"
PHASE4_DIR = ROOT / "backtest/phase4"


def sha256_file(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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
    t_date = spx_arr[idx_t]["date"]
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
    return exit_row["adjClose"] / entry - 1, exit_row["date"]


def eligible_module_observations(all_snaps, registry):
    rows = []
    for decision_date, snap in all_snaps.items():
        modules = snap.get("modules", {})
        for module_name, cfg in registry["modules"].items():
            m = modules.get(module_name)
            if not m:
                continue
            if m.get("status") != "ok":
                continue
            if module_name == "pensionRebalance" and m.get("isRebalanceWindow") is not True:
                continue
            raw = m.get(cfg["signalPath"])
            fts = m.get("firstTradableSession")
            sig_at = m.get("signalAvailableAt")
            if raw is None or fts is None or sig_at is None:
                continue
            try:
                signed_raw = float(raw) * float(cfg["sign"])
            except (TypeError, ValueError):
                continue
            if not np.isfinite(signed_raw):
                continue
            rows.append({
                "decisionDate": decision_date,
                "module": module_name,
                "firstTradableSession": fts,
                "signalAvailableAt": sig_at,
                "rawSignal": float(raw),
                "signedRawSignal": signed_raw,
            })
    return pd.DataFrame(rows)


def expanding_ecdf_scores(obs_df):
    if obs_df.empty:
        return obs_df.assign(moduleScore=np.nan, historyN=0)
    obs_df = obs_df.copy()
    obs_df["moduleScore"] = np.nan
    obs_df["historyN"] = 0

    for module_name, module_df in obs_df.groupby("module", sort=False):
        module_df = module_df.sort_values(["firstTradableSession", "decisionDate"])
        history = []
        for fts, same_fts in module_df.groupby("firstTradableSession", sort=True):
            n_hist = len(history)
            for idx, row in same_fts.iterrows():
                if n_hist == 0:
                    continue
                x = row["signedRawSignal"]
                ecdf = bisect.bisect_right(history, x) / n_hist
                obs_df.at[idx, "moduleScore"] = 2.0 * ecdf - 1.0
                obs_df.at[idx, "historyN"] = n_hist
            # Do not allow same-FTS observations to enter each other's history.
            for x in same_fts["signedRawSignal"].tolist():
                bisect.insort(history, float(x))
    return obs_df


def build_panel():
    registry = load_json(REGISTRY_PATH)
    inp = registry["inputs"]
    dev_snap_path = ROOT / inp["developmentSnapshots"]
    dev_lbl_path = ROOT / inp["developmentLabels"]
    holdout_snap_path = ROOT / inp["holdoutSnapshots"]
    spx_path = ROOT / inp["spx"]
    phase3_contract_path = ROOT / inp["phase3StatisticalContract"]

    for required in [dev_snap_path, dev_lbl_path, spx_path, phase3_contract_path]:
        if not required.exists():
            raise FileNotFoundError(f"Required Phase 4 input missing: {required}")

    if not holdout_snap_path.exists():
        raise FileNotFoundError(
            "True 2025-2026 holdout snapshots are missing. Generate them without inspecting outcomes, e.g.\n"
            "node backtest/build_historical_snapshots.js 2025-01-01 2026-08-07 "
            "phase4/snapshots_phase4_holdout.json 0\n"
            "Phase 4 refuses to substitute Phase 3 (2016-2024) data for the holdout."
        )

    dev_snaps = load_json(dev_snap_path)
    dev_labels = load_json(dev_lbl_path)  # Loaded for provenance / date coverage; composite labels use new composite FTS.
    holdout_snaps = load_json(holdout_snap_path)
    spx = load_json(spx_path)
    spx_arr = spx.get("values", spx)
    spx_map = {row["date"]: i for i, row in enumerate(spx_arr)}

    overlap = set(dev_snaps).intersection(holdout_snaps)
    if overlap:
        raise ValueError(f"Development and holdout snapshots overlap on {len(overlap)} decision dates.")
    if not set(dev_snaps).issubset(set(dev_labels)):
        raise ValueError("Phase 3 development labels do not cover every development snapshot decisionDate.")

    all_snaps = dict(dev_snaps)
    all_snaps.update(holdout_snaps)

    obs = eligible_module_observations(all_snaps, registry)
    obs = expanding_ecdf_scores(obs)
    obs_lookup = {
        (r.decisionDate, r.module): r
        for r in obs.itertuples(index=False)
    }

    rows = []
    required_core = registry["compositeDefinition"]["requiredCoreModules"]
    for decision_date in sorted(all_snaps):
        snap = all_snaps[decision_date]
        modules = snap.get("modules", {})
        active = []
        failure_reasons = []

        for module_name in required_core:
            m = modules.get(module_name)
            scored = obs_lookup.get((decision_date, module_name))
            if not m or m.get("status") != "ok":
                failure_reasons.append(f"{module_name}:status_not_ok")
                continue
            if scored is None or not np.isfinite(scored.moduleScore):
                failure_reasons.append(f"{module_name}:no_prior_ecdf_history_or_signal")
                continue
            active.append(scored)

        if failure_reasons:
            continue

        pension = modules.get("pensionRebalance")
        if pension and pension.get("status") == "ok" and pension.get("isRebalanceWindow") is True:
            p_scored = obs_lookup.get((decision_date, "pensionRebalance"))
            if p_scored is not None and np.isfinite(p_scored.moduleScore):
                active.append(p_scored)
            # Conditional pension is optional; lack of prior history does not invalidate the three-core composite.

        composite_fts = max(r.firstTradableSession for r in active)
        composite_signal_at = max(r.signalAvailableAt for r in active)
        composite_score = float(np.mean([r.moduleScore for r in active]))

        baseline_asof, mom_raw, vol20_raw = baseline_stats(spx_arr, spx_map, composite_fts)
        ret1, last1 = forward_return(spx_arr, spx_map, composite_fts, 1)
        ret5, last5 = forward_return(spx_arr, spx_map, composite_fts, 5)
        ret20, last20 = forward_return(spx_arr, spx_map, composite_fts, 20)

        if not np.isfinite(ret5) or last5 is None:
            continue

        year = int(composite_fts[:4])
        period = "development" if year <= 2024 else "holdout"

        score_by_module = {r.module: float(r.moduleScore) for r in active}
        hist_by_module = {r.module: int(r.historyN) for r in active}
        rows.append({
            "decisionDate": decision_date,
            "period": period,
            "compositeSignalAvailableAt": composite_signal_at,
            "compositeFirstTradableSession": composite_fts,
            "baselineAsOfSession": baseline_asof,
            "activeModuleCount": len(active),
            "pensionActive": "pensionRebalance" in score_by_module,
            "volControlScore": score_by_module.get("volControl"),
            "ctaEtfProxyScore": score_by_module.get("ctaEtfProxy"),
            "riskParityScore": score_by_module.get("riskParity"),
            "pensionRebalanceScore": score_by_module.get("pensionRebalance"),
            "volControlHistoryN": hist_by_module.get("volControl"),
            "ctaEtfProxyHistoryN": hist_by_module.get("ctaEtfProxy"),
            "riskParityHistoryN": hist_by_module.get("riskParity"),
            "pensionRebalanceHistoryN": hist_by_module.get("pensionRebalance"),
            "compositeScore": composite_score,
            "momentumRaw": mom_raw,
            "vol20Raw": vol20_raw,
            "return1d": ret1,
            "return5d": ret5,
            "return20d": ret20,
            "lastLabelSession1d": last1,
            "lastLabelSession5d": last5,
            "lastLabelSession20d": last20,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("No valid Phase 4 composite rows were generated.")
    df = df.sort_values(["compositeFirstTradableSession", "decisionDate"]).reset_index(drop=True)

    dev = df[df["period"] == "development"]
    holdout = df[df["period"] == "holdout"]
    if dev.empty:
        raise RuntimeError("No development composite rows generated.")
    holdout_years = set(pd.to_datetime(holdout["compositeFirstTradableSession"]).dt.year.tolist()) if not holdout.empty else set()
    required_holdout_years = set(registry["oos"]["requiredHoldoutYears"])
    if not required_holdout_years.issubset(holdout_years):
        raise RuntimeError(
            f"Holdout does not contain required years {sorted(required_holdout_years)}; found {sorted(holdout_years)}."
        )

    PHASE4_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    panel_path = PHASE4_DIR / "composite_panel.parquet"
    df.to_parquet(panel_path, index=False)

    manifest = {
        "registrySHA256": sha256_file(REGISTRY_PATH),
        "phase3StatisticalContractSHA256": sha256_file(phase3_contract_path),
        "developmentSnapshotsSHA256": sha256_file(dev_snap_path),
        "developmentLabelsSHA256": sha256_file(dev_lbl_path),
        "holdoutSnapshotsSHA256": sha256_file(holdout_snap_path),
        "spxSHA256": sha256_file(spx_path),
        "compositePanelSHA256": sha256_file(panel_path),
        "developmentRows": int(len(dev)),
        "holdoutRows": int(len(holdout)),
        "developmentFirstFTS": str(dev["compositeFirstTradableSession"].min()),
        "developmentLastFTS": str(dev["compositeFirstTradableSession"].max()),
        "holdoutFirstFTS": str(holdout["compositeFirstTradableSession"].min()),
        "holdoutLastFTS": str(holdout["compositeFirstTradableSession"].max()),
    }
    with (PHASE4_DIR / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    with (OUT_DIR / "01_summary.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Phase 4 composite panel: {len(df)} rows ({len(dev)} development, {len(holdout)} holdout).")


if __name__ == "__main__":
    build_panel()
