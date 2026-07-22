# Stage09 Native Data Core — N3A Report

## Scope

Created the requested PostgreSQL bootstrap, local-only HBA fragment, private-socket Redis configuration, hardened Redis systemd unit, and static validation/test scripts.

## Verification

- The validator checks the requested least-privilege, local-isolation, runtime-hardening, and forbidden-marker rules without printing file contents or values.
- The negative test copies the assets into a temporary directory and rejects a public HBA rule, Redis TCP port, missing password guard, and unsafe systemd override without value leakage.
- `sh -n scripts/verify-native-data-core-assets.sh` passed.
- `sh -n scripts/test-native-data-core-assets.sh` passed.
- `sh scripts/test-native-data-core-assets.sh` passed and printed `native data-core asset tests: PASS`.

## External Actions

No network, SSH, Docker, installation, PostgreSQL execution, Redis execution, or git commit was performed.
