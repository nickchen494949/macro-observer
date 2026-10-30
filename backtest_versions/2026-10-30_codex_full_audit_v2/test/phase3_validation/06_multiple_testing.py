import json
from statsmodels.stats.multitest import multipletests
import os

def main():
    print("Running 06_multiple_testing.py")
    with open('test/phase3_validation/output/02_results.json') as f:
        res02 = json.load(f)
        
    pvals = []
    hyps = []
    
    for r in res02:
        if not r['valid']:
            pvals.append(1.0)
        else:
            pvals.append(r['hac_p_two_sided'])
        hyps.append(r)
            
    assert len(pvals) == 8, f"Expected 8 primary hypotheses, got {len(pvals)}"
    
    reject, pvals_corrected, _, _ = multipletests(pvals, alpha=0.05, method='fdr_bh')
    
    results = []
    for i, r in enumerate(hyps):
        results.append({
            'module': r['module'],
            'hypothesis_id': r['hypothesis_id'],
            'raw_p': pvals[i],
            'fdr_p': pvals_corrected[i],
            'fdr_pass': bool(reject[i]),
            'valid': r['valid']
        })
        
    with open('test/phase3_validation/output/06_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("06_multiple_testing completed")

if __name__ == '__main__':
    main()
