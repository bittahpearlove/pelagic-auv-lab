# Temperature probes for adaptive boundary sampling

Our target is a tank-scale length–depth experiment with a classic 5 V Arduino Nano. Real sensor acquisition is still unimplemented. Firmware currently uses a virtual probe with adjustable response time. Values below are manufacturer specifications, checked 20 October 2026; suppliers' stock and delivery to Saint Petersburg are not verified.

## Candidate families

| Probe family / example | Why consider it | Nano integration and limits |
| --- | --- | --- |
| Small bead or glass NTC thermistor | Small thermal mass can make this a useful moving-probe sensor. An inexpensive, calibratable research option. | Resistance divider or bridge, low-noise excitation/readout, calibration and waterproof/pressure packaging. The Nano ADC alone is not a precision oceanographic instrument. Characterize the finished assembly; bare-element response does not describe a thick waterproof housing. |
| Blue Robotics Celsius / TSYS01 | Packaged subsea temperature sensor with specified ±0.1 °C absolute accuracy from −5 to 50 °C. Manufacturer time constant is 1 s at 0.5 m/s water flow and 2 s in still water. | I2C at 3.3 V logic; supply 3.3–5.5 V. Use a suitable bidirectional level converter with a classic 5 V Nano. The wet face must be installed through a sealed enclosure; the wire-exit back is not independently waterproof. Arduino library available. |
| Thin Pt100 / Pt1000 platinum RTD | Useful for a calibrated stationary reference or a robust probe when the specific package is fast enough. | Needs an RTD readout circuit, such as a suitable SPI converter, and lead-resistance compensation. Response depends on construction: the cited Omega PR-21 package specifies ≤3.5 s to 63% in water; that is not a universal Pt100 value. |
| RBR temperature logger / fast thermistor option | Professional comparison or reference instrument. RBRsolo4 T states ±0.002 °C calibration accuracy, about 1 s standard time constant or 100 ms with the fast option. | It is a self-contained logger with USB-C download, not a direct Nano sensor breakout. Synchronize clocks and characterize probe response/position. Obtain a quote and verify whether live data access is available for the chosen model if needed. |
| Sea-Bird SBE 3F | Professional fast oceanographic benchmark: manufacturer specifies roughly 0.07 s response and 0.001 °C initial accuracy. | Frequency output around 2–6 kHz and external 11–16 V supply. A custom interface, electrical review, calibration coefficients and acquisition clock are required; do not wire it to Nano logic without checking the manual. |
| DS18B20 in a waterproof probe | Accessible introductory tank instrument, suitable for learning acquisition and coarse profiles. | 1-Wire integration is straightforward. Chip accuracy is ±0.5 °C over −10 to 85 °C; 12-bit conversion can take 750 ms. That conversion interval is **not** its physical thermal time constant. Waterproof sheath construction varies and must be measured. |

## Recommendation for this experiment

For a first integrated system, Celsius/TSYS01 is a practical packaged candidate if delivery and price work. For resolving a sharp boundary during short local visits, investigate a faster low-mass thermistor assembly and a calibrated reference. Professional RBR/Sea-Bird instruments can be sought through an institute collaboration rather than treated as drop-in Nano accessories. A fast probe on the vehicle and an independent calibrated reference are more informative than several uncharacterized slow probes.

An eight-second visit does not guarantee a settled measurement. For a first-order sensor responding to a temperature step, approximately 95% settling requires 3 tau. Thus tau=2 s needs about six seconds after the step, while tau=0.1 s needs about 0.3 s. Motion crosses gradients continuously, making the step model only a starting approximation. At speed 0.05 m/s, v*tau is 0.10 m for tau=2 s and 0.005 m for tau=0.1 s. These are characteristic lag distances, not guaranteed boundary-position errors.

Absolute accuracy, short-term repeatability, resolution, sample interval and physical response time are different specifications. A fixed offset can cancel in a temperature difference; sensor noise and drift still affect our 0.08 °C trigger. Set thresholds from measured noise/repeatability rather than from displayed decimal places. Mount the probe away from electronics heat and characterize the effect of motion and thruster flow.

## First physical experiment

1. Use two well-mixed water baths at different stable temperatures and an independent calibrated reference. Log timestamps and reference readings.
2. Move the finished probe assembly between baths. Repeat warm-to-cold and cold-to-warm transfers under reproducible flow conditions.
3. Estimate the delay and time to 63.2% of the change (tau for an appropriate first-order fit); inspect the residuals before assuming that model is adequate.
4. Repeat in still water and at the intended profiling speed. Report the housing, mounting, immersion, sampling interval, calibration and fitted uncertainty.
5. Build a stationary tank reference profile, then compare fixed and adaptive trajectories with matched starting conditions. Score boundary-position error, elapsed time, travelled distance and spatial support. Log electrical power before making energy claims.

Temperature alone does not determine seawater density or identify every oceanographic front; conductivity/salinity and pressure become important for later field work. Begin with the controlled thermal tank question.

## Manufacturer sources

- [Blue Robotics Celsius specifications, integration and installation](https://bluerobotics.com/store/sensors-cameras/sensors/celsius-sensor-r1/)
- [Blue Robotics TSYS01 Arduino library](https://github.com/bluerobotics/BlueRobotics_TSYS01_Library)
- [RBRsolo4 T specifications](https://rbr-global.com/products/compact-loggers/rbrsolo-t/)
- [Sea-Bird SBE 3F specifications](https://www.seabird.com/products/sbe-3-oceanographic-temperature-sensor)
- [Omega PR-21 RTD package](https://www.dwyeromega.com/en-us/rtd-probes-with-mounting-threads-and-m12-connectors/p/PR-21)
- [Analog Devices DS18B20 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ds18b20.pdf)
- [Omega thermistor element specifications](https://assets.omega.com/spec/44000_THERMIS_ELEMENTS.pdf): response conditions for bare elements are not a water-rated assembled-probe specification.
