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
