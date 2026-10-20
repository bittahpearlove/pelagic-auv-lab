# 2D thermal mapping laboratory

Latest layout: use Setup for controls on narrow screens, and Live / Thermal maps /
Console tabs for compact views. Adaptive profiling now samples the same offline
field at a fixed x; free swim explores across x and depth.

Open http://127.0.0.1:8765/demo2d, select Free swim and choose a water structure.
Use WASD/arrows after Start, or Preview complete route for a deterministic
browser simulation. Thermal map jumps to the two maps. Reset clears the path and
map. Changing water settings also clears them to avoid mixing different fields.

## What is implemented

- Prescribed, static temperature fields: level layer, sloping layer, lateral front,
  warm patch plus layer, and sloping layer plus patch. These are teaching fields,
  not solutions of a circulation/heat-transfer model.
- Sloping centre depth: centre + 0.16 * (x - 4) metres. Patch amplitude 2 C,
  centre (5.3 m, layer-centre + 0.35 m), Gaussian scales (0.75 m, 0.3 m).
- Lateral front is centred at x=4 m, with horizontal transition scale 5 times the
  transition-scale slider. Layer-centre depth is unused for this preset.
- Existing motion, drag, buoyancy and first-order probe lag. Free-swim positions
  are exact simulated coordinates. Navigation error and water motion are absent.
- Choose crossed diagonals, regular sweeps, or broad sweeps + local refinement.
  Run route live animates the planner; Preview complete route advances simulated
  time immediately using the same observation-based planner. See
  [coverage planner notes](COVERAGE_PLANNER.md). Neither sends Nano commands.

## Estimator and observability

Only x, depth and delayed probe temperature enter ThermalMap. Simulator truth is
used separately for the reference image, numerical reference arrows and evaluation.
Samples aggregate into at most 40x30 spatial cells (0.2 m x 0.1 m). Waiting at one
location increases readings but not spatial coverage.
The browser fits a weighted local plane T = a + b*x + c*depth from up to 48 nearby
occupied cells. The slopes (b,c), in C/m, estimate the gradient. A covariance/geometry
check rejects collinear or poorly spread observations. Gradient arrows are also
withheld outside surrounding spatial support. Arrows point warmer, not along flow.

Unknown distant regions stay grey. Fading/support view uses a heuristic based on
nearby spatial coverage, sample geometry and fit residual. It is NOT a calibrated
confidence interval, uncertainty in physical position, or a correction for sensor lag.
The map can be biased even where support is strong. Maps update at most once per
second as new measurements arrive.

The dashed curve is the mid-plateau temperature isotherm (22 - drop/2 C), not a
universal definition of a front or the maximum-gradient boundary. It can form
multiple contours around a warm patch. Arrows have normalized visual lengths.
RMSE is evaluated against the simulator only at supported grid points; it is not
an error metric over the entire pool, nor evidence of real-world performance.

## Why there is no PDE solver

A gradient is an operation on a temperature field, not itself a PDE to solve.
For example, a 1 C change over 2 m gives an average slope of 0.5 C/m. Estimating
nearby horizontal and vertical slopes requires measured positions and temperatures.
The local plane is solved with algebra on the PC/browser. The estimator stays on the PC/browser and needs no PDE solver. Prepared v0.5
firmware adds shared-field selection for onboard simulation and is now physically
verified on the Nano.
See NANO_V05_UPLOAD.md for current instructions.
A future heat/advection/diffusion model could predict the evolution of temperature,
but would need physical parameters, flow and initial/boundary conditions. That is
a separate problem from reconstructing a field from observations.

## Exports and verification

Run CSV includes the nine original motion/probe columns plus source, field shape,
centre, width, temperature drop and probe tau. Export map CSV includes grid positions,
estimated and reference temperatures, gradient components where observable, support
score and field metadata. All spatial-map records are labelled browser_simulation.

Tests: thermal_map_test.mjs checks horizontal/sloping/patch fields, linear-gradient
recovery, vertical/diagonal-track rejection, unknown space, repeated-position
coverage, reset and survey/lag behavior. Existing movement/keyboard and 11 bridge
tests also pass. Browser inspection verifies populated maps, contours and controls;
CSV download completion could not be confirmed through the browser automation API.

The survey is a fixed coverage path. Automatic adaptive 2D boundary following and
sensor-lag compensation are future work; the display currently exposes their need.
