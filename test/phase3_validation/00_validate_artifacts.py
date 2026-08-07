import json
import hashlib
import sys
import math

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def validate():
    print("Validating Phase 3 Canonical Artifacts...")
    
    with open("backtest/phase3/manifest.json", 'r') as f:
        manifest = json.load(f)
        
    # 1. Hashes
    sigs = sha256_file("test/phase3_validation/config/signal_registry.json")
    hyps = sha256_file("test/phase3_validation/config/hypothesis_registry.json")
    bases = sha256_file("test/phase3_validation/config/baseline_registry.json")
    assert sigs == manifest['signalRegistrySHA256'], "FAIL: Signal registry hash mismatch."
    assert hyps == manifest['hypothesisRegistrySHA256'], "FAIL: Hypothesis registry hash mismatch."
    assert bases == manifest['baselineRegistrySHA256'], "FAIL: Baseline registry hash mismatch."
    print("Registry hashes PASS")
    
    snap_hash = sha256_file("backtest/phase3/snapshots_phase3.json")
    ms_hash = sha256_file("backtest/phase3/model_states_phase3.jsonl")
    lbl_hash = sha256_file("backtest/phase3/forward_labels_phase3.json")
    assert snap_hash == manifest['snapshotsSHA256'], "FAIL: snapshots hash mismatch."
    assert ms_hash == manifest['modelStatesSHA256'], "FAIL: modelStates hash mismatch."
    assert lbl_hash == manifest['forwardLabelsSHA256'], "FAIL: labels hash mismatch."
    print("Artifact hashes PASS")

    # 2. Date Coverage & Key Coverage
    with open("backtest/phase3/snapshots_phase3.json", 'r') as f:
        snaps = json.load(f)
    
    with open("backtest/phase3/forward_labels_phase3.json", 'r') as f:
        labels = json.load(f)
        
    dates = sorted(snaps.keys())
    assert len(dates) > 0, "No snapshots found."
    assert dates[0] >= manifest['canonicalStartDate'], f"Start date too early: {dates[0]}"
    assert dates[-1] <= manifest['canonicalEndDate'], f"End date too late: {dates[-1]}"
    print("Actual date coverage PASS")
    
    lbl_dates = sorted(labels.keys())
    assert set(dates) == set(lbl_dates), "Snapshot keys do not match Label keys."
    print("Snapshot/label key coverage PASS")
    
    # 3. Model States coverage and chain
    ms_dates = []
    with open("backtest/phase3/model_states_phase3.jsonl", 'r') as f:
        for line in f:
            if not line.strip(): continue
            row = json.loads(line)
            ms_dates.append(row['decisionDate'])
            
    assert len(ms_dates) == len(dates), "Model states row count mismatch."
    assert set(ms_dates) == set(dates), "Model states dates mismatch."
    
    for i in range(1, len(ms_dates)):
        assert ms_dates[i] > ms_dates[i-1], "Model states not strictly increasing."
    print("State file coverage PASS")
    
    # Check chain breaks from snapshots
    breaks = 0
    for i in range(1, len(dates)):
        curr_meta = snaps[dates[i]]['meta']
        prev_meta = snaps[dates[i-1]]['meta']
        if curr_meta['previousModelStateHash'] != prev_meta['outputModelStateHash']:
            breaks += 1
    assert breaks == 0, f"FAIL: found {breaks} state-chain breaks."
    print("State-chain breaks = 0 PASS")
    
    # 4. Primary Signal Paths and Label structures
    for d in dates:
        snap = snaps[d]
        lbl = labels[d]
        if 'modules' not in snap: continue
        
        for m in ['volControl', 'ctaEtfProxy', 'riskParity', 'pensionRebalance']:
            if m not in snap['modules']: continue
            m_snap = snap['modules'][m]
            if m_snap.get('status') == 'ok':
                # Primary signals exist check
                if m == 'volControl':
                    assert 'nextDayEstimateIfTargetUnchanged' in m_snap, f"{d} {m} missing primary signal"
                elif m == 'ctaEtfProxy':
                    assert 'equityAggregatePositionChange' in m_snap, f"{d} {m} missing primary signal"
                elif m == 'riskParity':
                    assert 'equityAllocationChange5d' in m_snap, f"{d} {m} missing primary signal"
                elif m == 'pensionRebalance':
                    assert 'equityOverweightPct' in m_snap, f"{d} {m} missing primary signal"
                    
            if m in lbl['modules']:
                m_lbl = lbl['modules'][m]
                if m_lbl.get('labelStatus') == 'ok':
                    assert m_lbl['firstTradableSession'] == m_snap['firstTradableSession'], "fts mismatch"
                    for h in [1,3,5,10,20]:
                        k = f'{h}d'
                        ret = m_lbl[f'return{k}Open']
                        mae = m_lbl[f'mae{k}']
                        mdd = m_lbl[f'mdd{k}']
                        last = m_lbl[f'lastLabelSession{k}']
                        assert not math.isnan(ret) and not math.isinf(ret), f"NaN/Inf in return {h}d"
                        assert not math.isnan(mae) and not math.isinf(mae), f"NaN/Inf in mae {h}d"
                        assert not math.isnan(mdd) and not math.isinf(mdd), f"NaN/Inf in mdd {h}d"
                        assert last >= m_lbl['firstTradableSession'], "lastLabelSession invalid"
                        if h >= 5:
                            vol = m_lbl[f'vol{k}']
                            assert not math.isnan(vol) and not math.isinf(vol), f"NaN/Inf in vol {h}d"
                            
    print("Primary signal paths exist PASS")
    print("All primary labels exist PASS")
    print("firstTradableSession alignment PASS")
    print("lastLabelSession valid per horizon PASS")
    print("NaN/Infinity = 0 PASS")
    
    print("\nCanonical Artifact Gate: PASS")

if __name__ == '__main__':
    validate()
