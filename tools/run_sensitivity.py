#!/usr/bin/env python3
"""Predeclared development-only one-factor checks, not final evaluation tuning."""
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('lab',ROOT/'lab/server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
if __name__=='__main__':
    lab=m.Lab();scenarios=[];index=0
    cases=[('true_tau_s',[.3,1,2,4]),('width',[.025,.05,.1]),('noise',[0,.02,.05,.1]),('position_sigma_m',[0,.01,.04]),('boundary_drift_mps',[-.005,0,.005]),('dropout_burst_steps',[0,3,12])]
    for key,values in cases:
        for value in values:
            index+=1;p=dict(m.DEFAULTS);e={}
            if key=='true_tau_s':p['tau']=value
            elif key in p:p[key]=value
            else:e[key]=value
            if key=='dropout_burst_steps':e['dropout_probability']=.05
            s=m.research.scenarios.scenario(p,70000+index,'development',e);s['id']=f'development-ofat-{key}-{value}';scenarios.append(s)
    out=m.research.new_run_directory(ROOT/'output/experiments/sensitivity')
    result=m.research.run_comparison(lab.core,m.DEFAULTS,lab.native_config,scenario_set=scenarios,output=out)
    print('Predeclared one-factor development scenarios:',len(scenarios),'saved',out)
