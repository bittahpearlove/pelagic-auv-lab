#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
build_dir="$(mktemp -d /tmp/auv-nano-tests.XXXXXX)"
trap 'rm -rf -- "$build_dir"' EXIT
c++ -std=c++11 -Wall -Wextra -Werror -pedantic -I"$project_dir/firmware/auv_nano" \
  "$project_dir/tests/controller_test.cpp" -o "$build_dir/controller_test"
"$build_dir/controller_test"
c++ -std=c++11 -Wall -Wextra -Werror -pedantic -I"$project_dir/tests/stubs" \
  "$project_dir/tests/sketch_test.cpp" -o "$build_dir/sketch_test"
"$build_dir/sketch_test"
c++ -std=c++11 -Wall -Wextra -Werror -pedantic \
  "$project_dir/tests/explorer_test.cpp" -o "$build_dir/explorer_test"
"$build_dir/explorer_test"
