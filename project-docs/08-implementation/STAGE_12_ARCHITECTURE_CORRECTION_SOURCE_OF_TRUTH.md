# Stage12 Architecture Correction Source Of Truth

## Status

- Status: approved for local implementation on 2026-07-30
- Scope: the nine correction packages frozen by `STAGE_12_COMPREHENSIVE_ARCHITECTURE_AUDIT.md` Section 8
- Approval: user explicitly confirmed the complete package on 2026-07-30
- Production status: not authorized for deployment, migration execution, activation, real-workspace external Provider/embedding, business writes or Telegram sends
- Supersedes: any Stage12-A/B/E/F local acceptance statement contradicted by the comprehensive audit
- Execution plan: `docs/superpowers/plans/2026-07-30-stage12-architecture-correction.md`
- Current Progress: Tasks 1–9/Task9B, HG-01–HG-10, ISO-01 and the approved bounded deterministic-section Composer correction are `implemented-local`. Human Gold is `48/48`. The post-correction real `48 × 3` campaign remains release `FAIL`, but every returned-answer/Case gate improved to `48/48` and `mixed_02`/`mixed_08` no longer collapse. Retrieval passed; Composer unavailable was `36/48`, `47/48`, `37/48`, and total-latency P95 worst was `13775.8 ms`. Current bundle `6b15446524a5a084d744dfc82564a73354d1477260c8e2e705375e9c392f1aa8`; effects `0/0/0`. Stage11 remains production answer authority; Stage12 is not activated or finally accepted.

## 1. Objective

Close the proven gap between Stage12 component code and the actual Agent runtime. A successful delivery must execute a raw Chinese Query through the same authorized A–F contracts used by evaluation, without Gold, expected Action, target, field or value injection, and must produce independently verifiable typed facts, claims, proposals and trace evidence.

The primary acceptance criterion is the quality of the final answer actually returned to the user. Planner, Query, Retrieval and Specialist metrics are diagnostic evidence only and cannot substitute for final-answer correctness, completeness, grounding, instruction satisfaction and stability. Safety hard gates remain non-compensable: a fluent answer cannot offset a permission leak, unsupported fact, unconfirmed write or external send.

## 2. Approved correction packages

1. Evaluation/trace V2.1 separates query result identity, supporting evidence and independently verifiable typed facts. Recovery is scored only when fault injection makes recovery applicable.
2. A generic authorized Entity Linker supplies the same runtime/evaluation contract from current authorized schema identity fields, exact values and aliases. Production prefix branches and fixture-derived candidates are removed.
3. Generic relation indexing permits valid same-table links. Permission proof, relation definition, visited-edge detection and traversal budgets remain mandatory.
4. Stage12 Digital Employee field-policy V2 uses versioned explicit `readable_field_ids`, `writable_field_ids` and masking rules. Stage12 fails closed when the policy is absent; existing V1 execution remains unchanged until migrated.
5. Public Action admission gains backward-compatible `requested_action=auto`. Explicit action/target values remain declared user context only and are not evaluation truth. Blind final Cases omit them.
6. Retrieval V2 gains the authorized projection outbox consumer and runtime candidate loader with current scope/version/revoke revalidation.
7. The real worker uses distinct typed Tabular/Risk/Daily/Action handlers. ClaimGraph accepts only validated artifact facts. Composer can select/order prevalidated factual text and bounded connectors but cannot invent factual prose.
8. An isolated runner executes A–F from raw Query and emits per-stage hashes, counts, error classes and segmented latency. Destructive PostgreSQL fixtures must use an isolated database/schema boundary and cannot reset the shared project schema.
9. Final gates require real Redis recovery/ack-once evidence, 48/48 human Gold sign-off and exactly three real Provider rounds reporting mean, worst round, population variance, safety failures and P95.

## 3. Contract invariants

### 3.1 Evaluation and fact grounding

- `result_record_ids` contains only records satisfying the Query result.
- `evidence_record_ids` contains supporting/context records and may not satisfy the Query result.
- A typed fact includes subject identity, predicate/field reference, canonical typed value, evidence IDs and source versions.
- An answer claim is grounded only when its subject, predicate and canonical value equal an independently produced fact and its evidence is a permitted subset of that fact's evidence.
- Citation identity alone cannot make an unsupported value pass.
- Normal non-fault Cases use recovery applicability `not_applicable`; fault Cases declare the expected recovery transition explicitly.

### 3.2 Authorization and genericity

- Entity candidates are built only after effective scope intersection and field visibility filtering.
- Evaluator and runtime call the same Entity Linker entry point; evaluation fixtures cannot construct richer candidates.
- No platform code may infer entity type from advertising-specific code prefixes.
- Same-table relations are valid when the schema relation, source/target record, permission proof and traversal budget are valid.

### 3.3 Stage12 field policy

- Effective readable/writable fields are intersections, never unions.
- The Stage12 policy and its version/hash are bound into scope proof, Provider input, proposal payload and confirmation revalidation.
- Missing, malformed, stale or contracted Stage12 policy fails closed.
- V1 behavior is not silently reinterpreted; a V1 employee must be explicitly migrated before Stage12 active execution.

### 3.4 Action blindness and safety

- `requested_action=auto` permits the Planner to discover one or more controlled Action kinds from raw Query.
- Explicit `requested_action` or `target_record_id` narrows declared user intent but never acts as Gold truth.
- Candidate resolution uses authorized Query results/current records only.
- Final campaign creates at most disposable pending/denied proposals and never confirms, writes, notifies or sends.

### 3.5 Typed fan-in and composition

- Risk/Daily consume typed facts/aggregates, not the original raw retrieval request.
- ClaimGraph membership is verified against sealed typed artifacts and current source versions.
- Deterministic rendering owns factual text; Provider composition owns ordering, summaries and bounded non-factual connectors.
- Any Provider output that introduces an unvalidated fact is `provider_semantic_invalid`, not `completed`.

## 4. Activation boundary

All new paths remain `off` or isolated/allowlisted. This approval permits local migrations, synthetic disposable PostgreSQL/pgvector/Redis fixtures and real Provider calls using synthetic Case data. It does not authorize production migration, Stage12 production dispatch, real workspace external embedding, action confirmation, business writes, notification delivery or Telegram send.

## 5. Acceptance gates

The package is not complete until all of the following have direct evidence:

- focused RED/GREEN tests for every changed behavior;
- real local PostgreSQL and pgvector migrations/current-head checks;
- real Redis duplicate, pending-claim, crash recovery and ack-once checks;
- A–F isolated runner proves no Gold/action/target/field/value injection;
- unsupported factual prose is rejected;
- field-policy contraction is enforced at read, Provider, proposal and confirmation boundaries;
- 48/48 human Gold sign-off;
- three complete real Provider rounds with all literal hard gates from `08_DELIVERY_TEST_AND_ACCEPTANCE.md`;
- final-answer review over every Case/round covers factual correctness, required-result completeness, relation/aggregate correctness, citation-to-fact grounding, instruction/action satisfaction, Chinese clarity and refusal/degradation appropriateness;
- final answer quality is the release decision source; component scores are retained only for diagnosis and must never be averaged into a passing product score when the final answer fails;
- full backend, Mini App and build regression with every skip classified;
- no production activation, external send or confirmed action during acceptance.

## 6. Current Progress

- 2026-07-30: architecture correction package approved; documentation freeze in progress.
- 2026-07-31: HG-01–HG-10 were approved, applied and regenerated; deterministic release is `48/48`. A subsequent completion audit reopened ISO-01 Specialist-derived fact trace ownership before Human Gold; F durable Action authority is already complete.
- Task 5 evidence currently proves the route no longer hard-fails with `retrieval_v2_shadow_source_unavailable` when a current authorized materialized source exists; worker callbacks consume source/projection/revoke events; stale/forged source identities and policy/version drift fail closed; real authorized linked-record values can produce and traverse a current relation edge.
- Task 5 is `implemented-local`: TDR-021 and TDR-022 now include first-registration catch-up for stable pre-existing sources and an allowlist-filtered SQL Retrieval worker loop. Requirement-level evidence is recorded in `evidence/stage12-task5-retrieval-runtime-2026-07-30.md`; production activation remains unauthorized.
- Task 6 is `implemented-local`: the durable worker executes distinct typed handlers, typed owners support Query/Evidence/Action inputs, ClaimGraph rejects unsupported canonical facts, Composer rejects valid-ID hallucinated prose, and Supervisor preserves one terminal result under optional failure. Requirement-level evidence is recorded in `evidence/stage12-task6-typed-worker-composer-2026-07-30.md`; production activation remains unauthorized.
- Task 7 is `implemented-local`: the isolated runner accepts only raw Query, round identity and isolated runtime context; it emits complete/sanitized stage observations, materializes only unconfirmed disposable Action proposals, and writes atomic round/aggregate artifacts. All 48 deterministic Cases complete with zero confirmed actions/writes/sends. The former PostgreSQL test no longer drops `public`; its unique temporary schema rolls back and leaves project head `0039` unchanged. Requirement-level evidence is recorded in `evidence/stage12-task7-isolated-af-2026-07-30.md`; human Gold, real-Provider 48 Case × 3 and production activation remain pending.
- Task 8 is `implemented-local`: a loopback-only disposable Redis 7.4.10 container and the production Streams/worker/orchestrator path prove duplicate suppression, crash recovery, `XAUTOCLAIM`, ACK-once and terminal sibling drain. The related runtime slice is `25 passed`; Redis DB 15 is empty and the container/Docker engine are stopped after evidence. Requirement-level evidence is recorded in `evidence/stage12-task8-real-redis-2026-07-30.md`; human Gold, real-Provider 48 Case × 3 and production activation remain pending.
- Task 9 contract correction is `implemented-local` but final quality is still blocked: replacing only rendered prose can no longer bypass the seven-dimensional gate; bounded Provider plans cannot add facts; Action, denial, degradation, relation and aggregate provenance reach the receipt; and the real Gateway adapter preserves sanitized failure metadata. Focused evidence is green, while the deterministic full set reports 30/48 final-answer passes and lists all 18 failures. Direct evidence is recorded in `evidence/stage12-task9-final-answer-correction-2026-07-30.md`. Human Gold is still 0/48 and no real campaign has started.
- Task 9B is `implemented-local-technical-gate`: Planner/Query/Action mechanism corrections and the shared semantic relation-path evaluator projection are implemented without schema, API, permission or Provider-profile changes. Final-answer/safety are `48/48`; direct evidence is `evidence/stage12-task9b-core-quality-correction-2026-07-31.md`.
- Integrated Stage12 final-answer acceptance remains pending.
- 2026-08-01 Grounded per-slot P1/P2 gate is `implemented-local-p2-passed` under user-approved TDR-028. Final-code unit evidence is `2176 passed`; real P1 is `12/12`, and the accepted exact P2 is `36/36` real/final with zero fallback/effects/writes/sends and p95 `4385 ms` (hash `54de9da4eb0e7ae7eb65d62bbb85807d5382af05a2b795a29628dc10eecc86cc`). This does not close P3, native deployment, runtime activation or Telegram acceptance.
