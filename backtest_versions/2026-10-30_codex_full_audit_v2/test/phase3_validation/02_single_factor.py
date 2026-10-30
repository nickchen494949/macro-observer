import json
import pandas as pd
import numpy as np
import statsmodels.api as sm
from scipy.stats import spearmanr
import os
import math

def moving_block_bootstrap_ic(df, signal_col, outcome_col, h, iterations=5000, seed=20260807):
    # df is sorted by firstTradableSession, then decisionDate
    df = df.sort_values(by=['firstTradableSession', 'decisionDate']).reset_index(drop=True)
    N = len(df)
    block_length = max(h, 20)
    
    if N < block_length:
        return np.nan, np.nan
        
    blocks = []
    for i in range(N - block_length + 1):
        blocks.append(df.iloc[i:i+block_length])
        
    np.random.seed(seed)
    
    ic_samples = []
    for _ in range(iterations):
        sample_dfs = []
        sampled_len = 0
        while sampled_len < N:
            idx = np.random.randint(0, len(blocks))
            sample_dfs.append(blocks[idx])
            sampled_len += block_length
            
        bs_df = pd.concat(sample_dfs).iloc[:N]
        # Calculate IC
        rho, _ = spearmanr(bs_df[signal_col], bs_df[outcome_col])
        ic_samples.append(rho)
        
    ic_samples = np.array(ic_samples)
    ic_samples = ic_samples[~np.isnan(ic_samples)]
    if len(ic_samples) == 0:
        return np.nan, np.nan
        
    return np.percentile(ic_samples, 2.5), np.percentile(ic_samples, 97.5)

def main():
    print("Running 02_single_factor.py")
    df = pd.read_parquet('test/phase3_validation/output/phase3_panel.parquet')
    
    with open('test/phase3_validation/config/hypothesis_registry.json') as f:
        registry = json.load(f)
        
    results = []
    
    for mod_name, mod_data in registry['modules'].items():
        for hyp in mod_data.get('primaryHypotheses', []):
            horizon = hyp['horizon']
            direction = hyp['expectedDirection']
            outcome_field = 'outcomeReturn'
            hyp_id = f"{mod_name}_{horizon}d"
            
            sub_df = df[(df['module'] == mod_name) & (df['horizon'] == horizon)].copy()
            sub_df = sub_df.dropna(subset=['rawSignalValue', outcome_field])
            
            N = len(sub_df)
            
            invalid = False
            if N < 60 or sub_df['rawSignalValue'].var() == 0:
                invalid = True
                
            if invalid:
                results.append({
                    'module': mod_name,
                    'hypothesis_id': hyp_id,
                    'horizon': horizon,
                    'direction': direction,
                    'N': N,
                    'spearman_rho': np.nan,
                    'hac_p_two_sided': 1.0,
                    'direction_pass': False,
                    'ic_bootstrap_pass': False,
                    'partial_ic_pass': False,
                    'valid': False
                })
                continue
                
            # Spearman IC
            rho, _ = spearmanr(sub_df['rawSignalValue'], sub_df[outcome_field])
            direction_pass = True if (direction == 1 and rho > 0) or (direction == -1 and rho < 0) else False
            
            # HAC
            rank_S = sub_df['rawSignalValue'].rank(method='average')
            rank_Y = sub_df[outcome_field].rank(method='average')
            
            X = sm.add_constant(rank_S)
            model = sm.OLS(rank_Y, X)
            
            maxlag = max(horizon - 1, int(math.floor(4 * ((N / 100.0) ** (2.0/9.0)))))
            res = model.fit(cov_type='HAC', cov_kwds={'maxlags': maxlag})
            hac_p = res.pvalues[rank_S.name]
            
            # Bootstrap
            ci_low, ci_high = moving_block_bootstrap_ic(sub_df, 'rawSignalValue', outcome_field, horizon)
            if direction == 1:
                bootstrap_pass = True if (not np.isnan(ci_low) and ci_low > 0) else False
            else:
                bootstrap_pass = True if (not np.isnan(ci_high) and ci_high < 0) else False
                
            # Partial IC
            strict_df = sub_df.dropna(subset=['rawSignalValue', outcome_field, 'momentumRaw', 'vol20Raw']).copy()
            if len(strict_df) < 60:
                partial_ic_pass = False
            else:
                rank_S2 = strict_df['rawSignalValue'].rank(method='average')
                rank_Y2 = strict_df[outcome_field].rank(method='average')
                rank_M2 = strict_df['momentumRaw'].rank(method='average')
                rank_V2 = strict_df['vol20Raw'].rank(method='average')
                
                X2 = sm.add_constant(pd.concat([rank_M2, rank_V2], axis=1))
                
                res_S = sm.OLS(rank_S2, X2).fit()
                res_Y = sm.OLS(rank_Y2, X2).fit()
                
                resid_S = res_S.resid
                resid_Y = res_Y.resid
                
                partial_rho = resid_S.corr(resid_Y)
                
                if np.isnan(partial_rho) or partial_rho == 0:
                    partial_ic_pass = False
                elif direction == 1 and partial_rho > 0:
                    partial_ic_pass = True
                elif direction == -1 and partial_rho < 0:
                    partial_ic_pass = True
                else:
                    partial_ic_pass = False
                    
            results.append({
                'module': mod_name,
                'hypothesis_id': hyp_id,
                'horizon': horizon,
                'direction': direction,
                'N': N,
                'spearman_rho': rho,
                'hac_beta': res.params[rank_S.name],
                'hac_p_two_sided': hac_p,
                'hac_maxlag': maxlag,
                'bootstrap_ci_low': ci_low,
                'bootstrap_ci_high': ci_high,
                'direction_pass': direction_pass,
                'ic_bootstrap_pass': bootstrap_pass,
                'partial_ic_pass': partial_ic_pass,
                'valid': True
            })
            
    with open('test/phase3_validation/output/02_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("02_single_factor completed")

if __name__ == '__main__':
    main()
