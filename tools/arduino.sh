#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -x "$project_dir/.tools/arduino/bin/arduino-cli" ]]; then
  exec "$project_dir/.tools/arduino/bin/arduino-cli" --config-file "$project_dir/.tools/arduino/arduino-cli.yaml" "$@"
fi
if command -v arduino-cli >/dev/null 2>&1; then
  exec arduino-cli "$@"
fi
printf '%s\n' 'Install Arduino CLI and add it to PATH, or use Arduino IDE.' >&2
exit 127
