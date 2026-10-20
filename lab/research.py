"""Production Nano algorithm in reproducible, truth-separated vertical trials."""
import csv
import ctypes
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import time


def _module(name):
    spec=importlib.util.spec_from_file_location('pelagic_'+name,Path(__file__).with_name(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

scenarios=_module('scenarios');evaluation=_module('evaluation')
MODES=('adaptive','fast','slow','medium','response','ungated')
MODE_IDS={name:i for i,name in enumerate(MODES)}
SHAPES={name:i for i,name in enumerate(scenarios.SHAPES)}
BIN_M=.025


def bind(core):
    ptr=ctypes.POINTER(ctypes.c_float)
    core.lab_trial_tick.argtypes=[ctypes.c_uint32,ctypes.c_float,ptr,ptr]
    core.lab_trial_config.argtypes=[ctypes.c_int,ctypes.c_float,ctypes.c_float,ctypes.c_float,ctypes.c_float,ctypes.c_uint32]
    core.lab_version.restype=ctypes.c_char_p


def source_identity():
    root=Path(__file__).resolve().parent.parent
    paths=sorted((root/'firmware/auv_nano').glob('*.h'))+[root/'firmware/auv_nano/auv_nano.ino',Path(__file__),Path(__file__).with_name('scenarios.py'),Path(__file__).with_name('evaluation.py'),Path(__file__).with_name('controller_bridge.cpp')]
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def new_run_directory(base):
    directory=Path(base)/('run-'+str(time.time_ns()))
    directory.mkdir(parents=True,exist_ok=False);return directory


def _trial(core,s,mode,policy,budget_s,repeat):
    allowed_ms=round(budget_s*1000)
    if not core.lab_trial_config(MODE_IDS[mode],policy['tau_nominal_s'],policy['tau_max_s'],policy['epsilon_c'],policy['noise_assumed_c'],allowed_ms-5000):
        raise ValueError('Native controller rejected trial configuration')
    pipeline=scenarios.ObservationPipeline(s,mode);e=s['errors'];f=s['field']
    depth=velocity=command=energy=travel=0.
    probe=scenarios.temperature(f['profile_x'],e['probe_offset_m'],0,s)
    last=dict(acquired_ms=0,temperature_c=probe+e['temperature_bias_c']+s['noise_sigma_c']*pipeline.measurement_rng.gauss(0,1),depth_m=e['position_bias_m'],velocity_mps=0.)
    ms=0;previous_state=1
    while ms<allowed_ms:
        interval=min(pipeline.interval_ms(),allowed_ms-ms);dt=interval/1000
        before=depth
        steps=max(1,math.ceil(dt/.01));subdt=dt/steps
        for sub in range(steps):
            t=(ms+(sub+1)*interval/steps)/1000
            gain=e['thrust_gain']*(e['ascent_gain'] if command<0 else 1)
            velocity+=(command*gain-e['drag']*velocity-.01+e['acceleration_bias'])*subdt
            depth+=velocity*subdt
            if depth<=0:depth=velocity=0.
            truth=scenarios.temperature(f['profile_x'],depth+e['probe_offset_m'],t,s)
            tau=s['true_tau_s']*(1+e['flow_tau_factor']*abs(velocity))
            probe+=(truth-probe)*(1-math.exp(-subdt/tau))
            energy+=12*abs(command)*4*subdt
        ms+=interval;travel+=abs(depth-before)
        observation=pipeline.observe(ms,probe,depth,velocity,dt);fresh=observation is not None
        if fresh:last=observation
        inputs=(ctypes.c_float*9)(last['acquired_ms'],last['temperature_c'],last['depth_m'],last['velocity_mps'],12,abs(command)*4,0,1,0)
        out=(ctypes.c_float*30)();core.lab_trial_tick(ms,dt,inputs,out)
        # External experiment cap includes arming. Never extend it for a method.
        cap_abort=ms>=allowed_ms and int(out[0]) not in (5,6)
        if cap_abort:
            core.lab_trial_stop();core.lab_trial_tick(ms,0,inputs,out)
        state,faults=int(out[0]),int(out[1])
        leg={2:'descent',4:'ascent'}.get(previous_state,'settle_or_hold')
        row=dict(sample_schema=2,scenario_id=s['id'],split=s['split'],repeat=repeat,mode=mode,
            ms=ms,acquired_ms=last['acquired_ms'],sample_age_ms=ms-last['acquired_ms'],fresh=int(fresh),
            direction=leg,depth_m=last['depth_m'],estimated_probe_depth_m=last['depth_m']+e['calibrated_probe_offset_m'],
            true_depth_m=depth,probe_depth_m=depth+e['probe_offset_m'],temperature_raw_c=last['temperature_c'],
            probe_state_c=probe,reference_temperature_c=truth,true_gradient_cpm=scenarios.gradient(f['profile_x'],depth+e['probe_offset_m'],ms/1000,s),
            vertical_mps=last['velocity_mps'],true_vertical_mps=velocity,command_next=float(out[2]),
            target_depth_m=float(out[3]),speed_limit_mps=float(out[4]),speed_tracking_error_mps=abs(velocity)-float(out[4]),
            state=state,faults=faults,transition=int(out[7]),region_valid=int(out[9]),region_low_m=float(out[10]),region_high_m=float(out[11]),
            estimated_temperature_c=float(out[12]),estimated_gradient_cpm=float(out[13]),fit_residual_c=float(out[14]),
            fit_valid=int(out[15]),policy_reason=int(out[16]),gradient_sigma_proxy_cpm=float(out[17]),condition_proxy=float(out[18]),
            depth_span_m=float(out[19]),assumed_tau_s=float(out[20]),tau_max_s=float(out[21]),reached_bottom=int(out[22]),
            budget_return=int(out[23]),geometry_valid=int(out[24]),fit_status=int(out[25]),model_speed_limit_mps=float(out[26]),
            approximate_lag_error_c=float(out[27]),support_depth_m=float(out[28]),support_temperature_c=float(out[29]),
            actual_tau_s=tau,path_m=travel,toy_propulsion_j=energy,noise_sigma_c=s['noise_sigma_c'],
            field_shape=f['shape'],profile_x_m=f['profile_x'],field_center_m=f['center'],field_width_m=f['width'],field_drop_c=f['drop'],
            allowance_s=budget_s,seed=s['seed'],cap_abort=int(cap_abort))
        yield row
        command,previous_state=float(out[2]),state
        if state in (5,6):break


def run_comparison(core,params,config,budget_s=180,repeats=3,seed=20261020,*,policy=None,split='development',varied=False,errors=None,methods=None,output=None,scenario_set=None):
    if not math.isfinite(budget_s) or not 10<=budget_s<=600:raise ValueError('Trial allowance must be 10–600 s')
    bind(core);p=dict(scenarios.DEFAULT_POLICY,**(policy or {}))
    evaluation.loss_settings(p)
    methods=tuple(methods or MODES)
    if not methods or len(set(methods))!=len(methods) or any(m not in MODE_IDS for m in methods):raise ValueError('Invalid methods')
    if not(.1<=p['tau_nominal_s']<=8 and p['tau_nominal_s']<=p['tau_max_s']<=16 and 0<p['epsilon_c']<=5 and 0<=p['noise_assumed_c']<=.5):raise ValueError('Invalid frozen policy')
    definitions=scenario_set or scenarios.generate(params,repeats,seed,split,varied,errors)
    for s in definitions:scenarios.validate(s)
    directory=Path(output).resolve() if output else None
    if directory:
        directory.mkdir(parents=True,exist_ok=True)
        if any(directory.iterdir()):raise ValueError('Experiment directory must be new and empty')
    manifest=dict(schema=2,firmware=core.lab_version().decode(),seed=seed,split=split,allowance_s=budget_s,
        methods=list(methods),scenarios=definitions,policy=p,policy_sha256=scenarios.policy_digest(p),controller_config=dict(config),
        source_sha256=source_identity(),protocol='One profile per method/scenario. Same maximum allowance including 5 s arming; early completion leaves unused time. Model-based return reserve is common to methods.',
        pairing='Same field, clock and channel realization by scenario; independent digital measurement-noise streams by method. Raw samples are not independent experimental replicates.',
        primary_contrast='Failure-aware boundary loss: response/forward minus medium/raw by direction; detection counts and conditional error remain separate. Loss parameters frozen in policy.',
        reconstruction='Raw digitized samples versus forward-fit support temperature at its filtered-regressor support depth. Current-depth extrapolation is diagnostic, not a hidden truth shift.',
        scoring='Median bins on fixed 0.10–0.90 m grid; full-profile RMSE undefined if any required bin is missing. Boundary: strongest binned temperature-gradient peak in 0.20–0.80 m, >=2 C/m, optional local parabolic interpolation. Failures remain in denominators.',
        uncertainty='Scenario-paired bootstrap conditional on joint boundary success. Failure counts and coverage accompany conditional errors; no calibrated onboard confidence interval is claimed.')
    if directory:(directory/'manifest.json').write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n')
    rows=[];metrics=[];trials=[];preview=[];stream=None;writer=None
    try:
        if directory:stream=(directory/'samples.csv').open('w',newline='')
        for repeat,s in enumerate(definitions,1):
            for mode in methods:
                trial_rows=[]
                for row in _trial(core,s,mode,p,budget_s,repeat):
                    trial_rows.append(row)
                    if stream:
                        if writer is None:writer=csv.DictWriter(stream,fieldnames=list(row));writer.writeheader()
                        writer.writerow(row)
                    else:rows.append(row)
                last=trial_rows[-1]
                trials.append(dict(scenario_id=s['id'],repeat=repeat,mode=mode,allowance_s=budget_s,elapsed_s=last['ms']/1000,
                    unused_allowance_s=budget_s-last['ms']/1000,complete=last['state']==5,full_profile_complete=bool(last['state']==5 and last['reached_bottom']),
                    censored=bool(last['cap_abort'] or last['faults']&128 or (last['budget_return'] and not last['reached_bottom'])),
                    budget_return=bool(last['budget_return']),faults=last['faults'],path_m=last['path_m'],toy_propulsion_j=last['toy_propulsion_j']))
                metrics.extend(evaluation.score_trial(trial_rows,s,p))
                if repeat==1:
                    stride=max(1,len(trial_rows)//350)
                    preview.extend(trial_rows[::stride])
                if stream:stream.flush()
    finally:
        if stream:stream.close()
    evaluation.shared_bins(metrics)
    paired=evaluation.paired_effects(metrics,seed)
    boundary=scenarios.boundary(0,definitions[0]) if len(definitions) else None
    result=dict(schema=2,firmware=manifest['firmware'],allowance_s=budget_s,repeats=len(definitions),seed=seed,
        split=split,params=dict(params),controller_config=dict(config),policy=p,manifest=manifest,reference_boundary_m=boundary,
        reference='Ideal simulated field; not an independently calibrated physical reference.',
        design=manifest['protocol'],limitations=['First-order static local-linear estimator; moving/curved fields and wrong tau can invalidate it.',
            'Onboard residual/conditioning/sigma are reliability proxies, not calibrated confidence intervals.',
            'Toy planar/vertical dynamics and command-based energy; no physical vehicle or wet-probe validation.',
            'Conditional bootstrap intervals require joint success; failure-aware loss includes every expected-boundary scenario. Rejection reasons are associations, not causal proof.'],
        trials=trials,metrics=metrics,paired=paired,rows=rows,preview=preview,
        samples_path=str(directory/'samples.csv') if directory else None,run_directory=str(directory) if directory else None)
    if directory:save_comparison(result,directory)
    return result


def comparison_csv(result):
    if not result:return ''
    if result.get('samples_path'):return Path(result['samples_path']).read_text()
    if not result['rows']:return ''
    output=io.StringIO();writer=csv.DictWriter(output,fieldnames=list(result['rows'][0]));writer.writeheader();writer.writerows(result['rows']);return output.getvalue()


def save_comparison(result,directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    if not result.get('samples_path'):
        (directory/'samples.csv').write_text(comparison_csv(result))
        (directory/'manifest.json').write_text(json.dumps(result['manifest'],indent=2,allow_nan=False)+'\n')
    summary={k:v for k,v in result.items() if k not in ('rows','preview')}
    (directory/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    if result['metrics']:
        with (directory/'metrics.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(result['metrics'][0]));writer.writeheader();writer.writerows(result['metrics'])
