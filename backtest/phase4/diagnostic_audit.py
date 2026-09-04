import json

with open('backtest/phase4/snapshots_phase4_holdout.json') as f:
    snapshots = json.load(f)
    
with open('backtest/phase4/forward_labels_phase4_holdout.json') as f:
    labels = json.load(f)
    
def audit_year(year):
    stats = {
        'total_sessions': 0,
        'valid_vc': 0,
        'valid_cta': 0,
        'valid_rp': 0,
        'all_3_valid': 0,
        'missing_5d_labels': 0,
        'final_rows': 0,
        'exclusion_reasons': {}
    }
    
    for dt, snap in snapshots.items():
        if not dt.startswith(str(year)): continue
        stats['total_sessions'] += 1
        
        mods = snap.get('modules', {})
        vc_valid = mods.get('volControl', {}).get('status') == 'ok'
        cta_valid = mods.get('ctaEtfProxy', {}).get('status') == 'ok'
        rp_valid = mods.get('riskParity', {}).get('status') == 'ok'
        
        if vc_valid: stats['valid_vc'] += 1
        if cta_valid: stats['valid_cta'] += 1
        if rp_valid: stats['valid_rp'] += 1
        
        if vc_valid and cta_valid and rp_valid:
            stats['all_3_valid'] += 1
            
            lbl = labels.get(dt, {})
            comp_lbl = lbl.get('composite', {})
            
            if 'return5dOpen' not in comp_lbl:
                stats['missing_5d_labels'] += 1
                stats['exclusion_reasons']['Missing 5D Forward Label'] = stats['exclusion_reasons'].get('Missing 5D Forward Label', 0) + 1
            else:
                stats['final_rows'] += 1
        else:
            reason = "Missing Core Modules: "
            missing = []
            if not vc_valid: missing.append('VC')
            if not cta_valid: missing.append('CTA')
            if not rp_valid: missing.append('RP')
            reason += ", ".join(missing)
            stats['exclusion_reasons'][reason] = stats['exclusion_reasons'].get(reason, 0) + 1
            
    return stats

res2025 = audit_year(2025)
res2026 = audit_year(2026)

print("--- 2025 Audit ---")
for k, v in res2025.items(): print(f"{k}: {v}")

print("\n--- 2026 Audit ---")
for k, v in res2026.items(): print(f"{k}: {v}")
