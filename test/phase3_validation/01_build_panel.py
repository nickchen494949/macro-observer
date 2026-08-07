import json
import pandas as pd
import numpy as np
import os
import math

def calc_vol20(spx_data, idx_t):
    if idx_t < 20: return np.nan
    rets = []
    for j in range(idx_t - 19, idx_t + 1):
        prev = spx_data[j-1]['adjClose'] if j-1 >= 0 else spx_data[j]['adjOpen']
        rets.append(math.log(spx_data[j]['adjClose'] / prev))
    variance = np.var(rets, ddof=1)
    return math.sqrt(variance * 252)

def build_panel():
    with open('backtest/phase3/snapshots_phase3.json') as f:
        snaps = json.load(f)
    with open('backtest/phase3/forward_labels_phase3.json') as f:
        labels = json.load(f)
    with open('data/yahoo/_GSPC.json') as f:
        spx = json.load(f)
        
    spx_arr = spx.get('values', spx)
    spx_map = {row['date']: i for i, row in enumerate(spx_arr)}
    spx_dates = sorted(spx_map.keys())
    
    # helper for finding baseline 't'
    def get_baseline_session_and_stats(fts):
        idx_F = spx_map.get(fts)
        if idx_F is None or idx_F == 0:
            return None, np.nan, np.nan
        idx_t = idx_F - 1
        t_date = spx_arr[idx_t]['date']
        
        # Momentum
        if idx_t >= 252:
            mom = (spx_arr[idx_t]['adjClose'] / spx_arr[idx_t - 252]['adjClose']) - 1
        else:
            mom = np.nan
            
        # Vol20
        vol20 = calc_vol20(spx_arr, idx_t)
        return t_date, mom, vol20

    rows = []
    
    for d, snap in snaps.items():
        if 'modules' not in snap: continue
        lbl = labels.get(d, {})
        if 'modules' not in lbl: continue
        
        for m in ['volControl', 'ctaEtfProxy', 'riskParity', 'pensionRebalance']:
            if m not in snap['modules']: continue
            m_snap = snap['modules'][m]
            m_lbl = lbl['modules'].get(m, {})
            
            if m_snap.get('status') != 'ok' or m_lbl.get('labelStatus') != 'ok':
                continue
                
            fts = m_snap['firstTradableSession']
            if fts not in spx_map: continue
            
            t_date, mom, vol20 = get_baseline_session_and_stats(fts)
            if t_date is None: continue
            
            # Extract raw signal
            sig_val = np.nan
            if m == 'volControl':
                sig_val = m_snap.get('nextDayEstimateIfTargetUnchanged', np.nan)
            elif m == 'ctaEtfProxy':
                sig_val = m_snap.get('equityAggregatePositionChange', np.nan)
            elif m == 'riskParity':
                sig_val = m_snap.get('equityAllocationChange5d', np.nan)
            elif m == 'pensionRebalance':
                # Pension only eligible on actual rebalance window days
                if not m_snap.get('rebalanceActive', False):
                    continue
                sig_val = m_snap.get('equityOverweightPct', np.nan)
                
            if pd.isna(sig_val): continue
                
            # Create a row per horizon
            for h in [1, 3, 5, 10, 20]:
                k = f'{h}d'
                if f'return{k}Open' not in m_lbl: continue
                
                rows.append({
                    'decisionDate': d,
                    'module': m,
                    'signalAvailableAt': m_snap['signalAvailableAt'],
                    'firstTradableSession': fts,
                    'baselineAsOfSession': t_date,
                    'lastLabelSession': m_lbl[f'lastLabelSession{k}'],
                    'horizon': h,
                    'rawSignalValue': float(sig_val),
                    'outcomeReturn': m_lbl[f'return{k}Open'],
                    'outcomeMae': m_lbl[f'mae{k}'],
                    'outcomeMdd': m_lbl[f'mdd{k}'],
                    'momentumRaw': mom,
                    'vol20Raw': vol20
                })
                
    df = pd.DataFrame(rows)
    out_dir = 'test/phase3_validation/output'
    os.makedirs(out_dir, exist_ok=True)
    df.to_parquet(os.path.join(out_dir, 'phase3_panel.parquet'))
    print(f"Generated Phase 3 Panel with {len(df)} rows.")

if __name__ == '__main__':
    build_panel()
