# Local laboratory

See the root [README](../README.md) for setup and firmware upload. Start `python3 lab/server.py` and open http://127.0.0.1:8765/demo2d. The server compiles an isolated C++ controller library per instance; it never overwrites a library mapped by another process. Only one process can own the Nano USB port.

## Activities

- Adaptive exploration: shared Nano/native controller chooses movement from measured inputs. Each local visit lasts at most 8 simulated seconds, followed by at most 10 s of local frontier sampling. The AUV returns to the saved descent checkpoint, resumes profiling, then surfaces after reaching 2.7 m. See [current policy](../docs/NANO_V014_PROFILE_RETURN.md).
- Adaptive profile: finite descent/hold/ascent experiment, with adaptive or fixed speed, on the native controller or the board's own simulated sensor model.
- Research view: compare native fixed-fast, fixed-slow and adaptive vertical profiles, with the same 180 s maximum allowance and three paired-noise repeats. Descent/ascent metrics use common depth bins and report missing boundary estimates. One profile per trial; early finishes leave unused allowance. This uses ideal simulated reference water, not a tank instrument. CLI: `python3 tools/compare_profiles.py`.
- Free swim: keyboard-driven browser motion and sample mapping. It does not steer the Nano.

The true water map is visible for evaluation. Only measured, delayed temperature and estimated position/velocity are sent to the exploration controller. The estimated map uses position and probe samples; sampling support is a heuristic, not calibrated confidence.

## USB and data

Choose Nano USB, then Connect Nano. Use `--serial-port /dev/ttyUSB0` (or your own port) if adapter selection is ambiguous. At 115200 baud the bridge sends HELLO and checks simulated=1, motors=0 and the firmware schema. Exploration requires v0.14. All browser tabs share one experiment and serial connection.

Stop sends an operator stop; Reset/disconnect sends DISARM. Exploration requires live observations and stops on a lost link. The lab never enables motor outputs. Server shutdown attempts DISARM. Closing a browser tab is not an operator Stop.

Full session CSVs persist with unique names in `output/runs/`. Export reads the complete session; Reset/new run closes the old log without deleting it. The screen retains the last 10,000 sample records and 500 console entries. Buffered samples flush every 20 records, on terminal states and export; a crash can lose final buffered records. Research CSV/JSON are in `output/experiments/profile_comparison/` and are overwritten by the next comparison; archive each recorded experiment. Native playback supports 1×, 4× and 10×; local deadlines use simulated time. USB mode runs live controller decisions with the laboratory plant.

The web server listens on loopback, checks Host/Origin for writes and requires a per-process token. It is a local research tool, not a public service.
