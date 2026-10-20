> Superseded by [v0.11 spatial memory](NANO_V011_SPATIAL_MEMORY.md), which retains visited locations and replaces repeated routes with monitoring.

# Nano v0.10: continuous exploration

Adaptive exploration has no elapsed-time or travelled-distance termination. It runs until operator Stop, Reset, disconnect, invalid observations or a connection fault. Depth and local spatial bounds remain; motors remain disabled.

The initial route descends vertically at the selected x. A sustained measured thermal change triggers a slow 0.25 m upward retrace, then local investigation within the existing detection-centred bounds. Predictable/weak gradients or exhausted local candidates refresh the local geometry fit and candidate bitmap instead of stopping. This deliberately revisits the same bounded region to detect changes over time; it does not provide whole-tank coverage. No sweep is added.

In uniform water, the vehicle repeats vertical profiles between 0.2 and 2.7 m at the selected x until a feature is detected or Stop is pressed.

USB start remains EXPL,1,tau. OBS sequence and milliseconds now use strict uint32 integer parsing to avoid float precision and former packet-duration limits. The host wraps protocol counters at 32 bits, and the controller accepts forward timestamp rollover while rejecting duplicates/backward input. Elapsed time in lab logs remains unwrapped.

The exploration loop is separate from the original Adaptive profile activity, whose finite mission policy is unchanged. Native tests exercise 600 seconds of continuous motion in layered and uniform water, operator stop, invalid input and clock rollover. Lab integration exercises 610 seconds in both fields. Browser/bridge history remains a rolling 10,000-record buffer; download CSV periodically to retain earlier samples during long runs.
