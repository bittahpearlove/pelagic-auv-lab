#!/usr/bin/env python3
"""Offline proposal experiment. No USB connection or actuator output."""
import argparse
import importlib.util
from pathlib import Path

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('auv_lab', root/'lab/server.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tau', type=float, default=2)
    parser.add_argument('--noise', type=float, default=.005)
    parser.add_argument('--drop', type=float, default=3)
    parser.add_argument('--allowance', type=float, default=180)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--output', type=Path, default=root/'output/experiments/profile_comparison')
    args = parser.parse_args()
    for key in ('tau','noise','drop'):
        lo,hi=m.LIMITS[key]
        if not lo<=getattr(args,key)<=hi: parser.error('Invalid '+key)
    lab=m.Lab()
    with lab.lock:
        params=dict(m.DEFAULTS,tau=args.tau,noise=args.noise,drop=args.drop)
        result=m.research.run_comparison(lab.core,params,lab.native_config,args.allowance,args.repeats)
        m.research.save_comparison(result,args.output)
    for mode in m.research.MODES:
        for direction in ('descent','ascent'):
            rows=[r for r in result['metrics'] if r['mode']==mode and r['direction']==direction]
            values=[r['common_depth_rmse_c'] for r in rows if r['common_depth_rmse_c'] is not None]
            error=f'{sum(values)/len(values):.4f} C' if values else 'undefined'
            print(f'{mode:8} {direction:7} common-depth RMSE {error}')
    print('Saved',args.output/'summary.json','and samples.csv')
