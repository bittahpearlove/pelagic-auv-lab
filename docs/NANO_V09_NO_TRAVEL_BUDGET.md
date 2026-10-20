> Superseded by [v0.10 continuous exploration](NANO_V010_CONTINUOUS_EXPLORATION.md), which also removes time limits and automatic completion.

# Nano v0.9: no travel budget

The mission remains vertical descent, slow upward retrace after a sustained thermal change, one bounded local investigation, then finish. No sweep is introduced.

Neither total travelled distance nor local travelled distance stops the mission. Distance remains available in telemetry and CSV as `travel_m`; it is a research metric. There is no travel-budget setting or `path_budget_m` CSV column.

The local investigation retains its 100 s timeout and spatial bounds. The mission retains its 300 s timeout, depth bounds, observation validation and link timeout. Local investigation still finishes when observations are predictable, gradients are weak, candidate locations are already sampled, or geometry is insufficient.

USB start command: `EXPL,1,tau` (seconds, 0.1–8). The former third travel-budget argument is rejected by firmware. EXP replies retain measured distance and their existing layout. The lab requires firmware v0.9 for exploration.

Motor outputs remain disabled; water, sensors and motion are simulated by the laboratory. See [v0.8 geometry and trajectory](NANO_V08_VERTICAL_INVESTIGATION.md) for the unchanged movement policy; its distance limits are superseded by this document.
