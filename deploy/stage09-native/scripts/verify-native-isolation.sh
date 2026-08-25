#!/bin/sh
# Run the N1 contract validator and reject historical/container deployment markers.
set -eu

runtime_file=${1:-}
if [ -z "$runtime_file" ] || [ ! -r "$runtime_file" ]; then
    printf '%s\n' "native-isolation: fail" >&2
    exit 1
fi

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if ! sh "$script_dir/validate-runtime-presence.sh" "$runtime_file" >/dev/null 2>&1; then
    printf '%s\n' "native-isolation: fail" >&2
    exit 1
fi

if grep -Eqi 'stage03|stage07|docker|(^|[^[:alnum:]_])compose([^[:alnum:]_]|$)|volume|container|non[-_ ]?dry[-_ ]?run' "$runtime_file"; then
    printf '%s\n' "native-isolation: fail" >&2
    exit 1
fi

printf '%s\n' "native-isolation: pass"
