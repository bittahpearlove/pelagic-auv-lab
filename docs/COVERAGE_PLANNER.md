# Coverage before local thermal investigation

The lab remains a length–depth slice (x, depth), 8 × 3 m. Tank width is not
represented. An actual three-dimensional volume would need additional tracks
and position sensing. The Nano remains on verified v0.5; this planner runs in
the browser. It cannot steer real hardware. No firmware update is needed here.

## Using the lab

1. In Setup, select Free swim. This switches away from a connected Nano to the
   offline source; the bridge disarms/disconnects it.
2. Select Isolated warm spot for a 22 °C background with a Gaussian spot up to
   24 °C, or choose an existing layer/front field.
3. Choose crossed diagonals, regular sweeps, or broad sweeps + local refinement.
   Expand Define “just enough” to set spacing, proximity coverage goal,
   temperature-change trigger and time budget.
4. Run route live animates the motion. Pause freezes simulated time. WASD/arrows
   override the planner; Cut steering coasts; Stop terminates it. Preview complete
   route runs the bounded simulation immediately and opens Thermal maps.
5. Inspect the map and stop reason. Blue dashed segments are planned survey
   tracks; amber segments are local refinements (including unfinished segments).
   The pale solid line is actual travel. Toggle the planned route for clarity.
6. Save CSV measurements, map CSV and Planner report JSON together. Measurement
   CSV includes policy and final/current coverage settings; JSON includes route,
   candidate centres, event times, distance and stop reason. Save each policy's
   output before previewing the next; Reset/field changes clear the map.

The initial simulated probe is equilibrated before an automatic route. It then
has the selected response delay. Position is exact, field static, and the free
swim model has no noise/current/navigation uncertainty. The live integrator uses
20 ms steps, preview 50 ms, so small numerical differences are expected.

## Algorithm and measurable stopping rules

SurveyPlanner receives only x, depth, time and the delayed probe temperature.
It has no reference temperature field, true gradient or hidden spot coordinates.

Crossed diagonals provide reconnaissance. Sweeps cover equally spaced depths,
with requested track spacing 0.25–1 m. The adaptive policy first finishes this
broad route, then considers local investigation. It prioritizes remaining
coverage gaps; otherwise it compares measured spatial-bin temperatures separated
by 0.15–0.8 m, requiring a chosen absolute change (default 0.15 °C), and ranks
candidates by change/distance. Candidates within 0.8 m of an earlier candidate
are suppressed. Up to four local cross/box routes approach from different
directions, with smaller surge/heave command limits. These are heuristic choices,
not an optimal information-gain method or continuous gradient tracking.

Coverage is measured on a 48 × 18 grid inside vehicle margins: x 0.4–7.6 m,
depth 0.2–2.7 m. A grid cell counts if a probe observation falls within half
of the requested track spacing. Goal defaults to 90%. This near-track metric
is separate from the estimator's sampling-support shading, its supported-grid
RMSE, feature-detection probability and thermal accuracy. Changing spacing also
changes the coverage radius; compare policies at identical spacing.

After broad coverage, adaptive runs continue while qualifying candidates remain,
subject to time budget (default 240 s, selectable 30–360 s) and local-pass limit.
Thus meeting coverage alone does not terminate all thermal investigation. The
report distinguishes route completion, exhausted budget, refinement limit and
lack of further qualifying changes. A started pass can remain unfinished.

## Reproducible initial comparison

Isolated warm spot, spacing 0.5 m, goal 90%, trigger 0.15 °C, probe τ=2 s,
240 s budget; deterministic preview results:

| Policy | Near-track coverage | Time | Travel | Local passes started |
| --- | ---: | ---: | ---: | ---: |
| Crossed diagonals | 38.8% | 40.4 s | 19.2 m | 0 |
| Sweeps | 99.7% | 100.0 s | 46.1 m | 0 |
| Sweeps + refinement | 99.7% | 240.0 s | 69.0 m | 4 |

Adaptive stopped at its budget, with a local route unfinished. These results
show coverage/time tradeoffs, not a demonstrated improvement in reconstruction
accuracy. In the UI check, supported-grid RMSE was 0.16 °C over 129 grid points
for diagonals, 0.23 °C over 486 points for sweeps, and 0.19 °C over 486 points
for adaptive. The deceptively small diagonal error omits far more of the domain. Supported-grid RMSE omits unsupported regions and must be reported
with support area. Travel is not energy: the free-swim model does not estimate
power or battery consumption.

## What “just enough” still needs scientifically

Choose a minimum feature size, detectable temperature contrast and acceptable
boundary-location/map error, then validate track spacing and speed against those
requirements. A feature between tracks can remain unseen. A diagonal cannot
exclude hidden warm spots. A slower sensor smears a transition along travel by
roughly speed × response time; an apparent high-gradient candidate can be a
lagged trail. Local revisits do not automatically remove this bias.

Next experiments should vary spot location/size/contrast and probe delay, then
compare detection rate, boundary/peak location error, full-domain reconstruction
error including unknown areas, mission time and measured energy on real hardware.
Repeat with position error and currents before making field claims. A later
planner could choose between coverage, lag-aware revisits and uncertainty
reduction. No heat-transfer PDE solver is needed for this first experiment.

Related established work uses uncertainty-guided adaptive AUV sampling of river
plumes: [Frontiers in Marine Science, 2023](https://www.frontiersin.org/journals/marine-science/articles/10.3389/fmars.2023.1319719/full).
Our current planner is a simpler heuristic and does not implement that paper's
probabilistic method. Novelty requires a literature review and comparative data.

Verification: tests/survey_planner_test.mjs checks no field access, quiet water,
coverage gaps, measured triggers, local bounds, slower commands, budget stops and
all three policies. Existing motion/map/keyboard tests and 11 bridge tests pass.
