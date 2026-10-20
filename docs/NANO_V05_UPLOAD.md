# Nano v0.5 — ready for the next USB connection

Status: v0.5 uploaded and physically verified. All 14,292 flash bytes matched;
live HELLO/CONFIG, WATER4, X5.3 and a brief simulated descent passed. The Nano
was then confirmed disarmed. Evidence: output/logs/nano_v05_upload.txt and
nano_v05_verified.json. The steps below remain available for future reflashing.
Motor outputs remain disabled and sensors remain simulated.

## What changed

The browser's free-swim field and adaptive-profile simulator now use the same
field definitions. Native profiling and Nano firmware share ThermalField.h.
The browser implementation is checked against shared numerical test cases.
Profiles remain vertical at a fixed simulated x; there is no horizontal navigation.
The temperature detector still estimates temperature change per depth travelled.
It cannot resolve a complete 2D gradient from a single vertical line.

The patch centre is now (5.3 m, layer_centre + 0.35 m). This keeps the default
patch within the 1 m profile mission when layer centre is 0.5 m. Patch amplitude
is 2 C, horizontal/vertical Gaussian scales 0.75/0.3 m. Sloped layers use
centre + 0.16*(x-4); lateral fronts are centred at x=4 with scale 5*width.

New bench commands, accepted only while DISARMED, simulated sensors enabled and
physical motor outputs disabled:

| Command | Field |
| --- | --- |
| WATER0 | Level layer |
| WATER1 | Sloping layer |
| WATER2 | Lateral front (changes across x) |
| WATER3 | Level layer plus warm patch |
| WATER4 | Sloping layer plus warm patch |
| X5.3 | Set fixed simulated profile x; allowed range 0.5–7.5 m |

HELLO and CONFIG now report 18 values, including current water_shape and
profile_x_m. CSV telemetry remains the same 27 columns. DISARM and DEMO retain
selected field/x; power reset restores Config.h defaults (WATER0, x=4).

## Upload when the Nano is attached

1. Connect the Nano directly by USB. In the lab, click Disconnect Nano if connected;
   close any Serial Monitor. Stop the lab server with Ctrl+C if necessary.
2. From the project directory, compile and upload with verification:

```sh
cd "/path/to/pelagic-auv-lab"
bash tools/arduino.sh compile --fqbn arduino:avr:nano:cpu=atmega328 --warnings all --build-path "$PWD/build/nano" firmware/auv_nano
bash tools/arduino.sh upload --port /dev/ttyUSB0 --fqbn arduino:avr:nano:cpu=atmega328 --input-dir "$PWD/build/nano" --verify firmware/auv_nano
```

The build checked here uses 14,292 bytes of flash (46%) and 453 bytes static RAM
(22%). Use the identified port if its name changes. This Nano previously verified
successfully with the normal atmega328/115200 bootloader setting. If USB transfer
fails, reconnect/check the data cable and retry; do not treat a failed upload as a
verified installation.

3. Restart `python3 lab/server.py`, open http://127.0.0.1:8765, choose Setup,
   Arduino Nano USB, then Connect Nano. Expect v0.5, simulated sensors, motors off,
   and CONFIG containing water_shape/profile_x_m. Older v0.4 can still supply
   telemetry; selecting different Nano fields remains disabled until v0.5.
4. Select Sloping layer + warm patch and profile x=5.3. The lab sends DISARM,
   WATER4, X5.300 and CONFIG. Read the acknowledgements in Console.
5. Run a profile, inspect Live/Maps, then Reset. Confirm DISARMED. Settings on Nano
   use compiled centre/width/drop/probe tau; these sliders are read-only in USB mode.
   For different onboard numeric values, edit Config.h and recompile/upload.

A pure lateral front has no vertical gradient at fixed x; a vertical mission should
not claim to map its horizontal gradient. Slow probe settling can still create
transients. For a detectable vertical transition, choose a layer/patch and ensure
its boundary lies within the mission's 0–1 m depth range.

## Compact lab controls

Live, Thermal maps and Console switch panels within the viewport. Setup opens
settings on narrow screens; desktop screens keep a settings sidebar. Run, Pause,
Reset, Stop and CSV stay in the top toolbar. Long explanations are collapsed in
help; setup/log content scrolls inside its panel. Profile and free swim retain the
same selected offline field/settings. Maps from a vertical profile show its fixed
x track and withhold an unobservable full 2D gradient.
