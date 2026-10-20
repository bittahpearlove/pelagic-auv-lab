# Nano v0.15: two motor-disabled bench images

The classic ATmega328P Nano cannot hold the full new estimator/diagnostics and the 2D explorer in one image. Native builds include both. Arduino builds default to the **research image**; the optional exploration image preserves the bounded 2D controller. Both retain legacy vertical profiles and fixed-medium mode. USB identity reports capabilities explicitly:

    # AUV Nano adaptive v0.15; simulated=1; motors=0
    # FEATURES,research=1,exploration=0

The exploration image reports research=0,exploration=1. The lab disables unavailable mode choices. Reflash when changing experiment family. A capability bit is not permission to enable motors.

```sh
# Install arduino:avr 1.8.8 and Servo 1.3.0 first.
bash tools/build_nano.sh research
# Or: bash tools/build_nano.sh exploration
bash tools/arduino.sh upload --fqbn arduino:avr:nano:cpu=atmega328 --port /dev/ttyUSB0 --input-dir build/nano-v015-research --verify
```

Close every USB owner before uploading. Select the appropriate processor/bootloader for a different Nano. At this build, research uses 25,074/30,720 flash bytes and 932/2,048 static SRAM bytes; exploration uses 28,106 and 1,098 respectively (Arduino CLI 1.5.2-rc.1, AVR core 1.8.8, Servo 1.3.0). Static remaining RAM is not a measured worst-case stack margin. CI compiles both images; local physical HIL measures runtime/stack separately.

## Commands and external observations

115200 baud, newline terminated. Existing HELLO/CONFIG/STATUS/STOP/DISARM/ARM/START/DEMO and 27-column profile telemetry remain. ADAPT/FAST/SLOW/MEDIUM select modes 0–3; LAG/UNGATED select 4–5 in the research image. Change modes and calibration only when disarmed.

Research-only bench commands:

    CAL,tauNominal,tauMax,epsilonC,noiseSigmaC
    PROF,mode,tauNominal,tauMax,epsilonC,noiseSigmaC,allowanceMs
    P,sequence,currentMs,acquiredMs,estimatedDepthM,estimatedVerticalMps,probeTemperatureC,flags

CAL changes provisional settings for the built-in simulated DEMO. PROF arms a motor-disabled externally observed trial at experiment time zero, including five-second arming. P supplies **only measured/estimated inputs**, never true gradients or boundary location. Flags are additive: valid=1, leak=2, low battery=4, tilt=8, overcurrent=16. Normal flags=1. Sequence must advance (uint32 rollover supported); currentMs must advance with gap at most 500 ms. Acquisition timestamps retain their original time when observations are lost. The sensor freshness limit is 500 ms. Unordered/repeated sequence, nonfinite data, invalid flags or stale observations fault; a missing external link stops after one wall second while active. Sequence/time validation is separate from sensor acquisition age.

`PROF`/`CAL` are available only with simulated sensors and disabled outputs. Real sensor drivers are not implemented by this protocol.

## Research diagnostics frame

`# PRF,` precedes 35 comma-separated values: sequence, acquisition timestamp, 30 shared-core outputs, decision microseconds, maximum decision microseconds, painted stack margin bytes. Built-in telemetry uses sequence zero; external requests echo their sequence. The old numeric CSV schema is unchanged.

Shared-core output indices (zero based, after sequence and acquisition timestamp):

| Indices | Meaning |
|---|---|
| 0–8 | state, fault bits, next command, target depth, requested speed, reported gradient magnitude, gradient valid, transition candidate, mode |
| 9–11 | legacy learned-band valid, low depth, high depth |
| 12–17 | current-depth estimated T, signed gradient, fit residual, fit valid, policy reason, gradient uncertainty proxy |
| 18–23 | condition proxy, observed depth span, assumed tau, upper tau, reached bottom, budget return |
| 24–29 | geometry valid, fit status, unconstrained model speed limit, approximate achieved lag error, support depth, support temperature |

Policy reasons: 0 fixed, 1 conservative invalid-fit fallback, 2 lag-limited, 3 minimum speed prevents tolerance, 4 quiet, 5 allowance return, 6 rate-limited, 7 hysteresis. Fit status: 0 good, 1 warming, 2 geometry, 3 conditioning, 4 residual/uncertainty, 5 stale, 6 invalid input. These codes explain decisions; they do not certify accuracy.

Timing covers the controller decision, excluding UART formatting/transmission. The 20 Hz nominal tick is 50,000 µs. Stack paint begins before setup allocations and leaves a conservative 64-byte guard; reported unused margin applies only to exercised code paths. No heap allocation is introduced by the estimator. New physical drivers/logging require fresh memory and scheduling tests. Serial input processing is bounded to 32 bytes per loop and overlong commands are rejected.

The exploration EXP frame remains 16 outputs; its final historical recheck field is a reserved zero. The host calls it `reserved_legacy_rechecks`. Full retrace feasibility is rejected before selecting motion; partial inspection remains limited to eight seconds.

## Verification tools

```sh
bash tools/test.sh
python3 tests/lab_test.py
python3 tests/research_test.py
# Connected board, research image, no other serial owner:
python3 tools/verify_nano_research.py
# Exploration image instead:
python3 tools/verify_nano_exploration.py
```

Both tools use virtual observations with an actual Nano making decisions. They do not validate wet probes, position estimation, hydrodynamics or physical recovery. The research tool tests a complete response-aware route, native/AVR numeric differences, unordered packets, stale acquisitions, leak and missing-link stops, then disarms. Stop neutralizes commands; fault ascent is not implemented. Motors remain disabled throughout.

Measured on the connected Nano in this pass: 1,417 profile observations, complete route, zero discrete fit/policy differences from native; maximum signed-gradient difference 0.0106 °C/m and current-temperature difference 0.00052 °C. Maximum decision time 3,212 µs; minimum observed painted stack margin 815 bytes. Reordered sequence, stale acquisition, leak and missing-link faults stopped commands. Exploration completed 736 observations / 73.5 simulated seconds, checkpoint return and surfacing, with operator Stop and disarm verified. These are exercised bench paths only. The final installed image is research, disarmed, simulated=1, motors=0.
