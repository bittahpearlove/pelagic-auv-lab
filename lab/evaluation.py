"""Offline scoring; truth is available here, never to firmware decisions."""
import csv
import importlib.util
import json
import math
from pathlib import Path
import random
import statistics

_spec=importlib.util.spec_from_file_location('pelagic_scenarios',Path(__file__).with_name('scenarios.py'))
scenarios=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(scenarios)


def _rmse(values):return math.sqrt(sum(v*v for v in values)/len(values)) if values else None

def score_trial(rows,scenario,policy):
    width=policy['bin_m'];lo,hi=policy['required_depth_range_m'];total=round((hi-lo)/width)
    metrics=[]
    for direction in ('descent','ascent'):
        selected=[r for r in rows if r['direction']==direction and r['fresh']]
        for reconstruction in ('raw','forward'):
            bins={}
            for r in selected:
                if reconstruction=='forward' and not r['fit_valid']:continue
                z=r['estimated_probe_depth_m'] if reconstruction=='raw' else r['support_depth_m']+scenario['errors']['calibrated_probe_offset_m']
                value=r['temperature_raw_c'] if reconstruction=='raw' else r['support_temperature_c']
                if lo<=z<hi:
                    bins.setdefault(int((z-lo)/width),[]).append((value,r['ms']/1000))
            curve={i:statistics.median(v[0] for v in records) for i,records in bins.items()}
            times={i:statistics.median(v[1] for v in records) for i,records in bins.items()}
            errors={i:value-scenarios.temperature(scenario['field']['profile_x'],lo+(i+.5)*width,times[i],scenario) for i,value in curve.items()}
            gradients={i:(curve[i+1]-curve[i-1])/(2*width) for i in curve if i-1 in curve and i+1 in curve}
            left,right=policy['boundary_search_m'];threshold=policy['gradient_threshold_cpm']
            candidates=[i for i,g in gradients.items() if left<=lo+(i+.5)*width<=right and abs(g)>=threshold]
            peak=max(candidates,key=lambda i:abs(gradients[i])) if candidates else None
            estimated=None;reference=None;peak_time=None
            if peak is not None:
                offset=0.
                if peak-1 in gradients and peak+1 in gradients:
                    a,b,c=(abs(gradients[peak+j]) for j in (-1,0,1));denom=a-2*b+c
                    if denom< -1e-8:offset=max(-.5,min(.5,.5*(a-c)/denom))
                estimated=lo+(peak+.5+offset)*width;peak_time=times[peak]
                reference=scenarios.boundary(peak_time,scenario)
            expected=scenarios.boundary(0,scenario) is not None
            boundary_error=abs(estimated-reference) if estimated is not None and reference is not None else None
            error_values=list(errors.values())
            transition_errors=[value for i,value in errors.items() if scenarios.boundary(times[i],scenario) is not None and abs(lo+(i+.5)*width-scenarios.boundary(times[i],scenario))<=.15]
            # Count separated gradient peaks; the strongest supplies the declared estimate.
            peaks=[]
            for i in sorted(candidates,key=lambda i:abs(gradients[i]),reverse=True):
                if all(abs(i-j)*width>=.075 for j in peaks):peaks.append(i)
            path=sum(abs(b['true_depth_m']-a['true_depth_m']) for a,b in zip(selected,selected[1:]))
            metrics.append(dict(scenario_id=scenario['id'],mode=rows[0]['mode'],direction=direction,
                reconstruction=reconstruction,repeat=rows[0]['repeat'],samples=len(selected),
                occupied_bins=len(curve),total_bins=total,coverage=len(curve)/total,
                full_profile_rmse_c=_rmse(error_values) if len(curve)==total else None,
                covered_profile_rmse_c=_rmse(error_values),transition_rmse_c=_rmse(transition_errors),
                common_depth_rmse_c=None,common_bins=0,boundary_expected=expected,
                boundary_depth_estimate_m=estimated,reference_boundary_m=reference,
                boundary_depth_error_m=boundary_error,boundary_failed=expected and boundary_error is None,
                false_boundary_peaks=len(peaks) if not expected else max(0,len(peaks)-1),
                false_peaks_per_m=(len(peaks) if not expected else max(0,len(peaks)-1))/path if path>.01 else None,
                peak_acquisition_s=peak_time,elapsed_s=rows[-1]['ms']/1000,
                transition_fraction=sum(r['transition'] for r in selected)/len(selected) if selected else None,
                _errors=errors))
    return metrics


def shared_bins(metrics):
    groups={}
    for metric in metrics:groups.setdefault((metric['scenario_id'],metric['direction'],metric['reconstruction']),[]).append(metric)
    for group in groups.values():
        common=set.intersection(*(set(m['_errors']) for m in group))
        for m in group:
            m['common_bins']=len(common);m['common_depth_rmse_c']=_rmse([m['_errors'][i] for i in common])
    for m in metrics:m.pop('_errors',None)


def paired_effects(metrics,seed=8128,resamples=1000):
    result=[]
    contrasts=[('combined_vs_medium','response','forward','medium','raw'),
               ('combined_vs_legacy','response','forward','adaptive','raw'),
               ('adaptation_only','response','forward','medium','forward'),
               ('estimator_only','response','forward','response','raw'),
               ('confidence_gate','response','forward','ungated','forward')]
    for label,method,recon,baseline,base_recon in contrasts:
        for direction in ('descent','ascent'):
            left={m['scenario_id']:m for m in metrics if m['mode']==method and m['reconstruction']==recon and m['direction']==direction}
            right={m['scenario_id']:m for m in metrics if m['mode']==baseline and m['reconstruction']==base_recon and m['direction']==direction}
            ids=sorted(set(left)&set(right));expected=[s for s in ids if left[s]['boundary_expected']]
            differences=[left[s]['boundary_depth_error_m']-right[s]['boundary_depth_error_m'] for s in expected if left[s]['boundary_depth_error_m'] is not None and right[s]['boundary_depth_error_m'] is not None]
            interval=None
            if len(differences)>=2:
                rng=random.Random(scenarios.stream_seed(seed,label+direction));n=len(differences)
                bootstrap=sorted(sum(rng.choice(differences) for _ in range(n))/n for _ in range(resamples))
                interval=[bootstrap[int(.025*(resamples-1))],bootstrap[int(.975*(resamples-1))]]
            result.append(dict(contrast=label,direction=direction,scenario_pairs=len(ids),expected_boundary_pairs=len(expected),
                joint_valid_pairs=len(differences),method_failures=sum(left[s]['boundary_depth_error_m'] is None for s in expected),
                baseline_failures=sum(right[s]['boundary_depth_error_m'] is None for s in expected),
                conditional_mean_difference_m=statistics.mean(differences) if differences else None,
                conditional_bootstrap_95_m=interval,exploratory=len(differences)<20,
                interpretation='Negative favours response method; interval is conditional on BOTH detectors succeeding, not all missions.'))
    return result


def evaluate_saved(directory):
    directory=Path(directory);manifest=json.loads((directory/'manifest.json').read_text())
    definitions={s['id']:s for s in manifest['scenarios']};metrics=[];group=[];key=None
    text={'mode','scenario_id','direction','field_shape','split'}
    with (directory/'samples.csv').open() as stream:
        for source in csv.DictReader(stream):
            row={k:(v if k in text else float(v)) for k,v in source.items()}
            next_key=(row['scenario_id'],row['mode'])
            if group and next_key!=key:
                metrics.extend(score_trial(group,definitions[group[0]['scenario_id']],manifest['policy']));group=[]
            group.append(row);key=next_key
    if group:metrics.extend(score_trial(group,definitions[group[0]['scenario_id']],manifest['policy']))
    shared_bins(metrics)
    return dict(metrics=metrics,paired=paired_effects(metrics,manifest['seed']))
