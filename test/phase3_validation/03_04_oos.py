import json
import pandas as pd
import numpy as np
import statsmodels.api as sm
from scipy.stats import spearmanr
import os
import math

def moving_block_bootstrap_d(d_series, h, iterations=5000, seed=20260807):
    # d_series is already sorted chronologically
    d_vals = d_series.values
    N = len(d_vals)
    block_length = max(h, 20)
    
    if N < block_length:
        return np.nan, np.nan
        
    blocks = []
    for i in range(N - block_length + 1):
        blocks.append(d_vals[i:i+block_length])
        
    np.random.seed(seed)
    
    mean_samples = []
    for _ in range(iterations):
        sample_vals = []
        sampled_len = 0
        while sampled_len < N:
            idx = np.random.randint(0, len(blocks))
            sample_vals.extend(blocks[idx])
            sampled_len += block_length
            
        bs_array = np.array(sample_vals[:N])
        mean_samples.append(np.mean(bs_array))
        
    mean_samples = np.array(mean_samples)
    if len(mean_samples) == 0:
        return np.nan, np.nan
        
    return np.percentile(mean_samples, 2.5), np.percentile(mean_samples, 97.5)

def ecdf_transform(train_vals, test_vals):
    # Count of train elements <= x / N_train
    train_sorted = np.sort(train_vals)
    N = len(train_sorted)
    res = []
    for x in test_vals:
        count = np.searchsorted(train_sorted, x, side='right')
        res.append(count / N)
    return np.array(res)

def winsorize_train_test(train_vals, test_vals, limits=(0.05, 0.95)):
    low = np.percentile(train_vals, limits[0]*100, method='linear')
    high = np.percentile(train_vals, limits[1]*100, method='linear')
    train_w = np.clip(train_vals, low, high)
    test_w = np.clip(test_vals, low, high)
    return train_w, test_w

def main():
    print("Running 03_04_oos.py")
    df = pd.read_parquet('test/phase3_validation/output/phase3_panel.parquet')
    df['firstTradableSession'] = pd.to_datetime(df['firstTradableSession'])
    df['lastLabelSession'] = pd.to_datetime(df['lastLabelSession'])
    
    with open('test/phase3_validation/config/hypothesis_registry.json') as f:
        registry = json.load(f)
        
    results = []
    
    for mod_name, mod_data in registry['modules'].items():
        for hyp in mod_data.get('primaryHypotheses', []):
            if False: continue
                
            horizon = hyp['horizon']
            outcome_field = 'outcomeReturn'
            
            sub_df = df[(df['module'] == mod_name) & (df['horizon'] == horizon)].copy()
            sub_df = sub_df.dropna(subset=['rawSignalValue', outcome_field, 'momentumRaw', 'vol20Raw']).copy()
            sub_df = sub_df.sort_values('firstTradableSession')
            
            if len(sub_df) == 0:
                continue
                
            sub_df['testYear'] = sub_df['firstTradableSession'].dt.year
            
            pooled_d = []
            pooled_e_b = []
            pooled_e_e = []
            pooled_y = []
            
            years = sorted(sub_df['testYear'].unique())
            valid_fold_count = 0
            
            for y in years:
                test_fold = sub_df[sub_df['testYear'] == y].copy()
                first_test_session = test_fold['firstTradableSession'].min()
                
                # strict purge
                train_fold = sub_df[sub_df['lastLabelSession'] < first_test_session].copy()
                
                if len(train_fold) < 60:
                    continue
                    
                # Train mom/vol stats
                mom_mean, mom_std = train_fold['momentumRaw'].mean(), train_fold['momentumRaw'].std(ddof=1)
                vol_mean, vol_std = train_fold['vol20Raw'].mean(), train_fold['vol20Raw'].std(ddof=1)
                
                if mom_std == 0 or vol_std == 0 or pd.isna(mom_std) or pd.isna(vol_std):
                    continue
                    
                train_z_mom = (train_fold['momentumRaw'] - mom_mean) / mom_std
                train_z_vol = (train_fold['vol20Raw'] - vol_mean) / vol_std
                train_baseline_score = train_z_mom - train_z_vol
                
                test_z_mom = (test_fold['momentumRaw'] - mom_mean) / mom_std
                test_z_vol = (test_fold['vol20Raw'] - vol_mean) / vol_std
                test_baseline_score = test_z_mom - test_z_vol
                
                # Signal preprocessing
                train_sig_raw = train_fold['rawSignalValue'].values
                test_sig_raw = test_fold['rawSignalValue'].values
                
                if mod_name == 'pensionRebalance':
                    train_sig = train_sig_raw
                    test_sig = test_sig_raw
                else:
                    train_sig_w, test_sig_w = winsorize_train_test(train_sig_raw, test_sig_raw)
                    train_sig = ecdf_transform(train_sig_w, train_sig_w)
                    test_sig = ecdf_transform(train_sig_w, test_sig_w)
                    
                if np.var(train_sig, ddof=1) == 0:
                    continue
                    
                train_fold['processedSignal'] = train_sig
                test_fold['processedSignal'] = test_sig
                
                # Fit Baseline OLS
                X_b_train = sm.add_constant(train_baseline_score)
                Y_train = train_fold[outcome_field]
                model_b = sm.OLS(Y_train, X_b_train).fit()
                
                X_b_test = sm.add_constant(test_baseline_score, has_constant='add')
                pred_b = model_b.predict(X_b_test)
                
                # Fit Enhanced OLS
                X_e_train = sm.add_constant(pd.DataFrame({'b': train_baseline_score.values, 's': train_sig}, index=train_fold.index))
                model_e = sm.OLS(Y_train, X_e_train).fit()
                
                X_e_test = sm.add_constant(pd.DataFrame({'b': test_baseline_score.values, 's': test_sig}, index=test_fold.index), has_constant='add')
                pred_e = model_e.predict(X_e_test)
                
                Y_test = test_fold[outcome_field]
                
                err_b = Y_test - pred_b
                err_e = Y_test - pred_e
                
                d = (err_b ** 2) - (err_e ** 2)
                
                pooled_d.extend(d.values)
                pooled_e_b.extend(err_b.values)
                pooled_e_e.extend(err_e.values)
                pooled_y.extend(Y_test.values)
                valid_fold_count += 1
                
            if valid_fold_count == 0 or len(pooled_d) < 60:
                results.append({
                    'module': mod_name,
                    'hypothesis_id': f"{mod_name}_{horizon}d",
                    'valid': False
                })
                continue
                
            pooled_d = pd.Series(pooled_d)
            pooled_y = pd.Series(pooled_y)
            pooled_e_b = pd.Series(pooled_e_b)
            pooled_e_e = pd.Series(pooled_e_e)
            
            mean_d = pooled_d.mean()
            
            # HAC on intercept
            X_d = np.ones(len(pooled_d))
            model_d = sm.OLS(pooled_d, X_d)
            N = len(pooled_d)
            maxlag = max(horizon - 1, int(math.floor(4 * ((N / 100.0) ** (2.0/9.0)))))
            res_d = model_d.fit(cov_type='HAC', cov_kwds={'maxlags': maxlag})
            hac_p = res_d.pvalues[0]
            
            # Bootstrap
            ci_low, ci_high = moving_block_bootstrap_d(pooled_d, horizon)
            
            # Confirmatory metrics
            mae_b = pooled_e_b.abs().mean()
            mae_e = pooled_e_e.abs().mean()
            delta_mae = mae_b - mae_e
            
            ss_tot = ((pooled_y - pooled_y.mean())**2).sum()
            ss_res_b = (pooled_e_b**2).sum()
            ss_res_e = (pooled_e_e**2).sum()
            
            r2_b = 1 - ss_res_b / ss_tot
            r2_e = 1 - ss_res_e / ss_tot
            delta_r2 = r2_e - r2_b
            
            oos_loss_bootstrap_pass = True if (not np.isnan(ci_low) and ci_low > 0) else False
            squared_error_pass = True if (mean_d > 0 and hac_p < 0.05 and oos_loss_bootstrap_pass) else False
            
            results.append({
                'module': mod_name,
                'hypothesis_id': f"{mod_name}_{horizon}d",
                'N_pooled': N,
                'mean_d': mean_d,
                'hac_p_two_sided': hac_p,
                'hac_maxlag': maxlag,
                'bootstrap_ci_low': ci_low,
                'bootstrap_ci_high': ci_high,
                'delta_mae': delta_mae,
                'delta_r2': delta_r2,
                'oos_loss_bootstrap_pass': oos_loss_bootstrap_pass,
                'squared_error_pass': squared_error_pass,
                'valid': True
            })
            
    with open('test/phase3_validation/output/03_04_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("03_04_oos completed")

if __name__ == '__main__':
    main()
