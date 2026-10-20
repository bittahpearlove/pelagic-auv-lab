# Local laboratory

See the root [README](../README.md) for setup and firmware upload. Start `python3 lab/server.py` and open http://127.0.0.1:8765/demo2d. The server compiles the C++ controller into `build/lab/core.so`; stop it before running tests or verification scripts that rebuild the same library.

## Activities

- Adaptive exploration: shared Nano/native controller chooses movement from measured inputs. Each local visit and hold lasts at most 8 simulated seconds; retained visited-cell memory guides frontier targets. See [current policy](../docs/NANO_V012_BOUNDED_LOCAL.md).
- Adaptive profile: finite descent/hold/ascent experiment, with adaptive or fixed speed, on the native controller or the board's own simulated sensor model.
- Free swim: keyboard-driven browser motion and sample mapping. It does not steer the Nano.

The true water map is visible for evaluation. Only measured, delayed temperature and estimated position/velocity are sent to the exploration controller. The estimated map uses position and probe samples; sampling support is a heuristic, not calibrated confidence.

## USB and data

Choose Nano USB, then Connect Nano. Use `--serial-port /dev/ttyUSB0` (or your own port) if adapter selection is ambiguous. At 115200 baud the bridge sends HELLO and checks simulated=1, motors=0 and the firmware schema. Exploration requires v0.12. All browser tabs share one experiment and serial connection.

Stop sends an operator stop; Reset/disconnect sends DISARM. Exploration requires live observations and stops on a lost link. The lab never enables motor outputs. Server shutdown attempts DISARM. Closing a browser tab is not an operator Stop.

The server retains the last 10,000 sample records and 500 console entries. Export before Reset/new run or server shutdown; storage is not automatically persistent. Native playback supports 1×, 4× and 10×; local deadlines use simulated time. USB mode runs live controller decisions with the laboratory plant.

The web server listens on loopback, checks Host/Origin for writes and requires a per-process token. It is a local research tool, not a public service.
