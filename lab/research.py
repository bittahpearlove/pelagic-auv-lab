"""Reproducible vertical-profile trials using the production C++ controller.
The reference is ideal simulator water. It never enters the controller inputs.
"""
from collections import defaultdict
import ctypes
import csv
import io
import json
import math
from pathlib import Path
import random

MODES = ('adaptive', 'fast', 'slow')
SHAPES = {'layer': 0, 'tilted': 1, 'front': 2, 'patch': 3, 'combined': 4}
BIN_M = .025


def run_comparison(core, params, config, budget_s=180, repeats=3, seed=20261020):
    if not 10 <= budget_s <= 600 or int(repeats) != repeats or not 1 <= repeats <= 10:
        raise ValueError('Trial allowance must be 10–600 s; repeats 1–10')
    core.lab_trial_tick.argtypes = [ctypes.c_uint32, ctypes.c_float,
                                    ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float)]
    p = dict(params)
    def water(z):
        return float(core.lab_water(p['profile_x'], z, SHAPES[p['shape']], p['center'], p['width'], p['drop']))
    # One consistently defined boundary: unique mid-drop isotherm in this column.
    # A lateral front, uniform water or multiple crossings has no such metric.
    midpoint = config['water_surface_c'] - p['drop'] / 2
    crossings = []
    if p['drop'] > .001:
        previous = water(0) - midpoint
        for i in range(1, 1001):
            z = i / 1000
            value = water(z) - midpoint
            if previous * value < 0 or (value == 0 and previous != 0):
                crossings.append(z - .001 + .001 * abs(previous) / (abs(previous) + abs(value)))
            previous = value
    boundary = crossings[0] if len(crossings) == 1 else None
    rows, trials, groups = [], [], {}
    steps = int(round(budget_s / .05))
    for repeat in range(int(repeats)):
        for mode, name in enumerate(MODES):
            rng = random.Random(seed + repeat) # paired noise realizations at acquisition times
            core.lab_trial_reset(mode)
            depth = velocity = command = energy = travel = 0.
            probe = water(0)
            previous_state = 1
            trial_rows = []
            for step in range(1, steps + 1):
                ms = step * 50
                velocity += (command * 1.2 - velocity * 1.5 - .01) * .05
                before = depth
                depth += velocity * .05
                if depth <= 0: depth = velocity = 0.
                travel += abs(depth - before)
                truth = water(depth)
                probe += (truth - probe) * (1 - math.exp(-.05 / p['tau']))
                temperature = probe + rng.gauss(0, p['noise'])
                energy += 12 * abs(command) * 4 * .05
                inputs = (ctypes.c_float * 9)(ms, temperature, depth, velocity, 12, abs(command)*4, 0, 1, 0)
                out = (ctypes.c_float * 12)()
                core.lab_trial_tick(ms, .05, inputs, out)
                state, faults = int(out[0]), int(out[1])
                # Direction belongs to the acquisition interval, not the next command.
                leg = {2:'descent', 4:'ascent'}.get(previous_state, 'settle_or_hold')
                row = dict(repeat=repeat+1, mode=name, ms=ms, direction=leg,
                           depth_m=depth, probe_depth_m=depth, temperature_raw_c=temperature,
                           reference_temperature_c=truth, vertical_mps=velocity,
                           command_next=float(out[2]), speed_limit_mps=float(out[4]),
                           state=state, faults=faults, transition=int(out[7]),
                           region_valid=int(out[9]), region_low_m=float(out[10]), region_high_m=float(out[11]),
                           path_m=travel, toy_propulsion_j=energy,
                           actual_tau_s=p['tau'], assumed_tau_s=config['probe_tau_s'],
                           noise_sigma_c=p['noise'], field_shape=p['shape'], profile_x_m=p['profile_x'],
                           field_center_m=p['center'], field_width_m=p['width'], field_drop_c=p['drop'],
                           allowance_s=budget_s, seed=seed+repeat)
                trial_rows.append(row)
                command, previous_state = float(out[2]), state
                if state in (5, 6): break
            rows.extend(trial_rows)
            trials.append(dict(repeat=repeat+1, mode=name, allowance_s=budget_s,
                               elapsed_s=ms/1000, unused_allowance_s=budget_s-ms/1000,
                               complete=state==5, censored=state not in (5,6), faults=faults,
                               path_m=travel, toy_propulsion_j=energy))
            for leg in ('descent', 'ascent'):
                selected = [r for r in trial_rows if r['direction']==leg]
                bins = defaultdict(list)
                for r in selected:
                    if .1 <= r['probe_depth_m'] < 1.0:
                        bins[int((r['probe_depth_m']-.1)/BIN_M)].append(r)
                groups[(repeat, name, leg)] = (selected, bins)
    metrics = []
    for repeat in range(int(repeats)):
        for leg in ('descent', 'ascent'):
            common = set.intersection(*(set(groups[(repeat, name, leg)][1]) for name in MODES))
            for name in MODES:
                selected, bins = groups[(repeat, name, leg)]
                errors, transition_errors = [], []
                for index in sorted(common):
                    values = bins[index]
                    error = sum(r['temperature_raw_c']-r['reference_temperature_c'] for r in values)/len(values)
                    errors.append(error)
                    if boundary is not None and abs(.1+(index+.5)*BIN_M-boundary) <= .15:
                        transition_errors.append(error)
                measured_crossings = []
                if boundary is not None:
                    for a,b in zip(selected, selected[1:]):
                        ta,tb = a['temperature_raw_c']-midpoint,b['temperature_raw_c']-midpoint
                        if ta*tb<0:
                            measured_crossings.append(a['probe_depth_m']+(b['probe_depth_m']-a['probe_depth_m'])*abs(ta)/(abs(ta)+abs(tb)))
                # Noise can produce several crossings: use first in travel order,
                # never the crossing nearest truth. Report the ambiguity count.
                error_depth = abs(measured_crossings[0]-boundary) if measured_crossings else None
                rmse = lambda values: math.sqrt(sum(v*v for v in values)/len(values)) if values else None
                metrics.append(dict(repeat=repeat+1, mode=name, direction=leg, samples=len(selected),
                                    occupied_bins=len(bins), common_bins=len(common), total_bins=36,
                                    common_depth_rmse_c=rmse(errors), transition_rmse_c=rmse(transition_errors),
                                    boundary_depth_error_m=error_depth, measured_crossings=len(measured_crossings),
                                    transition_fraction=sum(r['transition'] for r in selected)/len(selected) if selected else None))
    return dict(schema=1, firmware='v0.13', allowance_s=budget_s, repeats=int(repeats), seed=seed,
                params=p, controller_config=dict(config), reference_boundary_m=boundary,
                reference='Ideal instantaneous simulator field at the probe; not an independent tank instrument',
                design='One descent/hold/ascent per trial, equal maximum allowance; early finishes leave unused time. Three paired-noise repeats by default. No relocation or repeated cycles are hidden in the budget.',
                limitations=['Exact simulated position; zero pressure/probe offset; static water; no mixing or navigation error.',
                             'Temperature RMSE uses the same occupied 2.5 cm bins for all three modes, separately by direction; report coverage alongside error.',
                             'Boundary = unique mid-drop isotherm; first measured crossing in travel order; null when undefined or uncrossed.',
                             'Energy is a command-based propulsion proxy, not measured battery energy; recovery after surface completion is excluded.',
                             'The controller assumes its configured tau; actual tau may differ. No deconvolution or truth feedback.'],
                trials=trials, metrics=metrics, rows=rows)


def comparison_csv(result):
    if not result or not result['rows']: return ''
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(result['rows'][0]))
    writer.writeheader(); writer.writerows(result['rows'])
    return output.getvalue()


def save_comparison(result, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory/'samples.csv').write_text(comparison_csv(result))
    (directory/'summary.json').write_text(json.dumps({k:v for k,v in result.items() if k!='rows'}, indent=2, allow_nan=False)+'\n')
