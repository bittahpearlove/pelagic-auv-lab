# Contributing

Open an issue with a reproducible experiment, expected behavior and relevant measured-input data. Label results as simulated, firmware-on-board/virtual-water, or real-water; do not describe simulated estimates as measured vehicle performance.

Run the checks in README before submitting changes. Never rebuild `build/lab/core.so` while another laboratory process is running. Keep motor outputs disabled and the simulated-sensor motor interlock intact. New sensor drivers need an explicit device/interface, voltage levels, nonblocking acquisition, calibration and failure behavior.

Please keep changes focused on adaptive thermal sampling, short trajectories, probe-response characterization and reproducible tests. Historical sweep fixtures are retained for comparison; the current controller uses frontier decisions. Do not commit local tools, credentials, binary builds or private experiment logs. Contributions are under the repository's MIT license.
