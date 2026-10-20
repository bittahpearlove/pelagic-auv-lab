#!/usr/bin/env python3
"""Recompute scores from saved observations; optionally create standalone figures."""
import argparse
import csv
import importlib.util
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('evaluation',ROOT/'lab/evaluation.py')
evaluation=importlib.util.module_from_spec(spec);spec.loader.exec_module(evaluation)

def figures(directory,destination):
    os.environ.setdefault('MPLCONFIGDIR','/tmp/pelagic-matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    with (directory/'samples.csv').open() as stream:
        reader=csv.DictReader(stream);first=None;groups={}
        for row in reader:
            if first is None:first=row['scenario_id']
            if row['scenario_id']!=first:continue
            groups.setdefault(row['mode'],[]).append(row)
    fig,axes=plt.subplots(4,1,figsize=(10,10),sharex=True,layout='constrained')
    for mode,rows in groups.items():
        step=max(1,len(rows)//1200);rs=rows[::step];ts=[float(r['ms'])/1000 for r in rs]
        axes[0].plot(ts,[float(r['temperature_raw_c']) for r in rs],alpha=.6,label=mode+' raw')
        if mode=='response':
            axes[0].plot(ts,[float(r['estimated_temperature_c']) if float(r['fit_valid']) else float('nan') for r in rs],color='black',label='response valid estimate')
            axes[0].plot(ts,[float(r['reference_temperature_c']) for r in rs],'k--',label='evaluator reference')
            axes[1].plot(ts,[float(r['estimated_gradient_cpm']) for r in rs],label='estimated gradient')
            axes[1].plot(ts,[float(r['true_gradient_cpm']) for r in rs],'--',label='true gradient, evaluator only')
            axes[1].plot(ts,[float(r['fit_residual_c']) for r in rs],label='residual °C')
            axes[2].plot(ts,[float(r['speed_limit_mps']) for r in rs],label='requested speed')
            axes[2].plot(ts,[abs(float(r['true_vertical_mps'])) for r in rs],label='achieved |speed|')
            axes[3].step(ts,[float(r['fit_valid']) for r in rs],label='fit valid')
            axes[3].step(ts,[float(r['policy_reason']) for r in rs],label='decision reason')
    for ax,label in zip(axes,['Temperature °C','Gradient °C/m / residual °C','Speed m/s','Validity / reason code']):
        ax.set_ylabel(label);ax.grid(alpha=.25);ax.legend(fontsize=7,ncol=3)
    axes[-1].set_xlabel('Elapsed experiment time s');fig.suptitle('First scenario: '+first+' — simulation only')
    fig.savefig(destination/'diagnostics.png',dpi=160);fig.savefig(destination/'diagnostics.pdf');plt.close(fig)
    result=evaluation.evaluate_saved(directory)
    effects=result['paired'];fig,ax=plt.subplots(figsize=(10,6),layout='constrained')
    labels=[]
    for i,e in enumerate(effects):
        labels.append(e['contrast']+' / '+e['direction']+f" ({e['joint_valid_pairs']}/{e['expected_boundary_pairs']} joint detections)")
        value=e['conditional_mean_difference_m'];ci=e['conditional_bootstrap_95_m']
        if value is not None:
            ax.plot(value*100,i,'o');
            if ci:ax.plot([v*100 for v in ci],[i,i],color='black')
    ax.set_yticks(range(len(effects)),labels,fontsize=8);ax.axvline(0,color='grey',linestyle='--');ax.set_xlabel('Conditional paired boundary-error difference, cm (negative favours response)');ax.grid(axis='x',alpha=.2)
    ax.set_title('Whole-scenario bootstrap; conditional on both detectors succeeding')
    fig.savefig(destination/'paired-effects.png',dpi=160);fig.savefig(destination/'paired-effects.pdf');plt.close(fig)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path);parser.add_argument('--plots',action='store_true');parser.add_argument('--output',type=Path)
    args=parser.parse_args();dest=args.output or args.directory/'reevaluated';dest.mkdir(parents=True,exist_ok=False)
    result=evaluation.evaluate_saved(args.directory)
    (dest/'scores.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    original=json.loads((args.directory/'summary.json').read_text())
    # CSV preserves floats exactly, but boolean counters re-read as numeric 0/1.
    assert result['metrics']==original['metrics'],'Saved-data scores differ from original'
    assert result['paired']==original['paired'],'Saved-data paired effects differ from original'
    if args.plots:figures(args.directory,dest)
    print('Saved-data evaluation matches original:',dest)
