// One field list shared by USB firmware and the native bridge. Values are read-only.
#pragma once
#define AUV_BASE_REPORTED_CONFIG(X) \
  X(target_depth_m, TARGET_DEPTH_M) \
  X(max_depth_m, MAX_DEPTH_M) \
  X(normal_speed_mps, TARGET_SPEED_MPS) \
  X(slow_speed_mps, SLOW_SPEED_MPS) \
  X(probe_tau_s, PROBE_TAU_S) \
  X(allowed_lag_m, ALLOWED_LAG_M) \
  X(gradient_window_m, GRADIENT_WINDOW_M) \
  X(gradient_enter_cpm, GRADIENT_ENTER_CPM) \
  X(gradient_exit_cpm, GRADIENT_EXIT_CPM) \
  X(control_ms, CONTROL_MS) \
  X(telemetry_ms, TELEMETRY_MS) \
  X(mission_timeout_ms, MISSION_TIMEOUT_MS) \
  X(water_center_m, WATER_CENTER_M) \
  X(water_width_m, WATER_WIDTH_M) \
  X(water_drop_c, WATER_DROP_C) \
  X(water_surface_c, WATER_SURFACE_C)

#define AUV_REPORTED_CONFIG(X) \
  AUV_BASE_REPORTED_CONFIG(X) \
  X(water_shape, WATER_SHAPE) \
  X(profile_x_m, PROFILE_X_M)
