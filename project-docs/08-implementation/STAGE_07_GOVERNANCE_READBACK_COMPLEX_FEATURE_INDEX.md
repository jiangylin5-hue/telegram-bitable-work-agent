# Stage07 Governance Readback Complex Feature Index

## Status

- Status: proposed; no implementation evidence yet
- Design authority: Technical Decision 003, Governance Readback Design, BDD and SDD

| ID | Complex concern | Required rule | Proof before acceptance | Status |
| --- | --- | --- | --- | --- |
| GR-I01 | browser audit disclosure | browser receives only strict timeline DTO; no legacy audit HTTP response is reused | route/schema/parser negative tests | proposed |
| GR-I02 | member pagination | deterministic opaque cursor, page size `1..100`, next page cannot duplicate rows | backend/frontend pagination tests | proposed |
| GR-I03 | audit pagination | preserve first authorised page if next cursor fails; no stale Base append | component/app race tests | proposed |
| GR-I04 | authorization intersection | both member and audit routes independently verify identity, membership, scope and action | cross-user/workspace/Base denial tests | proposed |
| GR-I05 | capability mismatch | navigation hint cannot grant route access; audit can be denied even when management entry exists | API/component denied-state tests | proposed |
| GR-I06 | protected state removal | 401 global, 403 workspace, 404 exact Base audit cleanup; late results discarded | QueryClient/App tests | proposed |
| GR-I07 | unknown stable values | unknown role/status/event code uses fixed generic label, not raw error/state text | parser/render tests | proposed |
| GR-I08 | visual reachability | labels, focus return, continuation/retry at 1440/1280/430/390 | Browser synthetic fixture evidence | proposed |

## Mandatory Out-Of-Scope Guards

No item in this index permits role/policy write, raw audit inspection, action export, member directory profile enrichment, Bot lifecycle, knowledge/memory, draft detail, Telegram surface, migration/index work or production claim.
