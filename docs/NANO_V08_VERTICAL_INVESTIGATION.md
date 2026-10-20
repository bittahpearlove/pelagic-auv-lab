> Current firmware v0.9 removes the distance limits described below. See [current travel-limit update](NANO_V09_NO_TRAVEL_BUDGET.md).

# v0.8: descend, rise slowly, investigate locally, finish

The active exploration controller has no sweep or area-coverage route. The former
policy selector and recorded sweep-comparison panel are removed from the lab.
Free swim remains manual; its automatic coverage-demo buttons are retired.
Existing v0.7 data and notes describe historical experiments only.

## Mission

1. Start at the chosen **Descent x** and simulated depth 0.20 m. Descend vertically
   toward 2.70 m at nominal 0.10 m/s, holding the initial x position.
2. Two measured temperature changes of at least 0.08 °C across spatial intervals
   of at least 0.15 m trigger one investigation. This uses the delayed probe;
   detection can occur below a real boundary.
3. Hold x and slowly retrace upward by 0.25 m (arrival tolerance 0.03 m). The
   nominal upward speed is at most `min(0.04, 0.08/tau)` m/s. Horizontal probing
   begins only after this upward retrace has reached its target.
4. Establish local sample geometry, then use the existing measured-gradient
   investigation nearby. Targets stay within ±0.45 m of the descent x, and
   between 0.45 m above and 0.10 m below the detection depth, clipped to the
   laboratory bounds. Actual motion can overshoot targets slightly in the plant.
5. Finish after this single investigation. No sweep, return to a survey track,
   restart of descent or automatic surface-return route is scheduled. If no
   temperature change is detected, finish at the depth limit instead.

Local travel/time limits remain 5 m / 100 simulated seconds; model predictability,
weak change, already-observed candidates or poor geometry can end it sooner.
Total travel defaults to 8 m (adjustable 1–16 m), with a 300 s mission timeout.
Quiet-water descent is about 2.5 m travel. The old 32 m coverage budget is retired.
Requests become zero when complete; stopping the virtual plant is not a physical
underwater station-keeping or recovery system.

Depth is positive downward (internal z / plotted vertical axis). A smaller depth
therefore means the requested upward retrace. Local investigation can move both
horizontally and vertically; only descent and the initial retrace hold x fixed.

## Controller and protocol

Shared firmware `Explorer.h` still owns all decisions, on Nano or native C++.
Stages are Descend=0, Backtrack=1, Probe=2, Follow=3, Finished=4. EXP field 2 is
0 for descent/finished, 1 upward retrace, 2 local geometry, 3 local follow. The
former coverage-waypoint field now reports mission stage. CSV phases are
`descend`, `backtrack`, `probe`, `follow`, `complete`; the final row has zero
motion requests. Trajectory policy is `vertical_then_local`.

The EXPL wire format remains `EXPL,1,tau,path_m`; the first field must be 1.
Old sweep-policy requests are rejected by both firmware and bridge. OBS format,
sequence correlation, invalid-input handling and link timeouts remain in force.
Firmware identity is v0.8; this protocol needs v0.8 on the connected board.
Physical motor outputs remain compile-disabled; no real sensor or navigation
adapter is added in this revision. See the earlier deployment-boundary notes.

## Laboratory

Setup → Adaptive exploration. Use layered water if a clear thermal boundary is
needed. Choose Descent x, total travel allowance and controller source, then Run.
The readout distinguishes vertical descent, slow upward retrace and local
investigation. Water fields are supplied by the lab and remain selectable as
before. There is no automatic broad mapping of water away from this vertical line
and local neighbourhood. A hidden feature elsewhere will remain unobserved.

## Verification

C++ tests check fixed x during descent/retrace, actual upward travel before
horizontal probing, bounded local motion, a single investigation, quiet water,
no movement after completion, travel/time limits, invalid observations and sketch
commands. Fifteen bridge tests include removed-policy rejection, field persistence
and protocol checks. The actual-board verifier uses a sloping layer at x=4 m and
records the upward stage separately before accepting the local investigation.

## Actual-board verification completed

v0.8 was uploaded and all 26,044 flash bytes verified (1,117 static RAM bytes,
931 bytes remaining for local/stack use; not a measured stack bound). The Nano
completed a sloping-layer experiment in 55.2 simulated seconds and
3.4575 m travel, using 553 observation/reply pairs. The upward-only
phase rose 0.226 m before horizontal probing. All descent/retrace rows held x=4 m
within 0.002 m. One local investigation ended, then motion requests stayed zero.
Discrete phases/decisions matched the native header on the same quantized inputs.
The board acknowledged DISARM afterward. Physical motor outputs stayed disabled.
Evidence: output/logs/nano_v08_upload.txt, nano_v08_verified.json and
nano_v08_exploration.csv. The accelerated USB experiment is virtual-water
verification, not physical underwater validation.
