# Unified 2D AUV lab

Latest source and physically verified Nano firmware: v0.5 (compact shared-field lab).
See NANO_V05_UPLOAD.md for current operation and upload steps. Earlier version records below describe prior milestones.

The main lab and movement demo now share one interface at http://127.0.0.1:8765.
The old `/demo2d` URL opens the same interface. Start with `python3 lab/server.py`.

## Profile activity

- Offline: actual native C++ Nano controller plus adjustable Python virtual water.
- Nano: board firmware runs its onboard toy water/vehicle model. USB supplies
  depth, measured temperature, state, faults, target depth, vertical command,
  speed limit and gradient flags. These are simulated sensor values from the
  board, not measurements of physical water.
- The 2D vehicle's vertical position follows that telemetry. A/D or left/right
  buttons steer the horizontal visual position locally. There is no horizontal
  navigation or steering command on the Nano yet.
- Read-only Controller parameters come from native C++ constants offline, or the
  Nano's HELLO/CONFIG response in USB mode. Provenance is shown explicitly.
  Includes target/maximum depth, normal/slow rate, probe tau, allowed lag,
  gradient thresholds/window, timing and onboard simulator water parameters.
- Firmware v0.4 adds CONFIG without changing the 27-column telemetry schema.
  Config.h and ReportedConfig.h are shared by the board and native bridge.
  Legacy v0.2/v0.3 can provide telemetry but no reported configuration.

## Free swim activity

Choose Free swim and Start. Click the tank and hold WASD/arrows, or hold its
buttons. Up/down changes depth; left/right changes x. Space/Cut steering
releases requests; inertia, drag and positive buoyancy continue moving the toy
vehicle. Stop freezes this browser run; Pause/Resume and Reset are available.
Water layer and probe lag use the same setup sliders as offline profiles.
Noise is not applied to free swim. CSV contains the last 6,000 samples at 10 Hz;
path history holds 2,000 points. Selecting this activity from Nano mode releases
USB and changes to offline. Inputs clear on blur, hidden page and mode changes.

## Scope and next work

The unified interface does not send virtual sensor observations or horizontal
actuator requests to the board. A genuine 2D hardware-in-the-loop experiment
still needs the bounded sensor/actuator protocol, shared thruster mixing,
stale-command handling and tests listed in NANO_NATIVE_FIRMWARE_ROADMAP.md.
Physical sensors, SD logging and motor outputs remain unimplemented/disabled.

Checks: firmware/sketch desktop tests, eight server integration tests (including
reported-config validation and disconnect cleanup), and movement model tests.

Physical Nano validation: v0.4 flash upload verified (12,372 bytes), live CONFIG
received for all 16 fields, and eight-second onboard DEMO showed descent and
positive vertical requests. Reset then confirmed DISARM. Captured in
output/logs/nano_v04_verified.json. Physical motor outputs remain disabled.

The subsequent spatial-mapping extension adds level/sloping layers, a lateral front,
warm patches, sampled-field estimates and gradient/support views to Free swim.
See THERMAL_MAPPING_LAB.md for the estimator, survey generation, limits and exports.

The research controller is now a separate **Adaptive exploration · Nano / native
controller** activity. Choose it to let the actual Nano change trajectories
through a two-way measured-observation/motion-request loop. Free swim's JavaScript
planner remains a demonstration; it is not the Nano controller.
See [v0.6 notes](NANO_V06_EXPLORATION.md).
