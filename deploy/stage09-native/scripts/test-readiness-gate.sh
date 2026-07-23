#!/bin/sh
# Focused contract tests for the bounded, fail-closed activation readiness gate.
set -eu

fail() {
    printf '%s\n' "readiness-test: FAIL: $1" >&2
    exit 1
}

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || fail path
verifier="$script_dir/verify-activation-readiness.sh"
[ -f "$verifier" ] || fail verifier-missing
grep -Fqx 'max_retry_attempts=20' "$verifier" >/dev/null || fail retry-budget-contract
grep -Fqx 'interval_seconds=2' "$verifier" >/dev/null || fail retry-interval-contract
grep -Fqx 'total_deadline_seconds=40' "$verifier" >/dev/null || fail deadline-contract
grep -Fqx 'retry_attempt=0' "$verifier" >/dev/null || fail immediate-attempt-contract
grep -Fqx '    [ "$retry_attempt" -lt "$max_retry_attempts" ] || break' "$verifier" >/dev/null || fail retry-cap-contract
grep -Fqx '    sleep "$interval_seconds" || fail' "$verifier" >/dev/null || fail retry-sleep-contract
grep -Fqx '    retry_attempt=$((retry_attempt + 1))' "$verifier" >/dev/null || fail retry-increment-contract
grep -Fqx 'deadline_epoch=$((start_epoch + total_deadline_seconds))' "$verifier" >/dev/null || fail deadline-start-contract
grep -Fq 'remaining=$(seconds_remaining) || break' "$verifier" || fail deadline-loop-contract
grep -Fq -- '--connect-timeout "$curl_timeout" --max-time "$curl_timeout"' "$verifier" || fail curl-bound-contract

fixture_root=$(mktemp -d "${TMPDIR:-/tmp}/stage09-readiness.XXXXXX") || fail fixture-create
trap 'rm -rf "$fixture_root"' EXIT HUP INT TERM
fixture_state="$fixture_root/state"
mkdir -p "$fixture_state" || fail fixture-state
helper="$fixture_root/helpers.sh"
normal_runner="$fixture_root/verify-normal.sh"
fast_runner="$fixture_root/verify-fast.sh"
cp "$verifier" "$normal_runner" || fail runner-copy
sed 's/^max_retry_attempts=20$/max_retry_attempts=0/' "$verifier" > "$fast_runner" || fail runner-fast-copy
chmod 700 "$normal_runner" "$fast_runner" || fail runner-mode

printf '%s\n' \
'fixture_increment() {' \
'    name=$1' \
'    file="$FIXTURE_STATE_DIR/$name"' \
'    value=$(sed -n "1p" "$file" 2>/dev/null || printf "0")' \
'    case "$value" in ""|*[!0-9]*) value=0 ;; esac' \
'    value=$((value + 1))' \
'    printf "%s\n" "$value" > "$file"' \
'    printf "%s\n" "$value"' \
'}' \
'date() {' \
'    current=$(sed -n "1p" "$FIXTURE_STATE_DIR/epoch")' \
'    printf "%s\\n" "$current" > "$FIXTURE_STATE_DIR/last_now"' \
'    printf "%s\\n" "$current"' \
'    if [ "$FIXTURE_DATE_STEP" -gt 0 ]; then printf "%s\\n" "$((current + FIXTURE_DATE_STEP))" > "$FIXTURE_STATE_DIR/epoch"; fi' \
'}' \
'timeout() {' \
'    duration=$1' \
'    shift' \
'    "$@"' \
'}' \
'systemctl() {' \
'    [ "$1" = "is-active" ] && [ "$2" = "--quiet" ] || return 2' \
'    [ "$3" = "$FIXTURE_INACTIVE_UNIT" ] && return 3' \
'    return 0' \
'}' \
'curl() {' \
'    target=' \
'    for argument in "$@"; do target=$argument; done' \
'    case "$target" in' \
'        http://127.0.0.1:18080/health)' \
'            count=$(fixture_increment loopback_count)' \
'            if [ "$FIXTURE_LOOPBACK_FORCE_STATUS" != "0" ]; then printf "%s" "$FIXTURE_LOOPBACK_FORCE_STATUS"' \
'            elif [ "$count" -le "$FIXTURE_LOOPBACK_FAILS" ]; then printf "%s" "$FIXTURE_LOOPBACK_FAIL_STATUS"' \
'            else printf "200"; fi' \
'            ;;' \
'        https://fixture.example.test/health) printf "%s" "$FIXTURE_HTTPS_HEALTH_STATUS" ;;' \
'        https://fixture.example.test/) printf "%s" "$FIXTURE_HTTPS_ROOT_STATUS" ;;' \
'        https://fixture.example.test/index.html) printf "%s" "$FIXTURE_HTTPS_STATIC_STATUS" ;;' \
'        http://fixture.example.test/) printf "%s" "$FIXTURE_HTTP_REDIRECT_STATUS" ;;' \
'        http://fixture.example.test/.well-known/acme-challenge/probe) printf "%s" "$FIXTURE_ACME_STATUS" ;;' \
'        *) return 2 ;;' \
'    esac' \
'}' \
'ss() {' \
'    case "$FIXTURE_LISTENER_MODE" in' \
'        safe)' \
'            printf "%s\n" "LISTEN 0 511 0.0.0.0:80 0.0.0.0:* users:((\"nginx\",pid=11,fd=6))"' \
'            printf "%s\n" "LISTEN 0 511 0.0.0.0:443 0.0.0.0:* users:((\"nginx\",pid=11,fd=7))"' \
'            printf "%s\n" "LISTEN 0 128 127.0.0.1:5432 0.0.0.0:* users:((\"postgres\",pid=12,fd=8))"' \
'            ;;' \
'        http-non-nginx)' \
'            printf "%s\n" "LISTEN 0 511 0.0.0.0:80 0.0.0.0:* users:((\"caddy\",pid=21,fd=6))"' \
'            printf "%s\n" "LISTEN 0 511 0.0.0.0:443 0.0.0.0:* users:((\"nginx\",pid=11,fd=7))"' \
'            ;;' \
'        http-extra)' \
'            printf "%s\n" "LISTEN 0 511 0.0.0.0:80 0.0.0.0:* users:((\"nginx\",pid=11,fd=6),(\"caddy\",pid=21,fd=7))"' \
'            printf "%s\n" "LISTEN 0 511 0.0.0.0:443 0.0.0.0:* users:((\"nginx\",pid=11,fd=8))"' \
'            ;;' \
'        https-non-nginx)' \
'            printf "%s\n" "LISTEN 0 511 0.0.0.0:80 0.0.0.0:* users:((\"nginx\",pid=11,fd=6))"' \
'            printf "%s\n" "LISTEN 0 511 0.0.0.0:443 0.0.0.0:* users:((\"caddy\",pid=21,fd=7))"' \
'            ;;' \
'        https-extra)' \
'            printf "%s\n" "LISTEN 0 511 0.0.0.0:80 0.0.0.0:* users:((\"nginx\",pid=11,fd=6))"' \
'            printf "%s\n" "LISTEN 0 511 0.0.0.0:443 0.0.0.0:* users:((\"nginx\",pid=11,fd=7),(\"caddy\",pid=21,fd=8))"' \
'            ;;' \
'        db-public)' \
'            printf "%s\n" "LISTEN 0 511 0.0.0.0:80 0.0.0.0:* users:((\"nginx\",pid=11,fd=6))"' \
'            printf "%s\n" "LISTEN 0 511 0.0.0.0:443 0.0.0.0:* users:((\"nginx\",pid=11,fd=7))"' \
'            printf "%s\n" "LISTEN 0 128 0.0.0.0:5432 0.0.0.0:* users:((\"postgres\",pid=12,fd=8))"' \
'            ;;' \
'        redis-public)' \
'            printf "%s\n" "LISTEN 0 511 0.0.0.0:80 0.0.0.0:* users:((\"nginx\",pid=11,fd=6))"' \
'            printf "%s\n" "LISTEN 0 511 0.0.0.0:443 0.0.0.0:* users:((\"nginx\",pid=11,fd=7))"' \
'            printf "%s\n" "LISTEN 0 128 0.0.0.0:6379 0.0.0.0:* users:((\"redis-server\",pid=13,fd=9))"' \
'            ;;' \
'        *) return 2 ;;' \
'    esac' \
'}' \
'sleep() {' \
'    fixture_increment sleep_count >/dev/null' \
'}' \
'awk() {' \
'    /usr/bin/awk "$@"' \
'}' \
> "$helper" || fail helper-write

reset_fixture() {
    printf '%s\n' 1000 > "$fixture_state/epoch"
    printf '%s\n' 1000 > "$fixture_state/last_now"
    printf '%s\n' 0 > "$fixture_state/loopback_count"
    printf '%s\n' 0 > "$fixture_state/sleep_count"
    FIXTURE_STATE_DIR=$fixture_state
    FIXTURE_INACTIVE_UNIT=
    FIXTURE_LOOPBACK_FAILS=0
    FIXTURE_LOOPBACK_FAIL_STATUS=503
    FIXTURE_LOOPBACK_FORCE_STATUS=0
    FIXTURE_HTTPS_HEALTH_STATUS=200
    FIXTURE_HTTPS_ROOT_STATUS=200
    FIXTURE_HTTPS_STATIC_STATUS=200
    FIXTURE_HTTP_REDIRECT_STATUS=308
    FIXTURE_ACME_STATUS=200
    FIXTURE_LISTENER_MODE=safe
    FIXTURE_DATE_STEP=0
    export FIXTURE_STATE_DIR FIXTURE_INACTIVE_UNIT FIXTURE_LOOPBACK_FAILS
    export FIXTURE_LOOPBACK_FAIL_STATUS FIXTURE_LOOPBACK_FORCE_STATUS
    export FIXTURE_HTTPS_HEALTH_STATUS FIXTURE_HTTPS_ROOT_STATUS
    export FIXTURE_HTTPS_STATIC_STATUS FIXTURE_HTTP_REDIRECT_STATUS
    export FIXTURE_ACME_STATUS FIXTURE_LISTENER_MODE FIXTURE_DATE_STEP
}

run_gate() {
    runner=$1
    set +e
    gate_output=$(TEST_HELPERS="$helper" STAGE09_P1_READINESS_HOSTNAME=fixture.example.test STAGE09_P1_READINESS_ACME_PATH=/.well-known/acme-challenge/probe /bin/sh -c '
runner=$1
. "$TEST_HELPERS"
set -- --verify
. "$runner"
' readiness-test "$runner" 2>&1)
    gate_status=$?
    set -e
}

assert_pass() {
    label=$1
    [ "$gate_status" -eq 0 ] || fail "$label-status"
    [ "$gate_output" = 'readiness-gate: pass' ] || fail "$label-output"
    printf '%s\n' "assert_pass $label"
}

assert_redacted_failure() {
    label=$1
    [ "$gate_status" -ne 0 ] || fail "$label-status"
    [ "$gate_output" = 'readiness-gate: fail' ] || fail "$label-output"
    case "$gate_output" in
        *fixture-secret-value*|*fixture.example.test*|*fixture-ready*) fail "$label-redaction" ;;
    esac
    printf '%s\n' "assert_redacted_failure $label"
}

assert_count() {
    name=$1
    expected=$2
    actual=$(sed -n "1p" "$fixture_state/$name")
    [ "$actual" = "$expected" ] || fail "$name-count"
}

reset_fixture
run_gate "$normal_runner"
assert_pass immediate-success
assert_count loopback_count 1
assert_count sleep_count 0

for inactive_unit in stage09-p1-api stage09-p1-worker stage09-p1-outbox-bridge stage09-p1-redis nginx; do
    reset_fixture
    FIXTURE_INACTIVE_UNIT=$inactive_unit
    export FIXTURE_INACTIVE_UNIT
    run_gate "$fast_runner"
    assert_redacted_failure "service-$inactive_unit"
done

reset_fixture
FIXTURE_LOOPBACK_FORCE_STATUS=503
export FIXTURE_LOOPBACK_FORCE_STATUS
run_gate "$fast_runner"
assert_redacted_failure loopback-health

reset_fixture
FIXTURE_HTTPS_HEALTH_STATUS=503
export FIXTURE_HTTPS_HEALTH_STATUS
run_gate "$fast_runner"
assert_redacted_failure https-health

reset_fixture
FIXTURE_HTTPS_ROOT_STATUS=503
export FIXTURE_HTTPS_ROOT_STATUS
run_gate "$fast_runner"
assert_redacted_failure https-root

reset_fixture
FIXTURE_HTTPS_STATIC_STATUS=503
export FIXTURE_HTTPS_STATIC_STATUS
run_gate "$fast_runner"
assert_redacted_failure https-static

reset_fixture
FIXTURE_HTTP_REDIRECT_STATUS=200
export FIXTURE_HTTP_REDIRECT_STATUS
run_gate "$fast_runner"
assert_redacted_failure http-redirect

reset_fixture
FIXTURE_ACME_STATUS=503
export FIXTURE_ACME_STATUS
run_gate "$fast_runner"
assert_redacted_failure acme

for listener_mode in http-non-nginx http-extra https-non-nginx https-extra db-public redis-public; do
    reset_fixture
    FIXTURE_LISTENER_MODE=$listener_mode
    export FIXTURE_LISTENER_MODE
    run_gate "$fast_runner"
    assert_redacted_failure "$listener_mode"
done

printf '%s\n' 'readiness-test: pass'
