# Electronics integration notes

## Proposed pin allocation

| Nano pin | Signal | Status |
| --- | --- | --- |
| D0 / D1 | USB serial service link | Used; avoid attaching another UART device |
| D2 | Normally closed dry leak loop to GND | Used, internal pull-up; HIGH faults |
| D3 | Left reversible ESC signal | Reserved; detached by default |
| D5 | Right reversible ESC signal | Reserved; detached by default |
| D6 | Vertical reversible ESC signal | Reserved; detached by default |
| D7 | Maintained arm-permit switch to GND | Used, internal pull-up; LOW permits arming |
| D10 | Future SD card chip select | Reserved |
| D11 / D12 / D13 | Future SD SPI MOSI / MISO / SCK | Reserved; D13 LED use must be removed for SPI |
| A0 | Future battery voltage divider | Reserved, no driver |
| A1 | Future current monitor analog input | Reserved, no driver |
| A4 / A5 | I2C SDA / SCL for pressure / IMU | Reserved, no drivers |
| D4 | Future digital temperature probe | Reserved, no driver |

D2 expects an isolated digital dry-contact loop or a compatible interface, **not
bare water electrodes**. Open circuit means leak or broken wire. A short to ground
can hide a leak, so proof-test the loop before each real run. Simulation also
requires this loop to be closed. D7 is a software permit, not a power disconnect.

Servo uses a timer to produce pulses on these digital pins; they are not driven
with `analogWrite()`. Review timer conflicts before adding another timing library.

Use a fused battery branch with accessible isolation for ESC power and a separate
regulated logic branch. Power thrusters through suitable ESCs, never from Nano
pins or its regulator. Connect signal ground according to ESC isolation topology.
Confirm each module's supply voltage and logic levels; a classic Nano is a 5 V
board and many sensors and SD cards need 3.3 V interfaces. Size the voltage divider
for the highest possible battery voltage plus margin before wiring A0.

## Real sensor adapter contract

Implement `Sensors::begin()` and `Sensors::read()` only after selecting components.
The main loop calls `read()` every 50 ms. Drivers must avoid long conversion waits:
start a conversion, return, and collect it on a later tick. Configure I2C timeouts
where supported and measure worst-case bus/storage latency against the watchdog.

Return `valid=false` until every required channel has a valid, calibrated reading.
Retain individual channel timestamps internally; return the **oldest** of those
in `Sample::acquiredMs`, using rollover-safe age comparisons. A cached reading must
not acquire a fresh timestamp merely because `read()` was called again. Choose
per-channel freshness limits or revise the 500 ms global limit for slower probes.

Required quantities:

- Raw and filtered temperature in °C; reject CRC failures and device error codes.
- Absolute pressure in mbar; raw and filtered depth in metres, positive downward.
  Establish surface reference while disarmed at the surface; never auto-zero at depth.
  With pressure in mbar, depth = `(pressure - surfacePressure) * 100 / (rho * g)`.
  Set density for the actual water and preserve the absolute pressure in the log.
- Vertical speed in m/s from filtered depth and actual acquisition intervals.
- Calibrated roll and pitch in degrees, including tilt validity.
- Battery voltage in V and signed battery current in A with calibrated scaling.
- Leak state from the selected interface. The sketch also ORs in the D2 interlock.

Measure pressure/temperature probe height offset and sensor lag. Log their mounting
and calibration, and use the offset to align temperature with pressure-derived
depth during analysis. Do not silently replace invalid values with plausible ones.

## Motor integration sequence

1. Complete sensor acquisition; with motor outputs still disabled, verify preflight
   rejects missing, stale, disconnected or out-of-range channels.
2. Confirm the ESC supports reversible servo pulses, its neutral/deadband/endpoints,
   required arming time, signal voltage and signal-loss behavior. Adjust `Config.h`.
3. Check mechanical thrust direction with an appropriate supervised fixture and
   manufacturer-approved cooling/water conditions. `VERTICAL_SIGN` maps down-thrust.
4. With the vehicle restrained appropriately and recovery available, enable real
   outputs only after `SIMULATED_SENSORS=false`. The compiler rejects the opposite.
5. Verify boot, reset, STOP, unplugged arm loop, leak loop and stalled firmware
   produce the expected physical response. Measure startup pulses and watchdog
   recovery on the actual board; software tests do not establish these behaviors.
6. Tune buoyancy, trim, gains and limits in shallow supervised water before missions.

In this base, hardware-mode preflight remains blocked until the sensor adapter is
implemented. Hardware gains and limits have not been validated. Horizontal ESCs
always receive neutral. Powered fault ascent, yaw control and storage readiness
must be designed and tested before extending this base toward the full proposal.
