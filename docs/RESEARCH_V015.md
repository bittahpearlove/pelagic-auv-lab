# v0.15: response-aware vertical profiling

The primary question remains whether accounting for probe response delay and choosing vertical speed improves a measured temperature profile. A vehicle or 2D map is an experimental platform, not evidence of the hypothesis. The original horizontal-front paper inspires this tank-scale vertical simplification; it is not replicated here.

## Estimator and policy

`AdaptiveLegacy` preserves the previous gradient-window sampler as mode 0. Modes 1/2/3 are fixed fast/slow/medium (0.05/0.02/0.035 m/s). Mode 4 is the new response-aware policy; mode 5 removes confidence gates for ablation while retaining minimum geometry and safety checks.

The model is first order: dy/dt=(T−y)/tau. Instead of differentiating noisy observations, the estimator filters constant and depth regressors with the same response recurrence. For initial reading y0 and depth origin z0 it fits

    y − y0 = psi0 * (beta0 − y0) + psiz * gradient.

The initial-state term is retained. Filter updates use actual acquisition intervals, including jitter; exponential coefficients are cached for repeated intervals. Twelve records, spaced at least 250 ms apart, occupy four fixed float arrays. A checked 2×2 Schur solve avoids an explicit matrix inverse. At least eight records, 0.04 m observed span, finite inputs and a positive pivot are required. Reliability additionally requires three assumed time constants of history and residual/gradient-uncertainty gates. These thresholds and uncertainty proxies are provisional; noisy positions are an errors-in-variables limitation.

Current-depth reconstructed temperature is a diagnostic extrapolation. For scoring, reconstructed temperature is associated with the fit's support depth z0 + sum(psi0*psiz)/sum(psi0²). This separates its window support from present vehicle position. Neither association uses true boundary depth or a truth-derived time shift. A calibrated probe/depth offset can be added in evaluation; an unknown offset remains an error source.

Speed request = clip(epsilon / (tauMax * max(abs(gradient), 0.2)), 0.02, 0.05) m/s. Unreliable fits use the conservative minimum. Increases require persistence and direction-change dwell; requested acceleration is limited to 0.01 m/s². The achieved speed and approximate lag error are logged separately. A speed floor, initial transient, curvature, wrong tau, plant lag or time-varying water can violate the intended tolerance. This is a candidate heuristic, not a bound on actual estimation error.

Safety checks precede sampling decisions. The experiment cap includes five-second arming. A common return reserve depth/0.015 + 10 seconds can terminate descent early; the hard allowance still stops the mission. Reaching the surface without the bottom target is recorded separately from a full profile. The reserve is a toy-plant heuristic, not a recovery guarantee.

## Why the local retrace was changed

At most 3.6 seconds remain for retrace after the old geometric probe phases. At a maximum 0.04 m/s this is 0.144 m, while the old requested margin abs(v)*tau + 0.30 m is at least 0.30 m. Even the former 0.03 m completion tolerance cannot bridge that gap. Full feasibility is checked before motion, including settling time. The eight-second user limit is preserved; the resulting upward motion is labelled **partial inspection / unresolved boundary**, never a completed full retrace.

The exploration image retains the v0.14 8 s local / 10 s total nearby-search / checkpoint return / descent / surface trajectory. Visited cells remain passage memory, not independent information or calibrated confidence. The last historical EXP field is a reserved zero, not a recheck metric. A new spatial information planner is deferred until the 1D result is established.

## Experiments and reproducibility

Six methods use identical dynamics and the same maximum allowance. Shared scenario seeds produce the same field, clock jitter and channel-loss realization; measurement-noise streams are independent by method. Noise is added to digitized observations, never to the probe's internal thermal state. Configurable errors include AR(1) noise, bias, drift, quantization, position/velocity uncertainty, missing packets, jitter, moving layers, sensor offset, flow-dependent tau and plant disturbances. On loss the last acquisition timestamp is retained. The 2D demonstration currently stops at its first simulated lost observation; the 1D runner supports bounded gaps and freshness faults.

Each run gets a new directory with a manifest, source hashes, scenario definitions, policy digest, raw observations, diagnostics and metrics. Existing nonempty experiment directories are rejected. Freeze settings **and source hashes** after development. Evaluation rejects a changed research source or policy override. Development and evaluation use disjoint seed namespaces. Frozen evaluation is a software study, not a preregistered physical experiment or sample-size power calculation.

Raw and reliable forward reconstructions are scored separately on 32 fixed 2.5 cm bins from 0.10 to 0.90 m. Full-profile RMSE is absent unless all bins are covered. Covered, transition and shared-bin RMSE are explicitly conditional. A boundary estimate is the strongest supported gradient peak above 2 °C/m in 0.20–0.80 m; optional local interpolation is fixed before evaluation. Undefined/missed boundaries remain in failure denominators. Flat water has no expected boundary; false peaks per travelled metre are reported. Moving-water reference is evaluated at each bin's acquisition time; the composite profile is not an instantaneous map.

Paired contrasts separate combined method, adaptation alone, estimator alone and confidence gating. Intervals bootstrap whole scenarios (1,000 resamples), conditional on **both** boundary detectors succeeding. Counts of failures and joint detections always accompany them. All comparisons are exploratory; multiple contrasts and mixed disturbance distributions are not confirmatory inference.

```sh
python3 tools/compare_profiles.py --repeats 20
python3 tools/run_sensitivity.py
python3 tools/compare_profiles.py --freeze-policy output/frozen-policy.json
python3 tools/compare_profiles.py --split evaluation --policy-file output/frozen-policy.json --varied --repeats 30 --seed 20261021
python3 -m pip install -r requirements-research.txt
python3 tools/evaluate_research.py output/experiments/research/RUN_DIRECTORY --plots
```

The offline evaluator reads the saved manifest and CSV, recomputes all scores without the controller or browser, and asserts they exactly match the original. Figures are standalone PNG/PDF files. Preserve the whole experiment directory when sharing results.

## Results from this implementation pass

Twenty nominal development scenarios, twenty varied development scenarios and twenty one-factor development checks preceded freezing. Thirty varied held-out scenarios produced 180 full simulated profiles across six strategies. Ten scenarios were flat; twenty had expected boundaries. No policy was retuned after this evaluation.

| Combined response/forward vs medium/raw | Descent | Ascent |
|---|---:|---:|
| Joint boundary detections / expected | 13/20 | 13/20 |
| Response boundary failures | 7/20 | 7/20 |
| Medium/raw boundary failures | 0/20 | 0/20 |
| Conditional mean error difference | +0.33 cm | +0.90 cm |
| Conditional bootstrap 95% interval | −2.68 to +3.31 cm | −1.37 to +3.36 cm |

Negative differences favour response. These results do **not** establish superiority. Nominal development showed lower combined boundary errors, but adverse conditions exposed missing reliable estimates and a loss of that advantage. Adaptation-only held-out differences were −0.28 cm descent and +0.71 cm ascent, with intervals spanning zero. The response model is a useful hypothesis and diagnostic tool; calibration and robustness are unresolved research work.

Local evidence: `output/experiments/v015-development-nominal/`, `v015-development-adverse/`, `sensitivity/`, `v015-heldout/`, and `v015-frozen-policy.json`. These generated datasets are not silently included in the source release. Reproduce them using the documented commands; never present a plot conditional on successes as an all-mission performance result.

## Physical milestones still pending

1. Calibrate the installed probe's step response at representative flow, with independent reference measurements and heating/cooling repeats.
2. Use a supervised vertical translation rig with measured speed and probe/depth offset, before relying on a freely swimming vehicle.
3. Compare complete reference profiles and energy measured by an instrument; retain failed trials.
4. Integrate real drivers, logging, buoyancy/recovery and actuation only after bench validation. Current firmware uses simulated sensors and disabled motors.

See [calibration protocol](PROBE_CALIBRATION.md), [firmware protocol](NANO_V015_RESEARCH.md), and [review disposition](REVIEW_RESPONSE_V015.md).

## Review follow-up: failure-aware scoring

The 20 October lab revision adds capped boundary loss, all-expected-scenario paired mean loss differences, fresh-sample rejection fractions in an evaluator-only +/-0.15 m transition window, and status-by-depth counts. Default cap/miss penalty are both 0.30 m and need scientific justification and sensitivity analysis before evaluation. CLI: `--error-cap` and `--miss-penalty` (development only; freeze them in the policy for evaluation). Historical controller and result claims above remain unchanged. Fresh source hashes require a fresh freeze. See [implementation and limitations](V015_FOLLOWUP.md).
