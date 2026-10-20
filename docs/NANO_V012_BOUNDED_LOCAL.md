> Superseded by [v0.13 research alignment and trajectory corrections](RESEARCH_ALIGNMENT_V013.md). The 17-field EXP frame and eight-second limits remain; firmware identity is now v0.13.

# Nano v0.12: bounded local visits and shorter paths

Each complete local visit has an 8,000 ms observation-clock deadline. The initial upward retrace and subsequent probing share that deadline; it is not reset when changing from retrace to probe. Each stationary hold also has an 8,000 ms deadline. Deadlines cause a new target decision, not mission termination. Stop, Reset, invalid observations and lost connection can still terminate a run. No total time or travelled-distance budget is imposed.

To fit useful local motion into eight seconds, the retrace is at most 0.12 m (shorter for slower probes), followed by two adjoining 0.125 m probe legs. The old four-leg diamond is removed. Probe targets already in visited cells are skipped. The mission-long 192-byte visited bitmap remains intact.

On expiry or after a short probe, select an unvisited cell centre within x=0.4–7.6 m and depth=0.2–2.7 m. Score candidates using squared distance, a penalty for sampled cells along seven points of the direct transit, and a penalty for sharp reversal relative to current velocity. This is a simple path heuristic, not a globally optimal route or an obstacle-avoidance planner. The tighter arrival tolerance ensures the vehicle enters the target cell before retargeting. Known water can still be crossed to reach new water.

New phase 6 is transit to an unvisited target. At arrival, measured temperature contrast determines whether to start another short local investigation or move to another new target. Local spatial bounds follow the investigated location; transit can leave the previous local patch. This is opportunistic frontier selection, with no prescribed sweep trajectory.

Uniform water starts with the original descent, holds for at most eight seconds, then explores unvisited targets. If all useful candidate cells in the permitted tank domain are visited, phase 7 explicitly reports Domain sampled and stays active at a bounded hold until Stop. This exceptional state cannot be resolved by an eight-second timer without revisiting known water; the controller does not erase its memory or invent novel locations.

The old temperature-triggered stationary recheck loop is superseded by these bounded visits. The legacy rechecks telemetry field remains reserved at zero. Monitor phase remains 5; USB EXP layout is unchanged from v0.11 (sequence plus 16 values). Native and Nano use the same header. Simulator seconds are the deadline clock; at 10× playback eight simulated seconds pass in about 0.8 wall seconds.

Motors remain disabled. Real-world visited-location awareness still requires a position estimator; the lab supplies simulated positions. Visited cells record passage with a delayed probe, not verified temperature accuracy. Sensor response lag can limit what an eight-second visit resolves, especially for tau near eight seconds.
