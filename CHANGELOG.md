# Changelog

## v0.14 — bounded exploration that resumes the profile

- Limit the complete unvisited-water phase to 10 s; waypoint changes cannot restart it.
- Keep unvisited targets local; return to the saved descent line/depth after search or exhaustion.
- Resume vertical descent with 0.25 m progress before rearming another investigation.
- Ascend and complete at the surface after reaching 2.7 m; quiet water goes straight down/up.
- Retain the 8 s local limit. Bound checkpoint return and stalled ascent with explicit recovery behavior.
- Add Return/Ascend telemetry states, update lab labels and verify full mission completion.

## v0.13 — proposal-aligned vertical evaluation

- Remember measured transition depth bands for a slower return ascent; clear acquisition history at reversal.
- Check gradients along exploration transits and enforce a vector speed-request cap.
- Report when sensor/detection margins cannot fit the eight-second local allowance.
- Research view and reproducible CLI: fixed-fast, fixed-slow and adaptive profiles, equal maximum allowance, separate descent/ascent metrics, coverage and missing boundary estimates.
- Persist complete session CSVs beyond the live history limit; isolate native library builds.
- Review all five original proposal pages and document experimental definitions, illustrative results and physical validation gaps.
- Firmware identity v0.13; USB exploration frame unchanged. Motors remain disabled.

## v0.12 — initial public source preparation

- Arduino Nano/native shared adaptive exploration controller.
- Eight-second complete local visits and holds; retained spatial memory.
- Short adjoining probe legs and frontier target scoring.
- Local web laboratory with profile, free-swim and adaptive-exploration activities.
- Portable USB adapter selection with explicit serial-port override.
- Offline/firmware tests and GitHub Actions checks.

This is a simulated-water prototype with motor outputs disabled. No real-sensor or physical-vehicle deployment is claimed.
