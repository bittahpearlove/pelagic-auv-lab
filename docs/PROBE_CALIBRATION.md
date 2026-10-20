# Installed-probe calibration and vertical-rig protocol

Status: procedure and analysis tool prepared; **no wet calibration has been performed**. Simulated tau values are hypotheses, not probe specifications.

Record probe model/serial privately, installation and sheath, reference instrument and its calibration, water temperatures/salinity, flow, date, acquisition timestamps and raw temperature. Measure the vertical offset between probe tip and pressure/depth reference, with sign convention positive down. Match both timestamps before estimating a gradient.

Use two well-mixed baths with a stable, measurable temperature difference. Measure both with a faster independent reference. Transfer the installed probe promptly between them while recording the immersion time; avoid exposing unsafe electronics. Record until a stable endpoint, ideally at least five fitted time constants. Repeat at least five heating and five cooling transfers at several representative flow speeds. Keep mounting and flow consistent with intended profiling. Separate mixing/transfer delay from sensor response; reject trials where the bath reference changes materially.

Prepare an isolated post-immersion CSV:

    time_s,temperature_c

Times must increase and the sample cadence should resolve the transient. The tool fits y=A+B exp(−t/tau), solving A/B for each candidate tau from 0.05–60 s. It reports residual RMSE, duration and search-edge warnings. It is a first-order fit, not a calibrated uncertainty interval. Inspect residuals versus time: systematic curvature, delay or flow dependence can require a richer model or a different sensor.

```sh
python3 tools/calibrate_probe.py step.csv --output step-fit.json
```

Do not choose tauMax from one clean synthetic fit. Summarize the spread across independent transfers and flow conditions; include reference uncertainty and transfer delay. Declare a conservative installed-probe range before evaluating a frozen speed policy. Retain unsuccessful fits and original CSVs.

For the first physical sampling comparison, use an encoder/marked vertical translation rig in a stable stratified tank. Measure a stationary reference profile before and after every block; document gradient drift and mixing. Randomize strategy order, run fixed-fast/medium/slow and legacy/new policies, keep maximum allowance and acquisition cadence common, and log achieved speed. Keep the reference data separate from firmware inputs. Repeat independent runs rather than treating each raw sample as a replicate. A warm/cold arrangement must remain stable long enough for a block; do not assume a uniform pool provides a thermocline.

Evaluate offset-corrected depth, boundary detection failures, full required-depth coverage, conditional error, total time, travelled distance and measured energy. Report physical findings separately from the toy plant. The rig is a valid first research platform even before an AUV hull and thrusters are available.
