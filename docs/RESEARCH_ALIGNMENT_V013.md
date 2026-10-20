> Exploration policy superseded by [v0.14 bounded search and surface return](NANO_V014_PROFILE_RETURN.md). The vertical Research comparison below is unchanged; open-ended exploration is no longer the current route.

# v0.13: trajectory and original proposal review

Reviewed against all five pages of **Adaptive Temperature Profiling with a Small AUV**, the original project proposal. This review preserves subsequent choices: length–depth views, no prescribed sweep, no total exploration budget, and eight-second local visits/holds. The original PDF remains unchanged.

## Research question and assessment

Can measured temperature gradients and the installed probe's response time guide vertical speed selection to improve a temperature profile, within the same maximum mission-time allowance?

The existing exploratory trajectory is useful for developing a measured-input controller and spatial memory. It is insufficient by itself to answer that question. A visited cell establishes passage, not a resolved water temperature, boundary location, optimal route, or complete map. A path that looks less tangled can still have more temperature error. Conversely, repeated measurements can be useful when they resolve lag or uncertainty; deleting every revisit would defeat the experiment.

The primary experiment is now explicitly a vertical descent–hold–ascent, with fixed-fast, fixed-slow and adaptive controls evaluated against the same simulated reference. Open-ended exploration remains a separate development activity. Claims about minimizing global path length, complete feature discovery, water sampling with bottles, or field deployment are outside the present implementation.

## Traceability to the five proposal pages

| Proposal | Current implementation / correction | Work still needed |
| --- | --- | --- |
| p.1: response-aware profiling, compare fixed speed and independent reference; begin with a vertical profile | Research tab and `tools/compare_profiles.py` run the exact production C++ profile controller for all three strategies, at fixed x and 0–1 m depth. | Independent reference instrument; physical calibration and repeated tank tests. Simulator truth is an evaluation oracle, not an independent physical instrument. |
| p.2: two horizontal thrusters and one vertical; sensors, enclosure, probe mounting | Firmware remains simulation-only, motor outputs disabled. Estimated x/depth in USB exploration are supplied by the virtual plant. | Hull, power, verified ESC interfaces, depth/yaw control, real position estimation, waterproof acquisition and storage. The proposed vehicle cannot independently translate sideways or guarantee station keeping. |
| p.3: reconnaissance, persistent gradient, sensor/detection margin, slower revisit, separate ascent/descent; logs and aborts | Profile firmware retains a measured depth interval across the bottom turn and slows before re-entering it on ascent. Acquisition-window history is cleared at reversal. Exploration tests spatially separated, direction-consistent windows, including during transit. Vector speed requests now obey their scalar cap. Retrace reports when lag/detection margin exceeds the local allowance. Complete session CSVs persist on disk. | Measure noise thresholds, installed-probe tau versus flow, pressure/probe vertical offset and timing. Add physical abort/recovery and positive-buoyancy tests; loopback/USB checks are not vehicle safety validation. |
| p.4: calibrated reference, repeated fast/slow/adaptive trials, equal allowance, common-depth and transition errors, time/energy/reliability | Three paired-noise repeats per strategy; identical 180 s maximum per trial; one profile per trial, early finishes leave unused time. Report common-depth binned error, transition error, boundary error, coverage, completion/censoring, faults, time, distance and a clearly named toy propulsion proxy. | Repeat count/power analysis informed by pilot variance; reference drift/mixing checks; measured voltage/current/energy; recovery cost and physical mission logging. |
| p.5: characterize sensor first, then vehicle, autonomy, controlled comparison | Current stage is software/hardware-in-loop preparation. New comparisons can test lag mismatch and flat-water false detections before buying parts. | Bench response/calibration experiment, stratified tank with a stationary reference array, then vehicle trials. Arctic/ocean claims would require a much larger program. |

## Firmware changes

### Vertical research profile

Two consecutive high-gradient depth windows establish a transition. The controller remembers a conservative interval around those measured windows, expanded by an observed-speed × configured-tau lag estimate plus one depth-window margin. It merges detected intervals conservatively; it does not reconstruct an unmeasured exact boundary or maintain a full map. On ascent the controller resets directional acquisition history but retains the interval and requests slow speed before entering it. A new mission/disarm clears the interval. Fast and slow baselines remain fixed strategies.

This is a lightweight revisit rule, not inverse filtering or a heat-equation/PDE solution. Tau is still the provisional configured 2 s in the vertical controller; the experiment can vary actual simulated tau to test mismatch. Settings must eventually come from the installed probe.

### Open-ended exploration

- Vertical descent still precedes local investigation. No sweep or total time/travel budget was added.
- Detection requires two direction-consistent displacement windows of at least 0.15 m, absolute change of at least 0.08 °C **and** measured along-track change of at least 2 °C/m. Holds cannot establish a spatial gradient. These are provisional thresholds; exploration noise remains disabled.
- Transit now checks measured change along its track, rather than relying on a single endpoint temperature difference.
- Requested x/depth velocity is normalized as a vector. Independent component clipping previously allowed a diagonal request up to √2 times the displayed cap. This caps the requested velocity, not a hard guarantee on physical speed under inertia/disturbance.
- Upward retrace checks estimated lag distance `|v| tau` plus two detection windows (0.30 m). It reserves 4.4 s for local probing within the total eight-second visit. If feasible retrace distance or a tank boundary prevents the full margin, `local_exit=5` means **boundary unresolved under this allowance**. A smaller detour is not presented as an accurate boundary revisit.
- Eight seconds is often insufficient for a slow probe to settle and acquire independent geometry in both directions. Local plane fits remain lag-biased estimates even when their geometry flag is valid. A horizontal front may need a different maneuver later; this upward rule primarily targets vertical structure.
- Retained 0.125 m visitation memory and nearby-frontier scoring remain route heuristics. They are not a proof of minimum path or complete coverage. “No unvisited target” means exhaustion of the permitted candidate grid, not that all temperatures are known. There is no localization error in this plant.

## Reproducible evaluation

Run `python3 tools/compare_profiles.py` or open **Research → Compare three strategies** after stopping the live run. The UI uses the current water/probe controls; the CLI defaults to a level layer centered at 0.50 m, scale 0.07 m, drop 3 °C, actual tau 2 s, noise sigma 0.005 °C, seed 20261020 and three repeats. The 1 m profile cannot investigate a layer outside its traveled depth range.

Every trial starts at the surface and includes five seconds of arming and five seconds of bottom hold. It ends on surface completion, fault or the same maximum allowance. Unused allowance is reported; it is **not** silently converted into extra profiles. Recovery after the surface completion criterion is excluded, so elapsed time and energy are not a complete physical recovery budget. Interactive exploration remains unlimited until Stop. `--allowance`, `--repeats`, `--tau`, `--noise` and `--drop` allow sensitivity experiments.

Temperature error is evaluated on the same occupied 2.5 cm bins for all strategies, separately on descent and ascent. Each bin contributes its mean measured-minus-reference error; the reported RMSE is the root mean square of those bin errors. Coverage is reported against 36 bins over 0.10–1.00 m. Missing bins do not become zero error. Transition error uses ±0.15 m around the reference boundary. Boundary means the unique mid-drop isotherm in the column, not a claim that every water structure has a single front. The first measured crossing in travel order is used, never the crossing nearest truth; extra crossings are counted. Undefined or uncrossed boundaries remain null.

The acquisition timestamp, measured temperature, simulated reference at that same probe position/time, depth, velocity, next command, learned interval, seed, noise, tau, field and allowance are logged. Truth never enters the C++ controller. Probe/depth offset is explicitly zero in this version; physical experiments must measure and correct it. Seed repeats characterize simulated acquisition noise, not tank-to-tank repeatability, mixing, drift or navigation uncertainty. No significance claim is made from three simulated trials.

Illustrative default simulation, three-repeat means (reproduce locally; these are not measured vehicle results):

| Strategy | Descent profile RMSE °C | Ascent profile RMSE °C | Descent boundary error cm | Ascent boundary error cm | Elapsed s |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fast | 0.531 | 0.523 | 7.89 | 7.89 | 52.25 |
| Adaptive | 0.467 | 0.250 | 7.35 | 3.59 | 79.60 |
| Slow | 0.253 | 0.249 | 3.58 | 3.57 | 107.95 |

All nine default profiles complete within the same 180 s allowance. There are 35 shared descent bins and 36 ascent bins. Adaptive is a time/accuracy compromise here: the first descent still detects late; the remembered-band ascent performs close to fixed slow. It does not dominate every baseline. The result motivates testing rather than establishes the hypothesis.

## Logging, reproducibility and next physical steps

Live/native/USB sessions now write full CSVs to `output/runs/`; the last 10,000 rows remain on screen. Export reads the complete current session. Reset/new run closes the old file without deleting it. Buffered writes flush at most every 20 samples, on terminal states and export; a crash can lose the final buffered records. The lab uses a unique native-library inode per instance, preventing test/startup recompilation from truncating an already loaded library. USB still belongs to a single process at a time.

Research artifacts are `output/experiments/profile_comparison/summary.json` and `samples.csv`. Each new comparison overwrites these two summary artifacts; archive a copy for each recorded experiment. Session CSVs have unique names. Generated output and the original proposal PDF remain excluded from the public source repository.

Next: characterize the complete probe assembly under several flow speeds; quantify noise and synchronization; measure probe/pressure offset; build a stable gradient and time-matched reference array; preregister crossing/bin/transition definitions and allowance handling; then run randomized repeated physical trials including mixing checks and measured energy. Only after that should broader path planning and real AUV navigation become the main experiment.
