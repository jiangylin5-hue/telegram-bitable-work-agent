# Stage09 N4B R2 Final Review

Status: complete (read-only review)
Scope: `deploy/stage09-native/scripts/verify-fixed-migration-offline.sh` and its repository fixtures.

## Verdict: C — Compliant

- The script derives `resolved_python` with `realpath`, requires a regular executable non-symlink resolved target, and allowlists only the artifact venv tree or the two fixed system-Python targets.
- It deliberately invokes `"$python_bin"`, not `"$resolved_python"`. This preserves the approved venv entrypoint while validation constrains its resolved executable target.
- The green fixture resolves the venv entrypoint to the permitted system target and makes the fake executable require `$0` to equal the original venv path; both `alembic heads` and offline `upgrade --sql` must therefore use that path.
- The negative fixture retargets the venv entrypoint to an external executable and requires generic failure, with no SQL output created. This rejects interpreter-path escape before either Alembic invocation.

## Evidence

- Static review: `verify-release-assets.sh` explicitly rejects reassignment to `resolved_python` and asserts the invocation-path fixture checks.
- Runtime execution was not available in this Windows shell: `sh` is absent. No remote or target-host operation was attempted.

## I/M

- I: none for the stated N4B R2 question.
- M: execution evidence must be produced on a POSIX shell/target runner; static review cannot replace that runtime proof.
