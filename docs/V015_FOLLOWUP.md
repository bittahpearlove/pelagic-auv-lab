# v0.15 follow-up: diagnose availability before changing the controller

This update follows the supplied 20 October 2026 technical review. The Nano firmware and its 12-record estimator remain unchanged. The work strengthens scoring, explains unavailable estimates and makes the laboratory easier to use. It does not claim an improved sampling policy, a new firmware flash or physical probe validation.

## New evaluation and diagnostic tools

A boundary miss now has an explicit loss. For an expected unique boundary, loss is the smaller of absolute depth error and a declared error cap when detected, or a declared miss penalty when no estimate exists. Defaults are 0.30 m for both, with miss penalty at least the cap. These are illustrative software-study choices, not calibrated scientific costs. Change and freeze them before a future evaluation. Detection count and conditional error remain separate; flat-water false alarms do not receive an invented boundary error.

Paired loss comparisons retain every expected-boundary scenario, including misses. Scenario bootstrap intervals are separate for this complete-denominator loss and for error conditional on both detectors succeeding. Descent and ascent remain separate. The UI headline cards show a single chosen leg; it does not present 40 correlated legs as 40 independent scenarios. The original 30-scenario evaluation remains frozen and unchanged.

Each score includes status counts inside an evaluator-only ±0.15 m true-boundary mask, reliability availability and status by estimated depth. The oracle mask never enters a Nano observation or changes a controller decision. Status proportions are descriptive associations, not causal attribution or independent sample-level statistical evidence. Gray/empty depth bins stay unknown.

```sh
python3 tools/compare_profiles.py --repeats 3 --varied --seed 20261022
python3 tools/evaluate_research.py PATH_TO_RUN --output NEW_EMPTY_ANALYSIS_DIRECTORY
# Optional scientific PNG figures:
python3 -m pip install -r requirements-research.txt
python3 tools/diagnose_failures.py PATH_TO_RUN --output NEW_EMPTY_DIAGNOSIS_DIRECTORY --plots
```

Offline rescoring reads original observations and scenario references without controller imports. It checks that every original score field is reproduced; additional diagnostics/loss fields are saved in a new directory. New runs freeze the loss settings in their policy. Historical rescoring necessarily adds retrospective default losses; it cannot turn an old held-out set into a new independent evaluation. The diagnostic report records source and input-manifest hashes and a penalty sensitivity check.

## Findings from the old evaluation, reanalysed retrospectively

All 14 missed response/forward legs (seven unique scenarios, each direction) are dominated near the reference transition by status 4: residual or uncertainty-proxy rejection. Of 3,651 such rejected fresh transition readings, 2,615 exceed the residual gate only and 1,036 exceed both residual and proxy gates. These are repeated readings used to diagnose availability; they are not 3,651 experimental replicates. The residual test alone is exceeded in all these status-4 readings. This does not isolate the physical cause: noise specification, response-model mismatch, position errors and curvature can all contribute.

With a retrospective 0.30 m cap and miss penalty, response/forward minus medium/raw loss is +8.98 cm on descent and +9.07 cm on ascent over all 20 expected-boundary scenarios. Descriptive scenario-bootstrap intervals are [+3.57,+14.66] cm and [+4.18,+14.56] cm. Positive favours medium. Conditional error remains +0.33/+0.90 cm among only 13 jointly detected scenarios, with intervals spanning zero. The distinction is precisely why misses must be counted.

Illustrative penalty sensitivity preserves the adverse mean direction:

| Error cap / miss penalty | Descent difference | Ascent difference |
|---|---:|---:|
| 0.15 / 0.15 m | +3.76 cm | +3.80 cm |
| 0.30 / 0.30 m | +8.98 cm | +9.07 cm |
| 0.30 / 0.60 m | +19.48 cm | +19.57 cm |

This is post-hoc sensitivity, not a confirmatory superiority/inferiority claim. Full reference-grid coverage, conditional covered-grid RMSE, mission completion and detection remain different outcomes. The `diagnose_failures.py` figures expose those distinctions and include accuracy against actual duration; equal allowance does not imply equal duration or energy.

## Guided laboratory

- Start here: choose a vertical profile, strategy comparison or the separate 2D sandbox.
- Settings: gentle-layer, sharp-boundary and challenging-probe presets; advanced errors and scoring stay available.
- Run from Settings opens the live view automatically. Continue returns to the comparison when configuring a research run.
- Compare: primary response/forward versus raw baselines by default; single-leg detection cards, failure-aware loss, coverage and unavailable full RMSE.
- Expand detailed tables, paired intervals and rejection diagnostics when needed. Saved-run conditions remain distinct from the next-run configuration; the last comparison is restored after refresh.
- Desktop Live/Start here views fit the viewport with panel scrolling. Settings and scientific details can scroll for readability; mobile layouts stack panels.

The dashboard also derives an explicit minimum-speed/tolerance-infeasible explanation from the existing logged model limit. It does not alter the governor or reinterpret a proxy as a calibrated confidence interval. USB capability gating retains separate research/exploration firmware images. Water presets do not silently switch controller source or enable outputs.

## Review proposals: accepted, deferred and physical work

| Proposal | Disposition |
|---|---|
| Detection probability plus conditional error | Kept separate, by leg; counts and complete denominators visible. |
| Failure-aware loss and penalty sensitivity | Implemented, defaults explicit; old-set reanalysis labelled retrospective. |
| Rejection-by-depth/scenario and missed-case diagnosis | Implemented with oracle-only reference masks and saved-data plots. |
| Whole-scenario comparisons, raw versus estimator and adaptation ablations | Preserved; all expected cases enter loss comparisons. |
| Keep two Nano images and twelve-record buffer | Preserved; current firmware matches the tested v0.15 baseline. |
| Smaller/faster sophisticated estimator | Not justified by measured resource shortage; no replacement. |
| Gate-B shorter warmup | Deferred: warming is not the dominant logged status in these missed transitions. Calibrate and test any candidate independently. |
| Gate-C allowance fallback / uncertainty buffer | Experimental candidates, not quietly activated. Need a new development/freeze/evaluation cycle. |
| FOH depth integration / reversal-window renewal | Isolated future numerical tests; no unsupported assertion that either fixes the current misses. |
| Full UART/service-loop stress time and adversarial stack tests | Pending; existing 3.212 ms is decision time only. Future proposed gates: research flash ≤27,648 B, static RAM ≤1,200 B, tested stack margin ≥512 B, decision ≤10 ms. These are engineering targets, not full-driver guarantees. |
| Independent probe calibration | Procedure/tool exist; actual baths, installed probe, faster reference and repeated heating/cooling/flow tests remain pending. |
| Vertical translation rig | Planned first physical comparison; independently measured depth/speed/reference, randomized order, retain faults and failed profiles. |
| Real AUV integration | Optional later stage: real drivers, storage, power, enclosure, propulsion, navigation and verified recovery. |

The presentation PDF is prepared locally under `output/pdf/pelagic_project_presentation.pdf`: project scope, physics, algorithm, trajectories, lab use, fair comparisons, original results, retrospective diagnosis, Nano measurements, physical plan, contribution and likely questions. Original supplied reviews and generated datasets are not part of the public source upload.
