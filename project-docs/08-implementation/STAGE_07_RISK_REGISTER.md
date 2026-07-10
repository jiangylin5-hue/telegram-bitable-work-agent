# Stage 07 Risk Register

## Status

- Document status: active planning risk register

| Risk | Impact | Mitigation | Gate |
| --- | --- | --- | --- |
| Team Bot model exceeds Stage06 base-bound employee | incorrect scope or rushed schema | separate technical decision, migration and authorization review | before Package 4 |
| Mini App identity differs from desktop identity | role spoofing or stale membership | retain Stage06 identity adapter boundary and verify both proofs server-side | before Package 1 release |
| Mobile table becomes card-only approximation | loss of Bitable semantics | preserve Grid access, field priority and full record editor | Package 2 visual/BDD |
| Cached protected data survives revocation | data exposure | workspace-keyed cache plus mandatory clear on 401/revocation | security tests |
| Bot UI implies shared private memory | privacy/trust failure | explicit personal/team labels and server-partitioned memory contract | Package 4 contract |
| Knowledge sources overreach permissions | cross-resource leak | curated sources and retrieval-time permission filter | contract/security tests |
| Visual work regresses to AI-dashboard style | rejected product direction | token lock and screenshot review against selected concept | visual QA |
| Raw field policy/options leak through Canvas schema | client learns governance metadata or internal configuration | typed safe schema projection and negative response tests | before F1 browser integration |
| Field add succeeds but new field is invisible | unusable schema and misleading success | server appends explicit saved-view field lists and client rereads presentation | F1 domain/API/browser tests |
| Same-key retry or concurrent builder duplicates a field/order | duplicated columns or unstable grid order | endpoint-scoped idempotency, table-row lock and six real PostgreSQL P3/F1 rollback/replay/concurrency/default-view cases passed on 2026-07-11 | local evidence complete; retain regression coverage and do not treat it as production load proof |
| Required choice field cannot be used in records | users create an impossible table | validated choices plus F1 multi-select create/direct-edit controls | F1 record tests |
| F1 grows into relationship/governance work | unsafe resource or policy disclosure | strict type/request allowlist and documented F2/V1 exclusion | F1 scope audit |
