> Superseded by [v0.12 bounded visits and shorter paths](NANO_V012_BOUNDED_LOCAL.md), retaining memory and adding 8 s local/hold limits.

# Nano v0.11: persistent spatial memory

The previous continuous policy erased the local visited bitmap and restarted its geometry route whenever an investigation ended. That produced repeated loops. This version retains the 192-byte, 64 × 24 occupancy bitmap (0.125 m cells) until a new run or Reset. This memory lives on the Nano, not just in the browser. It does not survive a power cycle.

Each measured observation marks its position visited. Gradient-following candidates reject visited target cells. When those candidates are exhausted, choose the nearest useful unvisited cell centre within the existing detection-centred local bounds. Transit through previously visited water is permitted: this is target novelty, not obstacle avoidance or a guarantee of a path that never crosses itself. The initial upward retrace and geometry probe deliberately revisit some positions to measure contrast.

When no useful new target remains, remain active and hold position while recording probe observations. Do not erase memory, repeat the diamond or automatically stop. Uniform water similarly profiles once to the depth limit, then holds instead of repeating the vertical line.

After holding for three probe response constants to settle the sensor, establish a reference probe temperature. Three consecutive observations differing from that reference by at least 0.15 °C trigger a deliberate geometry recheck. The visited bitmap remains intact during this recheck. This detector can observe changes at the holding location; it cannot detect a new feature elsewhere in the tank while stationary.

The time and travel budgets remain absent. Stop/Reset, invalid-input and link-failure protections remain. Motors remain disabled. New EXP fields append known-cell count and temperature-triggered recheck count; the reply now contains sequence plus 16 controller values. Monitor phase is 5. CSV adds known_cells and thermal_rechecks. Lab requires firmware v0.11.

A visited cell means that a position was traversed with a probe observation. It is not a temperature-accuracy or confidence guarantee: sensor lag and position error still matter. Real-water use needs a position estimator in the same coordinate frame; the lab currently supplies simulated position. The 12.5 cm grid is a tank setting, not a claimed real AUV navigation accuracy.
