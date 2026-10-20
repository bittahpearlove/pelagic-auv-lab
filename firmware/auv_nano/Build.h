#pragma once
#define AUV_VERSION "v0.15"
// Classic Nano flash cannot hold both experiment families plus diagnostics.
// Native tests include both. Arduino defaults to the primary 1D research image;
// compile with -DAUV_EXPLORATION_BUILD=1 for the existing 2D bench controller.
#ifndef AUV_EXPLORATION_BUILD
#define AUV_EXPLORATION_BUILD 0
#endif
#ifndef AUV_HAS_RESEARCH
#ifdef ARDUINO
#define AUV_HAS_RESEARCH (!AUV_EXPLORATION_BUILD)
#else
#define AUV_HAS_RESEARCH 1
#endif
#endif
#ifndef AUV_HAS_EXPLORER
#ifdef ARDUINO
#define AUV_HAS_EXPLORER AUV_EXPLORATION_BUILD
#else
#define AUV_HAS_EXPLORER 1
#endif
#endif
