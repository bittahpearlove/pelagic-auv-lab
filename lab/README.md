# Local laboratory

Start with **Start here**. Set up a vertical profile or open **Compare strategies**. Settings presets help choose water conditions; **Run** opens the live view. Detailed scientific tables and traces expand on demand. See [the follow-up guide](../docs/V015_FOLLOWUP.md) for failure-aware scoring, saved results and rejection diagnostics.

Current version: v0.15. See [research methods](../docs/RESEARCH_V015.md) and [image/protocol guide](../docs/NANO_V015_RESEARCH.md).

See the root [README](../README.md) for setup and firmware upload. Start `python3 lab/server.py` and open http://127.0.0.1:8765/demo2d. The server compiles an isolated C++ controller library per instance; it never overwrites a library mapped by another process. Only one process can own the Nano USB port.

## Guided workflow

Start here introduces the research question and three paths. Single profile visualises one mission; Compare strategies shows the primary response/forward versus raw-baseline comparison, failure-aware loss, full-RMSE availability, and rejection status by depth. Settings holds water/probe parameters and the error cap/miss penalty. Changes apply to the next comparison, never retroactively to saved results.

Loss defaults are 30 cm cap and 30 cm miss penalty. Flat-water false alarms remain separate. Diagnostic strips pool fresh readings by depth; status percentages use an evaluator-only +/-15 cm reference-transition window. They are not calibrated confidence or proof of a failure cause. See [review follow-up](../docs/REVIEW_FOLLOWUP_20261020.md).

## Activities

- Adaptive exploration: shared Nano/native controller chooses movement from measured inputs. Each local visit lasts at most 8 simulated seconds, followed by at most 10 s of local frontier sampling. The AUV returns to the saved descent checkpoint, resumes profiling, then surfaces after reaching 2.7 m. See [current policy](../docs/NANO_V014_PROFILE_RETURN.md).
- Adaptive profile: finite descent/hold/ascent experiment, with adaptive or fixed speed, on the native controller or the board's own simulated sensor model.
- Research view: compare native six strategies (fast, slow, medium, legacy, response-aware and ungated), with the same 180 s maximum allowance and configurable paired scenarios. Descent/ascent metrics distinguish raw/forward reconstruction, full and covered errors, coverage and failures. One profile per trial; early finishes leave unused allowance. This uses ideal simulated reference water, not a tank instrument. CLI: `python3 tools/compare_profiles.py`.
- Free swim: keyboard-driven browser motion and sample mapping. It does not steer the Nano.

The true water map is visible for evaluation. Only measured, delayed temperature and estimated position/velocity are sent to the exploration controller. The estimated map uses position and probe samples; sampling support is a heuristic, not calibrated confidence.

## USB and data

Choose Nano USB, then Connect Nano. Use `--serial-port /dev/ttyUSB0` (or your own port) if adapter selection is ambiguous. At 115200 baud the bridge sends HELLO and checks simulated=1, motors=0 and the firmware schema. Exploration requires the v0.15 exploration image; response-aware profiles need the research image. Native builds include both. All browser tabs share one experiment and serial connection.

Stop sends an operator stop; Reset/disconnect sends DISARM. Exploration requires live observations and stops on a lost link. The lab never enables motor outputs. Server shutdown attempts DISARM. Closing a browser tab is not an operator Stop.

Full session CSVs persist with unique names in `output/runs/`. Export reads the complete session; Reset/new run closes the old log without deleting it. The screen retains the last 10,000 sample records and 500 console entries. Buffered samples flush every 20 records, on terminal states and export; a crash can lose final buffered records. Research CSV/JSON have unique immutable run directories under `output/experiments/research/`; retain the complete manifest and samples together. Native playback supports 1×, 4× and 10×; local deadlines use simulated time. USB mode runs live controller decisions with the laboratory plant.

The web server listens on loopback, checks Host/Origin for writes and requires a per-process token. It is a local research tool, not a public service.
