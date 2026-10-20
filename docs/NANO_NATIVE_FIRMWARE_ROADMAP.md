# Native firmware and 2D demo handoff

Current source and physically verified Nano firmware: v0.13 (simulation-only). See the root README and RESEARCH_ALIGNMENT_V013.md for current operation, proposal review and remaining physical work. Earlier version records below describe prior milestones.

19 October 2026. Project: low-cost, sensor-response-aware adaptive vertical
temperature profiling with a three-thruster AUV. Starting board: classic
ATmega328P Nano, FT232R USB serial EXAMPLE_SERIAL. Location: Saint Petersburg.

## Meaning of “native” here

- The physical Nano already runs AVR firmware v0.3: mission states, bounded depth
  controller, gradient detector, adaptive trajectory speed, fixed-speed baseline
  modes, watchdog, fault checks, serial commands and HELLO identification.
- The offline lab compiles the same Controller.h/Adaptive.h as a native PC library.
  That does not make the Python water model or all dashboard features part of
  the Nano firmware.
- Nano USB mode currently runs the board's own toy water/probe model. Motor
  outputs are disabled, and real sensor acquisition is intentionally unimplemented.
- The new 2D side-view demo runs in the browser only. It never sends steering or
  motor commands to the Nano. It is a movement/measurement concept demo, not the
  current firmware controller or proof of physical control.

## Feature migration checklist

| Feature | Present implementation | Next work on physical Nano |
| --- | --- | --- |
| Mission states and adaptive depth speed | AVR firmware and shared C++ core | Tune/validate against actual vehicle and calibrated sensors |
| Real temperature/depth | Toy values; lagged probe simulation | Nonblocking drivers, CRC/status validation, calibration, surface pressure zero |
| Roll/pitch/heading | Simulated zero attitude | IMU driver, mounting calibration, heading validation near motors |
| Battery/current | Simulated 12 V and toy current | Calibrated divider/current sensor; change pack/current thresholds to chosen hardware |
| Leak/arm inputs | D2/D7 physical loops; DEMO virtualises them only with motors disabled | Actual sensor interface, wire-break/power-loss tests and documented polarity |
| Three thruster outputs | Driver scaffold; all physical outputs disabled | Review ESC protocol, neutral/polarity, startup and signal-loss response; add mixing |
| Horizontal motion/yaw | Horizontal commands remain zero | Surge/yaw requests, differential mixing, heading control and bounded slew rates |
| Onboard logging | USB CSV only | SD driver, buffered acquisition-rate records, storage-ready preflight and error handling |
| Configurable experiment settings | Python environment controls | Versioned bounded firmware settings; disarmed-only changes and acknowledgements |
| Real-world r ecovery | Neutral-on-fault; no powered fault ascent | Fault-specific recovery policy, validated depth/actuation conditions and passive buoyancy |
| Reference comparison | Lab plots and synthetic truth | Independent time-aligned temperature references, calibration and repeated trials |
| Revisit detected layer | Not implemented | Optional mission extension after online slowing is validated |
| 2D manual demo | Browser-local side-view toy model | First add shared horizontal control + a hardware-in-loop protocol; do not wire browser controls directly to ESCs |

## Suggested implementation sequence

### 1. Formalise board protocol and configuration

- Keep HELLO identity including version, simulated flag and motor-output flag.
- Define bounded commands and responses for experiment configuration, mode, start,
  stop and disarm; acknowledge accepted/rejected settings with actual applied values.
- Preserve safe boot and explicit arming. DEMO must remain impossible when physical
  motor outputs are enabled; no lab button should silently change this setting.
- Check incoming lengths, finite/range constraints and freshness; preserve the
  mission's autonomous time/depth limits independently of a service laptop.
- Distinguish loss of a required HIL input stream from loss of an optional real
  mission service link. Use explicit modes rather than one ambiguous timeout.

### 2. Real sensing, one channel at a time

- Choose exact sensor models/board revisions, interfaces, voltage translation and
  connector pinouts from datasheets before implementing their adapters.
- Trigger slow conversions asynchronously, preserve individual acquisition times,
  and set freshness limits by channel. A DS18B20 12-bit conversion may take 750 ms,
  exceeding the current 500 ms combined freshness limit.
- Retain raw data alongside filtered measurements. Reject device error codes and
  stale values rather than replacing them with plausible defaults.
- Establish surface pressure only while disarmed at the surface. Account for water
  density, temperature-probe height offset and sensor time alignment.
- Characterise the installed probe time constant at relevant flows. The 2 s value,
  gradient thresholds and 5 cm window in v0.3 are simulation placeholders.

### 3. Onboard logging and power monitoring

- Reserve D10–D13 for SD SPI and remove status-LED writes on D13.
- Measure SD worst-case write latency, handle full/missing/failing storage, and
  preserve control/watchdog scheduling. Log dropped-record counts explicitly.
- Log temperature/pressure/depth, acquisition times, attitude, selected target speed,
  gradient validity/transition flag, all motor requests, voltage/current, state and faults.
- Validate analog references and voltage divider at maximum fully charged pack
  voltage. Replace the current simulation's 3S-like thresholds before 4S operation.
- Integrate measured voltage × current over actual intervals for energy estimates.

### 4. Extend the shared controller before real movement

- Define axes and signs: surge forward, yaw, depth positive down; document ESC
  mounting and polarity separately from logical thrust.
- Mix horizontal commands: left = surge − yaw, right = surge + yaw (sign depends
  on frame convention). Bound/scale combined commands and preserve neutral on faults.
- Add heading control without claiming precise horizontal position. A Nano + IMU
  alone does not provide reliable absolute x/y underwater localisation.
- Test normal controls, saturation, reversals, stalls, freshness loss and stop before
  connecting propulsion power. Identify gains using measured vehicle response.

### 5. True hardware-in-loop option

The current USB demo is not an external-plant HIL loop. A future HIL test should:

1. Simulate water/vehicle motion on the PC.
2. Send framed, versioned, timestamped virtual sensor samples to the physical Nano.
3. Run actual firmware control and safety logic on the Nano.
4. Receive bounded actuator requests and use them to advance the PC plant.
5. Stop on stale/missing/invalid HIL frames, without energising ESC output pins.

Require a separate compile-time or explicit disarmed-only HIL mode, physical
outputs disabled, bounded message buffers, sequence numbers and integrity checks.
Avoid using slow USB CSV telemetry as the sole 20 Hz control input/output protocol.

### 6. Physical validation and research experiment

- Finalise mass/buoyancy, power budget, fuse/wire ratings, enclosure size and recovery.
- Test an empty enclosure and installed seals before adding electronics/battery.
- Validate one vertical propulsion channel before three-thruster operation.
- Demonstrate constant-speed descent, hold and ascent with complete onboard logs.
- Validate adaptive slowing with independent reference profiles, then optional revisits.
- Compare normal, slow and adaptive profiles with a common time allowance; measure
  profile/boundary-depth errors, duration and energy, repeat trials and inspect mixing.

## Nano resource gate

v0.3 currently builds to 11,638 bytes flash and 433 bytes static SRAM, before real
sensor/storage drivers. Classic Nano SRAM is 2 KB. SD buffers, I2C, IMU libraries,
serial queues and stack must be measured together. Use fixed storage, flash strings
and bounded streaming. If the combined design lacks measured stack/timing margin,
reduce scope or change board before promising that every dashboard feature fits.

## Demo operating notes

Start `python3 lab/server.py`, open http://127.0.0.1:8765/demo2d.
Use arrows or WASD: left/right = reverse/forward, up/down = ascend/descend.
There are hold-to-drive touch buttons, Stop (Space), reset, pause and CSV export.
Keys/pointer inputs are cleared when focus is lost or the page is hidden.
Stop removes virtual thrust; drag and buoyancy can keep the toy vehicle moving.
The demo uses x/depth, keeps pitch fixed, and displays a lagged temperature probe
crossing a horizontal thermal layer. It does not implement adaptive control or send
commands to the board. The existing vertical research lab remains at `/`.

## Unified lab update — 19 October 2026

The profile lab and 2D movement demo now share the main page. Nano profile
telemetry controls displayed depth/temperature/state; horizontal x remains a
browser visualization. Free swim remains browser physics, with no board steering
or PC-to-Nano virtual sensor injection.
Firmware v0.4 source adds read-only CONFIG (also returned by HELLO) for compiled
controller and simulator constants; this does not add parameter editing, EEPROM
storage, sensor drivers, horizontal control or HIL. Desktop tests and AVR build
pass. Physical v0.4 installation subsequently succeeded after USB reconnection: full
flash verification, live HELLO/CONFIG through the actual bridge, and a short DEMO
followed by confirmed DISARM all passed. Earlier transfer failures remain logged.

## v0.6 architecture correction: controller-owned exploration

Adaptive exploration now belongs to shared firmware `Explorer.h`, with measured
position/velocity/temperature input and motion-request output. Nano USB can run
the decision algorithm against the lab plant; native C++ uses the exact same
header. This supersedes the browser-only trajectory planner as the route toward
the physical research AUV. Free swim remains an illustrative comparison tool.
See [v0.6 integration and deployment limits](NANO_V06_EXPLORATION.md).

## Current v0.7 travel objective

The active controller now reserves a travel budget for broad reconnaissance and
spends local travel on new spatial targets along/across observed thermal
features. Sparse tracks replace the full dense sweep. See
[Nano v0.7](NANO_V07_BUDGETED_SAMPLING.md) for the actual-board evidence and
comparisons, including cases with worse global reconstruction.
