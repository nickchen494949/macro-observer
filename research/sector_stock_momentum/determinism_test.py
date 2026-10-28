#!/usr/bin/env python3
"""determinism_test.py — identical code + data must give identical picks under different PYTHONHASHSEED values
(external audit finding #3). Runs the production preprocessing (shared with backtest.py) in two subprocesses."""
import json, os, subprocess, sys

CODE = r'''
import json, sys, pit_truncation_test as t
out = t.picks(None)
json.dump({k: {str(a.date()): b for a, b in v.items()} for k, v in out.items()}, open(sys.argv[1], 'w'))
'''


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    res = []
    for seed in ['0', '1', '12345']:
        f = f'/tmp/determinism_{seed}.json'
        subprocess.run([sys.executable, '-c', CODE, f], cwd=here, env={**os.environ, 'PYTHONHASHSEED': seed}, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        res.append(json.load(open(f)))
    ok = all(r == res[0] for r in res[1:])
    for k in res[0]:
        print(k, 'identical across seeds' if all(r[k] == res[0][k] for r in res[1:]) else 'DIFFERS')
    print('RESULT:', 'PASS' if ok else 'FAIL')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
