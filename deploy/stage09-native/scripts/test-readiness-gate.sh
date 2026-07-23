#!/bin/sh
# Focused contract tests for the bounded Stage09 activation readiness gate.
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
verifier="$script_dir/verify-activation-readiness.sh"

fail() {
    printf '%s\n' "$1: FAIL" >&2
    exit 1
}

[ -x "$verifier" ] || fail readiness-script-missing

fixture_root=$(mktemp -d "${TMPDIR:-/tmp}/stage09-readiness.XXXXXX") || fail fixture-create
cleanup() { rm -rf "$fixture_root"; }
trap cleanup EXIT HUP INT TERM

fixture_bin="$fixture_root/bin"
fixture_verifier="$fixture_root/verify-activation-readiness.sh"
mkdir -p "$fixture_bin" || fail fixture-bin

# The production verifier fixes PATH. Only this copied fixture replaces that
# fixed value, allowing deterministic command simulations without creating a
# production test mode or waiting for real time to pass.
sed "s|^PATH=/usr/sbin:/usr/bin:/sbin:/bin$|PATH=$fixture_bin|" \
    "$verifier" > "$fixture_verifier" || fail fixture-copy
chmod 700 "$fixture_verifier" || fail fixture-copy-mode

write_fake() {
    command_name=$1
    shift
    {
        printf '%s\n' '#!/bin/sh'
        printf '%s\n' "$@"
    } > "$fixture_bin/$command_name" || fail "fake-$command_name"
    chmod 700 "$fixture_bin/$command_name" || fail "fake-$command_name-mode"
}

write_fake systemctl \
    'if [ "${FIXTURE_SERVICE_STATE:-active}" = active ]; then exit 0; fi' \
    'exit 3'

write_fake curl \
    'target=' \
    'for argument in "$@"; do target=$argument; done' \
    'case "$target" in' \
    '    http://127.0.0.1:18080/health)' \
    '        count_file="$FIXTURE_STATE_DIR/loopback-count"' \
    '        count=0; [ -r "$count_file" ] && IFS= read -r count < "$count_file"' \
    '        count=$((count + 1)); printf "%s" "$count" > "$count_file"' \
    '        ready_after=${FIXTURE_HEALTH_READY_AFTER:-0}' \
    '        if [ "$count" -le "$ready_after" ]; then printf "%s" "${FIXTURE_LOOPBACK_STATUS:-503}"; else printf "200"; fi' \
    '        ;;' \
    '    https://*/health)' \
    '        count=0; IFS= read -r count < "$FIXTURE_STATE_DIR/loopback-count"' \
    '        ready_after=${FIXTURE_HEALTH_READY_AFTER:-0}' \
    '        if [ "$count" -le "$ready_after" ]; then printf "%s" "${FIXTURE_PUBLIC_HEALTH_STATUS:-503}"; else printf "%s" "${FIXTURE_PUBLIC_HEALTH_STATUS_AFTER_READY:-200}"; fi' \
    '        ;;' \
    '    https://*/index.html) printf "%s" "${FIXTURE_STATIC_STATUS:-200}" ;;' \
    '    https://*/) printf "%s" "${FIXTURE_ROOT_STATUS:-200}" ;;' \
    '    http://*/.well-known/acme-challenge/*) printf "%s" "${FIXTURE_ACME_STATUS:-200}" ;;' \
    '    http://*/) printf "%s" "${FIXTURE_HTTP_ROOT_STATUS:-308}" ;;' \
    '    *) printf "000" ;;' \
    'esac'

write_fake ss \
    'if [ "${FIXTURE_LISTENER_STATE:-valid}" = valid ]; then' \
    '    printf "%s\\n" "LISTEN 0 511 0.0.0.0:80 0.0.0.0:* users:((\\\"nginx\\\",pid=1,fd=1))"' \
    '    printf "%s\\n" "LISTEN 0 511 0.0.0.0:443 0.0.0.0:* users:((\\\"nginx\\\",pid=1,fd=2))"' \
    '    printf "%s\\n" "LISTEN 0 511 127.0.0.1:5432 0.0.0.0:* users:((\\\"postgres\\\",pid=2,fd=1))"' \
    'else' \
    '    printf "%s\\n" "LISTEN 0 511 0.0.0.0:5432 0.0.0.0:* users:((\\\"postgres\\\",pid=2,fd=1))"' \
    'fi'

write_fake sleep \
    'printf "%s\\n" "$1" >> "$FIXTURE_STATE_DIR/sleeps"'

run_gate() {
    state_dir=$1
    shift
    env \
        PATH="$fixture_bin" \
        FIXTURE_STATE_DIR="$state_dir" \
        STAGE09_P1_READINESS_HOSTNAME=portal.example.test \
        STAGE09_P1_READINESS_ACME_PATH=/.well-known/acme-challenge/fixture-ready \
        "$@" \
        "$fixture_verifier" --verify
}

assert_pass() {
    label=$1
    state_dir=$2
    shift 2
    output=$(run_gate "$state_dir" "$@" 2>&1) || {
        printf '%s\n' "$output" >&2
        fail "$label-status"
    }
    [ "$output" = 'readiness-gate: pass' ] || fail "$label-output"
    printf '%s\n' "$label: PASS"
}

assert_redacted_failure() {
    label=$1
    state_dir=$2
    shift 2
    status=0
    output=$(run_gate "$state_dir" "$@" 2>&1) || status=$?
    [ "$status" -ne 0 ] || fail "$label-status"
    [ "$output" = 'readiness-gate: fail' ] || fail "$label-output"
    case "$output" in
        *fixture-secret-value*|*sensitive.example.test*|*fixture-ready*) fail "$label-leak" ;;
    esac
    printf '%s\n' "$label: PASS"
}

immediate_dir="$fixture_root/immediate"
mkdir -p "$immediate_dir" || fail immediate-fixture
assert_pass immediate-success "$immediate_dir" \
    FIXTURE_SERVICE_STATE=active \
    FIXTURE_HEALTH_READY_AFTER=0
[ ! -s "$immediate_dir/sleeps" ] || fail immediate-success-slept

delayed_dir="$fixture_root/delayed"
mkdir -p "$delayed_dir" || fail delayed-fixture
assert_pass delayed-success "$delayed_dir" \
    FIXTURE_SERVICE_STATE=active \
    FIXTURE_HEALTH_READY_AFTER=2
[ "$(wc -l < "$delayed_dir/sleeps")" -eq 2 ] || fail delayed-success-retries
[ "$(tr '\n' ' ' < "$delayed_dir/sleeps")" = '2 2 ' ] || fail delayed-success-interval

timeout_dir="$fixture_root/timeout"
mkdir -p "$timeout_dir" || fail timeout-fixture
assert_redacted_failure timeout "$timeout_dir" \
    FIXTURE_SERVICE_STATE=active \
    FIXTURE_HEALTH_READY_AFTER=99 \
    STAGE09_P1_READINESS_ACME_PATH=/.well-known/acme-challenge/fixture-secret-value \
    STAGE09_P1_READINESS_HOSTNAME=sensitive.example.test
[ "$(wc -l < "$timeout_dir/sleeps")" -eq 19 ] || fail timeout-retries

inactive_dir="$fixture_root/inactive"
mkdir -p "$inactive_dir" || fail inactive-fixture
assert_redacted_failure service-inactive "$inactive_dir" \
    FIXTURE_SERVICE_STATE=inactive \
    FIXTURE_HEALTH_READY_AFTER=0

health_dir="$fixture_root/health"
mkdir -p "$health_dir" || fail health-fixture
assert_redacted_failure health-non-200 "$health_dir" \
    FIXTURE_SERVICE_STATE=active \
    FIXTURE_HEALTH_READY_AFTER=0 \
    FIXTURE_PUBLIC_HEALTH_STATUS_AFTER_READY=502

boundary_dir="$fixture_root/boundary"
mkdir -p "$boundary_dir" || fail boundary-fixture
assert_redacted_failure listener-or-data-boundary "$boundary_dir" \
    FIXTURE_SERVICE_STATE=active \
    FIXTURE_HEALTH_READY_AFTER=0 \
    FIXTURE_LISTENER_STATE=invalid

printf '%s\n' 'readiness-gate: PASS'
