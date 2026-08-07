import json
import hashlib
import sys

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def validate():
    print("Validating Phase 3 Artifacts...")
    
    with open("backtest/phase3/manifest.json", 'r') as f:
        manifest = json.load(f)
        
    print("Manifest loaded.")
    
    sigs = sha256_file("test/phase3_validation/config/signal_registry.json")
    hyps = sha256_file("test/phase3_validation/config/hypothesis_registry.json")
    bases = sha256_file("test/phase3_validation/config/baseline_registry.json")
    
    if sigs != manifest['signalRegistrySHA256']:
        print("FAIL: Signal registry hash mismatch.")
        sys.exit(1)
        
    if hyps != manifest['hypothesisRegistrySHA256']:
        print("FAIL: Hypothesis registry hash mismatch.")
        sys.exit(1)
        
    if bases != manifest['baselineRegistrySHA256']:
        print("FAIL: Baseline registry hash mismatch.")
        sys.exit(1)
        
    print("All registry hashes match the manifest.")
    
    # Check data counts
    with open("backtest/phase3/snapshots_phase3.json", 'r') as f:
        snaps = json.load(f)
    print(f"Loaded {len(snaps)} snapshots.")
    
    with open("backtest/phase3/forward_labels_phase3.json", 'r') as f:
        labels = json.load(f)
    print(f"Loaded {len(labels)} labels.")
    
    if len(snaps) == 0 or len(labels) == 0:
        print("FAIL: Missing data.")
        sys.exit(1)
        
    print("Artifact validation PASS.")

if __name__ == '__main__':
    validate()
