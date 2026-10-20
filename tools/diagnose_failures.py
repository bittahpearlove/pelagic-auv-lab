#!/usr/bin/env python3
"""Retrospective gate diagnosis of saved profiles. Never retunes a controller."""
import argparse
import csv
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import statistics
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('evaluation',ROOT/'lab/evaluation.py');ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)

def diagnose(directory,output):
    directory=Path(directory);output=Path(output);output.mkdir(parents=True,exist_ok=False)
    result=ev.evaluate_saved(directory);manifest=json.loads((directory/'manifest.json').read_text())
    definitions={s['id']:s for s in manifest['scenarios']}
    missed={(m['scenario_id'],m['direction']):m for m in result['metrics'] if m['mode']=='response' and m['reconstruction']=='forward' and m['boundary_failed']}
    details={k:dict(residual_only=0,proxy_only=0,both=0,neither=0) for k in missed}
    with (directory/'samples.csv').open() as f:
        for row in csv.DictReader(f):
            key=row['scenario_id'],row['direction']
            if key not in missed or row['mode']!='response' or not int(row['fresh']) or int(row['fit_status'])!=4:continue
            s=definitions[key[0]];t=float(row['ms'])/1000;boundary=ev.scenarios.boundary(t,s)
            if boundary is None or abs(float(row['probe_depth_m'])-boundary)>.15:continue
            residual=float(row['fit_residual_c'])>max(.04,3*manifest['policy']['noise_assumed_c'])
            proxy=float(row['gradient_sigma_proxy_cpm'])>max(1,.8*abs(float(row['estimated_gradient_cpm'])))
            details[key]['both' if residual and proxy else 'residual_only' if residual else 'proxy_only' if proxy else 'neither']+=1
    cases=[]
    for key,m in missed.items():
        s=definitions[key[0]];counts=m['transition_status_counts'];cases.append(dict(scenario_id=key[0],direction=key[1],coverage=m['coverage'],true_tau_s=s['true_tau_s'],noise_sigma_c=s['noise_sigma_c'],position_sigma_m=s['errors']['position_sigma_m'],dominant_status=max(counts,key=counts.get),transition_samples=m['transition_status_samples'],status_counts=counts,status4_checks=details[key],status_by_depth=m['status_by_depth']))
    sensitivity=[]
    for cap,penalty in [(.15,.15),(.30,.30),(.30,.60)]:
        for direction in ['descent','ascent']:
            a={m['scenario_id']:m for m in result['metrics'] if m['mode']=='response' and m['reconstruction']=='forward' and m['direction']==direction and m['boundary_expected']}
            b={m['scenario_id']:m for m in result['metrics'] if m['mode']=='medium' and m['reconstruction']=='raw' and m['direction']==direction}
            def loss(m):return min(m['boundary_depth_error_m'],cap) if m['boundary_depth_error_m'] is not None else penalty
            differences=[loss(a[k])-loss(b[k]) for k in a]
            sensitivity.append(dict(cap_m=cap,miss_penalty_m=penalty,direction=direction,pairs=len(differences),mean_difference_m=statistics.mean(differences) if differences else None))
    report=dict(analysis='Retrospective diagnostic reanalysis; not an independent test and not causal attribution.',original_manifest_sha256=hashlib.sha256((directory/'manifest.json').read_bytes()).hexdigest(),scoring_source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['lab/evaluation.py','lab/scenarios.py',str(Path(__file__).relative_to(ROOT))]},loss_default=ev.loss_settings(manifest['policy']),loss_sensitivity=sensitivity,missed_cases=cases,paired=result['paired'])
    (output/'diagnosis.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    (output/'scores.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return result,report

def plots(result,report,output):
    os.environ.setdefault('MPLCONFIGDIR','/tmp/pelagic-matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    modes=['fast','medium','slow','adaptive','response','ungated'];labels=['Fast / raw','Medium / raw','Slow / raw','Legacy / raw','Response / fit','Ungated / fit']
    colors=['#668ca3','#205e7a','#8cacc0','#acaf92','#259b81','#d39b57']
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for ax,direction in zip(axes,['descent','ascent']):
        counts=[];totals=[]
        for mode in modes:
            ms=[m for m in result['metrics'] if m['mode']==mode and m['direction']==direction and m['reconstruction']==('forward' if mode in ['response','ungated'] else 'raw') and m['boundary_expected']]
            counts.append(sum(not m['boundary_failed'] for m in ms));totals.append(len(ms))
        ax.bar(range(6),counts,color=colors);ax.set_ylim(0,max(totals)+3);ax.set_xticks(range(6),labels,rotation=35,ha='right');ax.set_ylabel('Detected / expected boundary scenarios');ax.set_title(direction.capitalize())
        for i,(n,total) in enumerate(zip(counts,totals)):ax.text(i,n+.4,f'{n}/{total}',ha='center')
        ax.spines[['top','right']].set_visible(False)
    fig.suptitle('v0.15 historical evaluation: detection availability matters');fig.savefig(output/'detection.png',dpi=180);plt.close(fig)
    cases=report['missed_cases'];names=list(ev.FIT_STATUS.values());palette=['#70c4a7','#78baf5','#eab878','#bda0ea','#ed9393','#e6dc87','#f38bc3','#dddddd']
    matrix=[];labels=[]
    for case in cases:
        row=[]
        for bin in case['status_by_depth']:row.append(names.index(max(bin['counts'],key=bin['counts'].get)) if bin['samples'] else 7)
        matrix.append(row);labels.append(case['scenario_id'].removeprefix('evaluation-')+' / '+case['direction'])
    fig,ax=plt.subplots(figsize=(10,5.6),layout='constrained');ax.imshow(matrix,aspect='auto',vmin=-.5,vmax=7.5,cmap=matplotlib.colors.ListedColormap(palette),extent=[.1,.9,len(cases)-.5,-.5]);ax.set_yticks(range(len(cases)),labels,fontsize=8);ax.set_xlabel('Estimated probe depth m');ax.set_title('All missed response/fit legs: dominant logged fit status by depth')
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=color,label=name.replace('_',' ')) for name,color in zip(names+['no samples'],palette)],loc='upper center',bbox_to_anchor=(.5,-.12),ncol=4,fontsize=8)
    fig.savefig(output/'rejection-depth.png',dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,4.4),layout='constrained')
    for i,direction in enumerate(['descent','ascent']):
        values=[v for v in report['loss_sensitivity'] if v['direction']==direction];ax.plot([v['miss_penalty_m']*100 for v in values],[v['mean_difference_m']*100 for v in values],'o-',label=direction)
    ax.axhline(0,color='grey',linestyle='--');ax.set_xlabel('Miss penalty cm (error cap 15, 30, 30 cm respectively)');ax.set_ylabel('Response minus medium mean loss, cm');ax.set_title('Retrospective penalty sensitivity; all expected boundary scenarios');ax.legend();ax.grid(alpha=.2);fig.savefig(output/'loss-sensitivity.png',dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,5),layout='constrained');unscored=0
    for mode,label,color in zip(modes,labels,colors):
        ms=[m for m in result['metrics'] if m['mode']==mode and m['reconstruction']==('forward' if mode in ['response','ungated'] else 'raw')]
        for full,marker in [(True,'o'),(False,'x')]:
            subset=[m for m in ms if (m['coverage']==1)==full and m['covered_profile_rmse_c'] is not None]
            ax.scatter([m['elapsed_s'] for m in subset],[m['covered_profile_rmse_c'] for m in subset],color=color,s=18,alpha=.55,marker=marker,label=label if full else None)
        unscored+=sum(m['covered_profile_rmse_c'] is None for m in ms)
    ax.set_xlabel('Actual mission duration s (same 180 s maximum allowance)');ax.set_ylabel('Covered-bin RMSE °C, conditional on sampled bins');ax.set_title(f'Accuracy and duration: circles full coverage; crosses partial; {unscored} legs unscored (zero bins)');ax.legend(fontsize=8,ncol=2);ax.grid(alpha=.2);fig.savefig(output/'accuracy-duration.png',dpi=180);plt.close(fig)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--plots',action='store_true');args=p.parse_args();r,d=diagnose(args.directory,args.output)
    if args.plots:plots(r,d,args.output)
    print('Saved retrospective diagnosis:',args.output,'missed legs:',len(d['missed_cases']))
