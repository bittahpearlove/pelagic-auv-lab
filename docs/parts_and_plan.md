# AUV parts and development plan

Prepared 19 October 2026. Starting inventory: classic Arduino Nano and working USB
cable. Firmware is uploaded in simulated mode, with motor outputs disabled.

Target: supervised shallow-water temperature profiling with two horizontal
thrusters and one vertical thruster. Exact suppliers, prices and vehicle size
remain open until budget, purchasing country, operating depth and pool access are
confirmed. Component names below are candidates, not a completed compatibility BOM.

## Stage 1: inexpensive bench equipment

| Quantity | Item | Selection notes |
| --- | --- | --- |
| 1 | Solderless breadboard | For logic-level bench wiring only |
| 1 set | Male/male and male/female jumper wires | Match the Nano's fitted headers |
| 1 set | Nano headers, if missing | Solder before breadboard use |
| 2 | Small maintained switches | Arm permit and simulated dry leak loop |
| 1 assortment | Resistors including 4.7 kΩ | Temperature pull-up and later test circuits |
| 1 | Digital multimeter | Voltage, continuity, resistance |
| 1 | Soldering iron plus solder, cutters and heat-shrink | Borrow workshop tools where possible |
| 1 | Optional DS18B20 three-wire probe assembly | Cheap temperature-driver learning; verify probe sealing and authenticity |

A DS18B20 is a learning option, not a final research-probe commitment. The IC's
specified accuracy is ±0.5°C from -10 to 85°C. At 12-bit resolution a conversion
can take 750 ms; this is NOT the assembled probe's thermal time constant. The
existing 500 ms freshness policy needs changing to support this conversion rate,
or use another acquisition configuration. Measure the response of the complete
probe and cable assembly before using it for moving profiles. Use externally
powered three-wire operation for the initial driver.

Source: https://www.analog.com/media/en/technical-documentation/data-sheets/ds18b20.pdf

## Stage 2: measurement and logging assembly

| Quantity | Item | Selection notes |
| --- | --- | --- |
| 1 | Underwater absolute-pressure sensor | Candidate: Bar02/MS5837-02BA, appropriate for a shallow pool |
| 1 | Dedicated water-temperature probe | Choose for accuracy, installed response time and mounting; Celsius/TSYS01 is a candidate |
| 1 | Bidirectional 5 V ↔ 3.3 V I2C level-shifter module | Check pull-ups and bus speed; pressure and temperature candidates require 3.3 V logic |
| 1 | IMU breakout | Accel + gyro for tilt; add a calibrated heading solution for later yaw control; verify Nano library RAM/flash needs |
| 1 | SPI microSD module and card | Module must explicitly accommodate a 5 V host and provide correct SD voltage regulation/translation |
| 1 set | Leak sensor/interface and sensing contacts | Must translate dry/wet states to the fail-safe D2 interface expected by the firmware |
| As needed | Sensor mating cables and connectors | Include matching JST GH or supplier connectors; supplied sensor leads are not necessarily Nano jumpers |
| Borrow 1 | Reference thermometer | Calibration reference independent of the vehicle probe |

Bar02 is specified for roughly 0–10 m operating depth; this does not establish a
safe depth for the whole vehicle. Its advertised 0.16 mm resolution is not its
measurement accuracy. Use surface calibration and validate the actual error.
It requires drying for at least two hours daily. A pressure breakout must have a
wet-facing sensing element and suitable housing seal; a generic air-pressure
board placed inside the sealed housing will not measure external water depth.

Source: https://bluerobotics.com/store/sensors-cameras/sensors/bar-depth-pressure-sensor/

Celsius is a scientific-probe candidate rather than a required brand. The current
product page describes a TSYS01 version with ±0.1°C accuracy and reports a thermal
time constant of 1 s at 0.5 m/s flow and 2 s in still water. It also announces a
future TMP119 revision: confirm the actual shipped revision before writing the
driver. The cable side is not waterproof on its own: seal the bulkhead through an
enclosure. Its supply range does not make its I2C lines 5 V tolerant. A remote
boom mounting needs a sealed probe-side arrangement and enclosure penetrator;
do not assume the whole sensor can simply be submerged on an extension cable.

Source: https://bluerobotics.com/store/sensors-cameras/sensors/celsius-sensor-r1/

## Stage 3: one-thruster vertical prototype

Buy and validate one propulsion channel before committing to three.

| Quantity | Item | Selection notes |
| --- | --- | --- |
| 1 initially, 3 total | Underwater thruster | Size from buoyancy imbalance, drag, desired speed and total mass; guarded propeller |
| 1 initially, 3 total | Matching reversible brushless ESC | Forward/reverse servo PWM, neutral arming, signal-loss behavior, thermal/current rating |
| 1 | Battery pack | Voltage, peak current, capacity and physical size chosen after propulsion calculations |
| 1 | Chemistry/cell-count-compatible charger | Include balancing where the selected pack requires it |
| 1 | Regulated 5 V DC/DC converter | Independent electronics power branch; input rated for fully charged pack |
| 1 set | Fuse, holder, accessible power isolator and distribution wiring | Size to measured loads, cable ratings and fault protection requirements |
| 1 | Suitable current monitor | Must tolerate maximum pack voltage and total motor current; many small shunt breakout boards cannot |
| 1 set | Voltage-divider components | Scale fully charged battery plus margin into Nano ADC range; calibrate |
| As needed | Power connectors, correctly sized wire, terminals and strain relief | No motor power through breadboard or Nano regulator |
| Borrow 1 | Current-limited lab supply | For low-power electronics bring-up; it may not be suitable for thruster current |

T200 + Basic ESC is a documented example, not an automatic recommendation for a
small vehicle. At 12 V, each T200 can draw 17 A at full throttle, so three could
total approximately 51 A before electronics. At 16 V the published per-thruster
figure is 24 A. Size the complete power system for its actual operating envelope;
firmware throttle limits alone do not establish adequate hardware protection.
The starter firmware's 10 A current limit and 10.5 V battery limit are placeholders
and must be changed to match the selected design.

Sources:
- https://bluerobotics.com/store/thrusters/t100-t200-thrusters/t200-thruster-r2-rp/
- https://bluerobotics.com/learn/technical-reference/
- https://bluerobotics.com/learn/control-the-basic-esc-with-an-rc-transmitter/

## Stage 4: housing and complete vehicle

| Quantity | Item | Selection notes |
| --- | --- | --- |
| 1 assembly | Depth-rated electronics enclosure with end caps and seals | Size after laying out battery, ESCs, wiring and electronics; include thermal management |
| As needed | Cable penetrators matched to exact cable diameters | Plan every cable and wet-facing sensor port before ordering end caps |
| 1 set | Seal consumables, spare O-rings and compatible lubricant | Follow enclosure material/manufacturer guidance |
| Borrow 1 set | Manufacturer-compatible vacuum/leak-test equipment | Vacuum integrity testing does not substitute for pressure/depth validation |
| 1 | Frame with thruster mounts | Corrosion-aware materials and service access |
| As needed | Depth-appropriate buoyancy and adjustable ballast | Positive buoyancy, buoyancy above mass centre; verify trim with installed components |
| 1 | Adjustable sensor mount/boom | Position away from electronics heat and thruster wash; record vertical offset |
| 1 | Recovery arrangement | Supervised pool retrieval plan, attachment point and suitable line where allowed; manage snag risk |
| As needed | Fasteners, brackets, guards, cable clamps and internal mounting plate | Include assembly mass in the buoyancy budget |

Do enclosure-only water/leak tests with no electronics or battery first. Validate
sealing and recovery before powered trials. The initial firmware faults to neutral;
it does not perform a powered abort ascent. Positive buoyancy and recovery planning
are part of the first vehicle design.

## Work possible before purchases

1. Document maximum test depth, target speed, mission duration and temperature-error
   goal. Confirm pool access, supervision and a suitable thermal test column.
2. Practice serial commands and capture/plot simulated logs. With no jumpers yet,
   ARM rejection from the open permit is expected; do not bypass the interlocks.
3. Build a simulation test matrix: missing samples, noise, delayed temperature,
   sustained tilt, leak, battery sag, timeouts and controller resets.
4. Develop a log parser and plots of temperature vs depth, depth vs time and state.
5. Make mass/volume/buoyancy and power/energy budgets; use component datasheets and
   CAD dimensions before choosing the battery, thrusters or housing.
6. Draw the wiring diagram and reserve pins. D13 is currently a status LED but must
   be handed over to SPI clock when microSD logging is implemented.
7. Implement sensor drivers one device at a time and profile RAM, flash and timing.
   Recheck Nano capacity after combining IMU, storage and adaptive processing.
8. Add bounded onboard logging and storage-ready preflight before untethered runs.
9. Characterise probe calibration and response before implementing gradient-based
   adaptive revisits. Use independent reference measurements for comparisons.

Milestone order: bench logger → one-thruster depth control → three-thruster vehicle
→ constant-speed profiles → adaptive revisit and comparative experiments.
