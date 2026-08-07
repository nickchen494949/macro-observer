import json
import os

def load_json(path):
    with open(path) as f:
        return json.load(f)

def main():
    print("Running 07_evidence_gate.py")
    
    with open('test/phase3_validation/config/hypothesis_registry.json') as f:
        registry = json.load(f)
        
    res02 = load_json('test/phase3_validation/output/02_results.json')
    res0304 = load_json('test/phase3_validation/output/03_04_results.json')
    res05 = load_json('test/phase3_validation/output/05_results.json')
    res06 = load_json('test/phase3_validation/output/06_results.json')
    
    def get_res(results_list, module, hyp_id):
        for r in results_list:
            if r['module'] == module and r['hypothesis_id'] == hyp_id:
                return r
        return None
        
    verdicts = {}
    
    for mod_name, mod_data in registry['modules'].items():
        hyps = mod_data.get('primaryHypotheses', [])
        
        module_supported = True
        failure_reasons = []
        
        for hyp in hyps:
            horizon = hyp['horizon']
            hyp_id = f"{mod_name}_{horizon}d"
            
            r02 = get_res(res02, mod_name, hyp_id)
            r0304 = get_res(res0304, mod_name, hyp_id)
            r05 = get_res(res05, mod_name, hyp_id)
            r06 = get_res(res06, mod_name, hyp_id)
            
            if not r02 or not r02['valid']:
                module_supported = False
                failure_reasons.append(f"{hyp_id}: Invalid or insufficient data (02).")
                continue
                
            if not r02['direction_pass']:
                module_supported = False
                failure_reasons.append(f"{hyp_id}: Rank IC direction reversed.")
            if not r02['ic_bootstrap_pass']:
                module_supported = False
                failure_reasons.append(f"{hyp_id}: IC Bootstrap CI includes zero.")
            if not r02['partial_ic_pass']:
                module_supported = False
                failure_reasons.append(f"{hyp_id}: Partial Rank IC reversed or invalid.")
                
            if not r0304 or not r0304['valid']:
                module_supported = False
                failure_reasons.append(f"{hyp_id}: Invalid OOS data (03/04).")
            elif not r0304['squared_error_pass']:
                module_supported = False
                failure_reasons.append(f"{hyp_id}: Pooled OOS Squared Error gate failed.")
                
            if not r05 or not r05['valid']:
                module_supported = False
                failure_reasons.append(f"{hyp_id}: Invalid Regime data (05).")
            elif not r05['regime_pass']:
                module_supported = False
                failure_reasons.append(f"{hyp_id}: Regime robustness rules failed.")
                
            if not r06 or not r06['valid']:
                module_supported = False
                failure_reasons.append(f"{hyp_id}: Invalid FDR data (06).")
            elif not r06['fdr_pass']:
                module_supported = False
                failure_reasons.append(f"{hyp_id}: FDR Benjamini-Hochberg failed.")
                
        status = "SUPPORTED" if (module_supported and len(hyps) > 0) else "NOT_SUPPORTED"
        if len(hyps) == 0:
            status = "NOT_SUPPORTED"
            failure_reasons.append("No primary hypotheses active.")
            
        verdicts[mod_name] = {
            "status": status,
            "failure_reasons": failure_reasons
        }
        
    with open('test/phase3_validation/output/07_verdict.json', 'w') as f:
        json.dump(verdicts, f, indent=2)
        
    print("\n--- FINAL EVIDENCE VERDICT ---")
    for m, v in verdicts.items():
        print(f"[{m}] {v['status']}")
        for reason in v['failure_reasons']:
            print(f"  - {reason}")
    print("------------------------------")

if __name__ == '__main__':
    main()
