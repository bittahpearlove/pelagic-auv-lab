#!/usr/bin/env python3
"""Run versioned vertical trials; no USB connection or actuator output."""
import argparse
import importlib.util
import json
from pathlib import Path

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('auv_lab',root/'lab/server.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tau',type=float,default=2,help='True simulated tau; distinct from assumed tau')
    parser.add_argument('--assumed-tau',type=float)
    parser.add_argument('--tau-max',type=float)
    parser.add_argument('--epsilon',type=float)
    parser.add_argument('--error-cap',type=float,help='Boundary error cap in metres; freeze before evaluation')
    parser.add_argument('--miss-penalty',type=float,help='Missed-boundary penalty in metres, at least error cap')
    parser.add_argument('--noise',type=float,default=.005)
    parser.add_argument('--drop',type=float,default=3)
    parser.add_argument('--width',type=float,default=.07)
    parser.add_argument('--center',type=float,default=.5)
    parser.add_argument('--allowance',type=float,default=180)
    parser.add_argument('--repeats','--runs',dest='repeats',type=int,default=20)
    parser.add_argument('--seed',type=int,default=20261020)
    parser.add_argument('--split',choices=['development','evaluation','deterministic'],default='development')
    parser.add_argument('--varied',action='store_true',help='Predeclared randomized mixture of adverse conditions')
    parser.add_argument('--methods',nargs='+',choices=m.research.MODES,default=list(m.research.MODES))
    parser.add_argument('--policy-file',type=Path)
    parser.add_argument('--freeze-policy',type=Path,help='Write immutable defaults/explicit settings, then exit')
    parser.add_argument('--position-noise',type=float,default=0)
    parser.add_argument('--position-drift',type=float,default=0)
    parser.add_argument('--temperature-bias',type=float,default=0)
    parser.add_argument('--temperature-drift',type=float,default=0)
    parser.add_argument('--noise-rho',type=float,default=0)
    parser.add_argument('--quantum',type=float,default=0)
    parser.add_argument('--dropout',type=float,default=0)
    parser.add_argument('--dropout-burst',type=int,default=0)
    parser.add_argument('--jitter-ms',type=int,default=0)
    parser.add_argument('--boundary-drift',type=float,default=0)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    policy=dict(m.research.scenarios.DEFAULT_POLICY)
    if args.policy_file:
        frozen=json.loads(args.policy_file.read_text())
        policy=frozen['settings']
        if frozen.get('sha256')!=m.research.scenarios.policy_digest(policy):parser.error('Frozen policy digest mismatch')
        if args.split=='evaluation' and frozen.get('source_sha256')!=m.research.source_identity():parser.error('Research source changed after policy freeze; create a new development freeze')
    if args.split=='evaluation' and (not args.policy_file or any(v is not None for v in (args.assumed_tau,args.tau_max,args.epsilon,args.error_cap,args.miss_penalty))):
        parser.error('Evaluation requires --policy-file and forbids policy overrides; freeze development settings first')
    for key,value in [('tau_nominal_s',args.assumed_tau),('tau_max_s',args.tau_max),('epsilon_c',args.epsilon),('boundary_error_cap_m',args.error_cap),('boundary_miss_penalty_m',args.miss_penalty)]:
        if value is not None:policy[key]=value
    m.research.evaluation.loss_settings(policy)
    if args.freeze_policy:
        if args.freeze_policy.exists():parser.error('Refusing to overwrite a frozen policy')
        args.freeze_policy.parent.mkdir(parents=True,exist_ok=True)
        args.freeze_policy.write_text(json.dumps(dict(schema=1,selection_split='development',source_sha256=m.research.source_identity(),settings=policy,sha256=m.research.scenarios.policy_digest(policy)),indent=2)+'\n')
        print('Frozen policy:',args.freeze_policy);raise SystemExit(0)
    params=dict(m.DEFAULTS,tau=args.tau,noise=args.noise,drop=args.drop,width=args.width,center=args.center)
    errors=dict(position_sigma_m=args.position_noise,position_drift_m_s=args.position_drift,
                temperature_bias_c=args.temperature_bias,temperature_drift_c_sqrt_s=args.temperature_drift,
                noise_rho=args.noise_rho,temperature_quantum_c=args.quantum,dropout_probability=args.dropout,
                dropout_burst_steps=args.dropout_burst,jitter_ms=args.jitter_ms,boundary_drift_mps=args.boundary_drift)
    directory=args.output or m.research.new_run_directory(root/'output/experiments/research')
    lab=m.Lab()
    with lab.lock:
        result=m.research.run_comparison(lab.core,params,lab.native_config,args.allowance,args.repeats,args.seed,
            policy=policy,split=args.split,varied=args.varied,errors=errors,methods=args.methods,output=directory)
    for effect in result['paired']:
        if effect['expected_boundary_pairs']:
            value=effect['conditional_mean_difference_m']
            print(effect['contrast'],effect['direction'],'all-expected loss delta',effect['failure_aware_mean_difference_m'],'m; conditional delta',f'{value:.5f} m' if value is not None else 'undefined',
                  'joint valid',effect['joint_valid_pairs'],'/',effect['expected_boundary_pairs'],
                  'failures method/baseline',effect['method_failures'],effect['baseline_failures'])
    print('Exploratory' if args.repeats<20 else 'Scenario study','— no physical or statistical superiority assumed.')
    print('Saved',directory)
