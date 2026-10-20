# Nano v0.14: bounded detours, resume descent, then surface

Historical v0.14 behavior. See [v0.15 model and image changes](NANO_V015_RESEARCH.md) and [current research methods](RESEARCH_V015.md). The short upward motion is now explicitly a partial inspection because full retrace is infeasible.

The v0.13 frontier search could keep selecting another unvisited target forever. Its waypoint changes restarted phase bookkeeping, and no transition restored the original descent mission. This was a route design bug, not a lack of temperature measurements.

The current route is:

1. Start at the selected x and descend toward 2.7 m.
2. On a persistent measured gradient, save the current depth as the resume checkpoint. Keep the original descent x. Slowly retrace and investigate locally for at most **8 s total**.
3. Sample nearby unvisited water for at most **10 s total** across all waypoint hops. Entering another target cell cannot renew this timer. No nested gradient-triggered detour may restart the local visit. Every observation continues to update the local fit when sufficiently displaced.
4. Return to the saved x/depth checkpoint. Visited memory must not forbid this intentional return. Resume descent, resetting reversal history. At least **0.25 m of additional depth progress** is required before another local investigation can trigger.
5. At the 2.7 m bottom criterion, ascend directly without new detours. Complete at depth ≤0.14 m with |vertical speed| <0.03 m/s, targeting 0.10 m. This represents the surface inside the virtual plant, whose lower depth bound is 0.08 m. Completion zeros motion requests.

Quiet water takes the direct down/up route. No sweep, global coverage objective, stationary exhaustion hold or endless frontier loop remains in exploration. The separate Research tab's controlled 1 m profiling comparison is unchanged.

## Bounds and exceptional cases

- Candidate unvisited targets are inside the local rectangle: ±0.45 m in x, 0.45 m above / 0.10 m below the detection depth, clipped to the tank. They cannot lead a chain of local searches across the entire tank.
- If no local unvisited target exists, return immediately to the saved checkpoint.
- Checkpoint return has a 15 s observation-clock watchdog. If it cannot reach the checkpoint, attempt ascent from the current x instead of returning to frontier search.
- Ascent has a 60 s observation-clock watchdog. Failure to reach the surface becomes explicit reason 6, recovery timeout; outputs are zeroed. In a real vehicle, neutral commands do not guarantee recovery. Motors remain disabled and physical recovery requires independent validation.
- Stop, invalid/out-of-order observations and lost observation links still terminate the simulation. Local/search/recovery timers use observation time, including at accelerated native playback.
- The eight-second visit may remain too short to resolve sensor lag or two-dimensional geometry. Existing unresolved-boundary status 5 remains. Completion means the commanded virtual route finished, not that the region is fully mapped.

## Protocol and compatibility

Firmware identity is **v0.14**; the host requires it for exploration. EXP remains sequence plus 16 values. Added mission phases: **8 = return to descent checkpoint**, **9 = ascent to surface**. Phase 4 with reason 1 is successful completion; reason 6 is recovery timeout. Phase codes 5 and 7 are reserved from older policies and are no longer normal holds. Surface targets now allow 0.10 m in the host validator. Native and Nano share the same Explorer header.

## Verification

C++ motion tests cover layered and uniform water, tau 2/8 s, the shared ten-second search deadline, retained memory, checkpoint depth/x, resumed descent, finite surface completion, operator Stop, clock rollover and frozen return/ascent failures. Python integration tests check the complete virtual mission and lab phase mapping. The Nano verification helper compares the entire mission to native C++ and requires automatic surface completion, then separately checks operator Stop/DISARM. Generated evidence is retained under output/logs and excluded from public source.

The motor-disabled Nano v0.14 bench run completed in 73.5 simulated seconds: descent → retrace → probe → transit (10 s shared allowance) → return → resumed descent → ascent → complete. All 736 observation replies matched native discrete decisions; the maximum numeric discrepancy was below 0.000053. Manual Stop/DISARM were checked separately. Flash verification: 27,820 bytes of program storage, 1,080 bytes static RAM; remaining SRAM is not a measured peak stack margin. Evidence: `output/logs/nano_v014_verified.json`, `nano_v014_exploration.csv` and `nano_v014_phases.json`.

The USB bridge also retries an incomplete CONFIG frame during startup and requires a complete configuration before verification. A malformed configuration after verification remains a connection error; invalid values are rejected. This addresses the intermittent immediate-post-flash startup frame without accepting a partial handshake.
