import json
import pandas as pd
import numpy as np
from scipy.stats import spearmanr
import os

def main():
    print("Running 05_robustness.py")
    df = pd.read_parquet('test/phase3_validation/output/phase3_panel.parquet')
    df['firstTradableSession'] = pd.to_datetime(df['firstTradableSession'])
    df['testYear'] = df['firstTradableSession'].dt.year
    
    with open('test/phase3_validation/config/hypothesis_registry.json') as f:
        registry = json.load(f)
        
    results = []
    
    for mod_name, mod_data in registry['modules'].items():
        for hyp in mod_data.get('primaryHypotheses', []):
            if False: continue
                
            horizon = hyp['horizon']
            direction = hyp['expectedDirection']
            outcome_field = 'outcomeReturn'
            
            sub_df = df[(df['module'] == mod_name) & (df['horizon'] == horizon)].copy()
            sub_df = sub_df.dropna(subset=['rawSignalValue', outcome_field])
            
            if len(sub_df) < 60:
                results.append({
                    'module': mod_name,
                    'hypothesis_id': f"{mod_name}_{horizon}d",
                    'valid': False
                })
                continue
                
            agg_rho, _ = spearmanr(sub_df['rawSignalValue'], sub_df[outcome_field])
            agg_direction = np.sign(agg_rho)
            agg_correct = True if (direction == 1 and agg_rho > 0) or (direction == -1 and agg_rho < 0) else False
            
            years = sorted(sub_df['testYear'].unique())
            eligible_years = []
            annual_ics = {}
            ns = {}
            
            for y in years:
                y_df = sub_df[sub_df['testYear'] == y]
                if len(y_df) >= 30:
                    y_rho, _ = spearmanr(y_df['rawSignalValue'], y_df[outcome_field])
                    if not np.isnan(y_rho):
                        eligible_years.append(y)
                        annual_ics[y] = y_rho
                        ns[y] = len(y_df)
                        
            if len(eligible_years) == 0:
                results.append({
                    'module': mod_name,
                    'hypothesis_id': f"{mod_name}_{horizon}d",
                    'valid': False
                })
                continue
                
            n_total = sum(ns.values())
            correct_years = sum(1 for y in eligible_years if np.sign(annual_ics[y]) == direction)
            pct_correct = correct_years / len(eligible_years)
            pct_pass = bool(pct_correct >= 0.70)
            
            contributions = [ (ns[y] / n_total) * annual_ics[y] for y in eligible_years ]
            abs_contributions = np.abs(contributions)
            sum_abs_cont = np.sum(abs_contributions)
            
            if sum_abs_cont == 0:
                max_share_pass = False
            else:
                shares = abs_contributions / sum_abs_cont
                max_share_pass = bool(np.max(shares) <= 0.50)
                
            catastrophic_reversals = 0
            for y in eligible_years:
                ic_y = annual_ics[y]
                if np.sign(ic_y) != agg_direction and abs(ic_y) >= 0.5 * abs(agg_rho):
                    catastrophic_reversals += 1
            reversal_pass = bool(catastrophic_reversals <= 1)
            
            # LOYO
            loyo_ics = []
            for y_drop in eligible_years:
                loyo_df = sub_df[sub_df['testYear'] != y_drop]
                loyo_rho, _ = spearmanr(loyo_df['rawSignalValue'], loyo_df[outcome_field])
                loyo_ics.append(loyo_rho)
                
            loyo_median = np.median(loyo_ics)
            loyo_pass = True if (direction == 1 and loyo_median > 0) or (direction == -1 and loyo_median < 0) else False
            
            regime_pass = bool(agg_correct and pct_pass and max_share_pass and reversal_pass and loyo_pass)
            
            results.append({
                'module': mod_name,
                'hypothesis_id': f"{mod_name}_{horizon}d",
                'agg_rho': agg_rho,
                'agg_correct': agg_correct,
                'pct_correct': pct_correct,
                'pct_pass': pct_pass,
                'max_share_pass': max_share_pass,
                'catastrophic_reversals': catastrophic_reversals,
                'reversal_pass': reversal_pass,
                'loyo_median': loyo_median,
                'loyo_pass': loyo_pass,
                'regime_pass': regime_pass,
                'valid': True
            })
            
    with open('test/phase3_validation/output/05_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("05_robustness completed")

if __name__ == '__main__':
    main()
