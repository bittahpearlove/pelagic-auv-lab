#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
variant="${1:-research}"
case "$variant" in research) flags=;; exploration) flags=-DAUV_EXPLORATION_BUILD=1;; *) printf 'Use research or exploration\n' >&2; exit 2;; esac
bash "$project_dir/tools/arduino.sh" compile --fqbn arduino:avr:nano:cpu=atmega328 \
 --build-property "compiler.cpp.extra_flags=$flags" --build-path "$project_dir/build/nano-v015-$variant" "$project_dir/firmware/auv_nano"
