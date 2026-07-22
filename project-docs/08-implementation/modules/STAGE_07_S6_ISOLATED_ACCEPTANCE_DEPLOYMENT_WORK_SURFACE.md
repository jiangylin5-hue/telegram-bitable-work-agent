# Stage07 S6.3 Isolated Acceptance Deployment Work Surface

## Module Boundary

| Surface | Responsibility | Excluded responsibility |
| --- | --- | --- |
| `deploy/stage07-acceptance/compose.yml` | isolated API, Worker, Outbox, Postgres, Redis and static web service composition | Stage03 service replacement or host-port ownership |
| `deploy/stage07-acceptance/Dockerfile.web` | reproducible Vite build and static file serving | client API contract changes or browser secret injection |
| `deploy/stage07-acceptance/Caddyfile.stage07-host` | one Caddy host block that splits static paths and existing root API paths | modification of the existing Stage03 host block |
| `deploy/stage07-acceptance/runtime/.env.stage07-acceptance.example` | names/validation contract and C-selected runtime-file location | real values or credentials |
| remote `deploy/stage07-acceptance/runtime/` | mode-`0700` dedicated runtime directory; the only write-mounted surface for persisted-marker target bootstrap | source-tree exposure, Stage03 file mounts or general deployment writes |
| `deploy/stage07-acceptance/scripts/*` | guarded source staging, preflight, one-time private target capture, ingress activation and rollback | generic deployment platform, persistent webhook consumer or production automation |
| `backend/scripts/stage07_import_persisted_private_target.py` | one-time Stage03 ORM candidate selection plus sanitized target bootstrap contract | raw SQL, Stage03 mutation, a product API/CLI, broad user import or a permanent bridge |
| remote `/home/ubuntu/stage07-acceptance` | disposable execution directory | historical `/home/ubuntu/telegram-bitable-work-agent` mutation except one validated Caddy host append/restore |

## Data and Interface Flow

```text
source worktree archive
  -> isolated remote directory
  -> existing Stage03 persisted marker (read-only, one bind window only)
  -> atomic isolated target-env bootstrap within dedicated runtime directory
  -> compose build
  -> isolated DB migration
  -> HTTPS host validation
  -> existing S6.1/S6.2 interfaces
  -> sanitized evidence / cleanup
```

Only the existing FastAPI routes and the existing TD008 Worker invoke Telegram. The Vite bundle makes same-origin calls exactly as it does locally. No browser route accepts a deployment argument, secret, chat identifier or raw deep link.

## Operational Ownership

- Codex: local artifact preparation, isolated deployment commands, read-only verification, bounded S6.1/S6.2 invocation, sanitized evidence and rollback command preparation.
- User: explicit deployment authority (granted), DNS ownership, BotFather Main Mini App configuration, private test-chat ownership and any human Telegram tap needed for signed `initData`.
- Existing Stage03: remains owner of its containers, data, public host and historical runtime; it is not an input data source for the Stage07 database.
- Persisted-marker exception: only after the user-selected bridge direction and C runtime layout, the already persisted exact marker may be read once through the Stage03 API image's existing ORM. It supplies no business record/data to the Stage07 database; only the transient private test target is transferred into the ignored dedicated runtime env.
