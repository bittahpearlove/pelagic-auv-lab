# Historical v0.7: spend travel where measurements add local detail

Superseded by [v0.8 vertical investigation](NANO_V08_VERTICAL_INVESTIGATION.md).
Sweep results and policy source are retained as historical records only; the
active controller and lab no longer offer that route.

v0.6 completed a dense sweep and added crosses. That increased travel without
explicitly trading broad coverage against local detail. v0.7 replaces that policy
with sparse reconnaissance and bounded, measurement-guided feature following.
The decision code remains on the Nano; the lab is still its observation/plant
adapter. No physical motor output is enabled.

## Controller policy

- A dense sweep baseline has six tracks at 0.5 m spacing, about 47 m travel.
- Adaptive broad reconnaissance has three tracks at depths 0.30, 1.45 and 2.60 m.
  This costs about 25 m in uniform water. Gaps are intentionally left; quiet
  readings along these tracks do **not** establish zero gradient everywhere.
- Two changes of at least 0.08 °C over spatial intervals of at least 0.15 m trigger
  investigation. These are delayed measurements, not analytic field gradients.
- A compact diamond first provides two-axis sample geometry. The controller then
  uses a rolling 16-position local plane fit to choose short moves along the
  feature, with every third follow step crossing it in the normal direction.
  Along-feature steps also use bounded normal correction and dither. This forms
  a ribbon of measurements around the feature, rather than one isotherm only. This is
  following a measured thermal feature, rather than replaying the same cross.
- Candidate targets in already observed 0.125 × 0.125 m cells are rejected using
  a 192-byte visitation bitmap. Among unobserved candidates, the controller
  favours directional continuation and smaller correction. The bitmap stores
  observation proximity only, not a temperature map or statistical confidence.
- A local investigation stops after three arrival predictions have residual
  ≤0.05 °C, two weak-gradient arrivals, no new candidate cells, insufficient fit
  geometry/domain edge, its allocated distance, or 100 s. It does not treat a
  high sample count alone as evidence of sufficient information.
- Local distance allowance is at most 5 m and is computed from the travel left
  after reserving a direct route through the remaining broad-survey waypoints,
  plus a 0.5 m margin. At least 1.2 m allowance is required to start a probe.
  This is a geometric planning estimate, not a guarantee under currents/inertia.
- Up to three investigations; 300 simulated seconds; default total path budget
  32 m. Stop reason **6** means travel budget reached. The hard check occurs on
  incoming observations, so one observation interval can exceed the budget.
- Local speed retains the probe-lag rule `min(0.08, 0.10/tau)` m/s per axis.
  Dense and sparse transit both use nominal 0.4 m/s. A shorter route can still
  take longer because slower probe measurements require time.

This is a constrained heuristic with spatial novelty and prediction residual as
information proxies. It does not solve a global information-gain optimization,
compute entropy, or guarantee an optimal path. A local fit remains biased by
probe delay and can follow a displaced apparent boundary.

## Laboratory use

Setup → Adaptive exploration → Nano USB (v0.7) or native C++.
Choose **Sparse survey + gradient following** or **Dense sweep**, and set the
same travel budget for a fair budget-limited comparison. Set 60 m to let the
complete dense sweep finish. Default 32 m ends a dense sweep early.

Maps show actual travel/budget, probing versus following, and the local exit
reason. Recorded comparison is collapsed below the controller report. Its results
are fixed benchmark data, explicitly separate from the current run. Native and
Nano use the same header, water/lag input contract, guards and disabled outputs. Native
observations and requests use the same four-decimal precision as USB packets
so the comparison includes that discretization.

EXPL now requires a travel budget:

```
EXPL,adaptive,probe_tau_s,path_budget_m
```

OBS is unchanged. EXP retains its previous fields but `local` is now a phase code
(0 broad survey, 1 geometry probe, 2 feature following), followed by two extra
values: travelled metres and local exit code. The host requires v0.7 for this
activity; older v0.5/v0.6 boards retain vertical profile support.

Local exit: 0 pending, 1 locally predictable/weak/already observed, 2 local
travel/time allowance, 3 insufficient geometry or domain edge. Mission stop codes
0–5 are unchanged; 6 is total travel budget. CSV adds travelled distance, budget,
local exit and explicit trajectory policy. Input/output timing and source labels
remain available.

## What the comparison measures

`tools/compare_exploration.py` runs six static fields with three policies each:
complete dense sweep (60 m allowance), dense sweep with 32 m allowance, adaptive
with 32 m allowance. Centre 1.3 m, transition scale 0.07 m, probe tau 2 s, no
noise/navigation error/current. Patch-only has zero background drop; other
structured fields use 3 °C drop. These examples are not a held-out evaluation.

`tools/score_exploration.mjs` evaluates the recorded paths on a 40 × 16 interior
grid. The actual controller never receives the reference quantities used here:

- Gradient readings/m: readings at locations where reference |gradient|≥0.5 °C/m,
  divided by path length. Correlated readings are **not** independent information.
- Gradient cells/m: distinct 0.1 m spatial bins in that same reference region per
  metre. This reduces the reward for repeated readings, but is still a geometric
  proxy, not entropy or a detection probability.
- Supported fraction / supported RMSE: the existing map's local-plane fit with
  sampling-support heuristic >0.15 and valid geometry. RMSE omits unsupported
  points, so it must be read with supported fraction.
- Whole-grid NN error: RMSE of a separate nearest-observed-temperature estimator,
  evaluated everywhere, including gaps. This includes extrapolation and is not
  the local-plane map displayed in the lab. It exposes failures hidden by a
  supported-only error metric.
- Warm-spot peak error: distance between the maximum measured-temperature
  location and the prescribed spot centre; an imperfect lag-sensitive proxy.

Results are in `output/experiments/exploration_comparison.json`, with paths in
`exploration_trajectories.json`. Regenerate using Python, then Node (Node ≥18
required for the scoring module). If only Python runs, map-quality columns are
unavailable until the Node scoring step.

```sh
python3 tools/compare_exploration.py
node tools/score_exploration.mjs
```

## Limits of the result

The implemented policy reduces path length in all six presets, but it does not
uniformly improve map accuracy, feature coverage or spatial information per metre.
In particular a narrow hidden feature can fit between sparse tracks; a smooth
measured profile cannot rule it out. A dense sweep remains appropriate if the
requirement is detailed coverage everywhere. Peak location and whole-grid error
can worsen even while supported local errors improve.

The research problem is now a measurable trade-off: set a minimum feature size,
contrast and acceptable boundary/map error, and compare strategies at equal
travel/energy budgets over many unseen feature locations, noise levels, response
times and navigation errors. The current static, noise-free tank is a development
experiment. Travel is measured; physical power/energy is not modelled.

## Firmware build and tests

Standard Nano bootloader: `arduino:avr:nano:cpu=atmega328` (115200 baud).
Build v0.7 currently uses 27,404 flash bytes and 1,119 static RAM bytes, leaving
929 bytes for stack/local use. This is not a measured worst-case stack bound.
Bench-only EXPL guard, motor-off compile settings, packet validation and link
abort protections remain. See v0.6 notes for the hardware deployment boundary.

C++ tests cover the new distance reduction, actual follow phase, bounded controls,
quiet water, local plane fitting, time/path limits and invalid input. Bridge tests
cover protocol, budget validation, sequence correlation and timeout. Actual-board
verification is recorded separately under `output/logs/nano_v07_*`.

## Recorded final native results

| Field | Full sweep / adaptive travel, m | Full sweep / adaptive NN error, °C | Full sweep / adaptive map support |
| --- | ---: | ---: | ---: |
| flat | 46.9 / 25.2 | 0.00 / 0.00 | 100% / 12% |
| layer | 46.9 / 31.5 | 0.64 / 1.06 | 100% / 23% |
| tilted | 46.9 / 31.5 | 0.53 / 0.78 | 100% / 33% |
| front | 46.9 / 31.4 | 0.57 / 0.53 | 100% / 43% |
| patch | 46.9 / 29.1 | 0.22 / 0.23 | 100% / 35% |
| combined | 46.9 / 30.6 | 0.56 / 0.74 | 100% / 31% |

At USB-equivalent four-decimal precision, the warm-spot route is 38.0% shorter.
Distinct gradient bins per metre rise from 1.98 to 2.37 (about
20% more). Supported-gradient RMSE falls from 0.37 to 0.29 °C,
while gradient-region support falls from 100% to 61%. Whole-grid NN
error is 0.221 versus 0.226 °C and peak-location error
is 0.53 versus 0.55 m. Time is 123.6 versus 149.8 s. Thus the gain is
travel efficiency and concentrated local detail, not uniformly better accuracy.

Small numeric/input changes can alter discrete waypoint/visitation choices. Earlier
unquantized trials had different paths and peak errors. The table above uses the
final policy and the USB precision contract; it supersedes intermediate tuning
results. These few hand-chosen presets are development data, not independent
validation or a proof of an optimum.

A regression test includes a narrow warm spot placed between sparse tracks. It
is missed, as expected: this prevents reporting quiet-track observations as
proof that all intervening water is uniform.

## Final actual Nano verification

The final 27,404-byte build was uploaded and flash-verified. A complete actual
Nano-controlled warm-spot run used 29.0933 m of the 32 m allowance, 149.2 simulated
seconds and 1,493 correlated observation/reply pairs. It completed its sparse
survey after one investigation, including along/across feature-following steps;
that investigation reached its allocated local travel/time limit (exit 2).
All discrete decisions matched the native header replayed on identical quantized
inputs. Small float differences remain (maximum thrust difference below 0.0012).
DISARM was acknowledged after completion. No motor actuation occurred.

Evidence: `output/logs/nano_v07_upload.txt`, `nano_v07_verified.json` and
`nano_v07_exploration.csv`. The native benchmark is 29.0969 m / 149.8 s; minor
rollout differences are expected from floating point and packet precision.

## Water-selection correction

The isolated warm-spot preset deliberately sets background temperature drop to
zero. Previously, selecting a layered structure afterward retained that zero,
so the layer was invisible. In Adaptive exploration, changing Water structure
now restores a 3 °C contrast if it was zero. **Use layered water** selects a
sloping 22-to-19 °C layer centred at 1.3 m, with 0.1 m transition scale. The
isolated-spot preset still deliberately removes the layer; manually choosing
zero contrast remains possible in Water & probe settings.

Idle field/preset changes are now saved to the lab immediately, clear old run
data, and survive reload. Numeric settings save on slider release. Changing
water is rejected during an active run. The host field applies to both native
and Nano exploration; this does not change the Nano's separate onboard vertical
profile simulator or require reflashing. Fifteen bridge tests now include field
persistence, sample reset, run locking and lab-side Nano field selection.
