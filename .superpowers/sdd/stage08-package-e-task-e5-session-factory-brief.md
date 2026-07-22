# Stage08 Package E — E5 request-session isolation remediation

## Finding

E5 independent review I-01 found a real concurrency defect: each read worker
eventually creates a distinct read-only SQLAlchemy session, but
`_isolated_read_uow` first calls `get_bind()` on the shared request session
inside both concurrently scheduled workers. SQLAlchemy sessions must not be
concurrently accessed. The existing barrier test proves child sessions differ,
not that the request session remains untouched.

## Required minimal repair

1. Before the graph fan-out, in the request/coordinator thread, derive the
   immutable Engine/bind and construct the internal read-session factory.
2. Pass only that factory/bind carrier to worker branches. Worker code must
   never dereference, call or inspect the request session/UoW for SQLAlchemy
   session creation.
3. Keep InMemory fallback serialized and its lock local. Do not change the
   Stage06 UoW protocol or any public contract.
4. Extend the local pgvector barrier test with a request-session no-touch
   probe that fails if a read worker accesses request-session methods after
   fan-out. Preserve distinct child-session and overlap proof.
5. Update E5 report and run E5 focused/service/PG/compile/diff checks.

## Boundaries

No API/schema/permission/provider/Telegram/deployment/Git changes. This is a
small implementation repair to meet the already approved isolated-session
contract. Do not expand tests beyond direct E5 evidence and existing compact
E regression.
