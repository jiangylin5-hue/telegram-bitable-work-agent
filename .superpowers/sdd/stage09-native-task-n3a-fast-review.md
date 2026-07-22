# Stage09 Native Data Core — N3A Fast Review

## Scope

Fast, read-only review of the N3A report, deployment plan, and native data-core assets. This is not an exhaustive execution review.

## Findings

### Critical

1. **Bootstrap cannot satisfy the verifier's required password guard.** The generic verifier expects an empty-password rejection and two `\\quit 1` guards, but the actual PostgreSQL bootstrap does not implement that contract. A nominal static pass therefore does not establish that bootstrap fails safely when the required password input is absent.

### Important

1. **The N3A report overstates verification coverage.** It describes a core verifier/test suite, but the scripts are generic static asset checks rather than validation of this bootstrap's actual control flow and contractual failure cases. The reported PASS should not be accepted as end-to-end or bootstrap-specific evidence.

2. **Redis socket naming is inconsistent.** Runtime configuration refers to `redis-stage09-p1`, while the Redis configuration/service path uses `stage09-p1`. This can prevent the application from locating the intended private socket.

3. **Redis service violates least privilege.** The Redis unit runs as the application user and loads the application runtime environment. Redis should have a dedicated service identity and only the narrowly scoped configuration/secret inputs it needs.

### Minor

1. **Plan-to-asset filename drift.** The deployment plan names `stage09-p1.sql`, but the actual bootstrap asset has a different name. Align the plan and asset reference before operator handoff.

## Required Remediation

1. Make the bootstrap explicitly reject missing/empty password input with the two expected `\\quit 1` guards, then make the verifier test that real bootstrap behavior.
2. Replace or supplement generic checks with bootstrap-specific negative tests.
3. Choose one Redis socket name and apply it consistently across runtime, Redis, and systemd assets.
4. Introduce a dedicated Redis user and remove application runtime-environment loading from the Redis unit.
5. Reconcile the plan's SQL filename with the shipped bootstrap filename.

## Conclusion

Do not treat N3A as acceptance-ready until the Critical and Important findings are resolved and evidenced by focused static or safe local tests.
