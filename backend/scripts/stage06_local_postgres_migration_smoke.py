from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@dataclass(frozen=True)
class LocalPostgresClassification:
    host: str
    database: str
    safe_url: str
    schema: str | None = None


def classify_local_postgres_url(database_url: str) -> LocalPostgresClassification:
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        raise RuntimeError("Stage06 migration smoke requires PostgreSQL")
    if url.host not in {"localhost", "127.0.0.1"}:
        raise RuntimeError("Stage06 migration smoke only allows local PostgreSQL")
    database = url.database or ""
    if "stage06" not in database and "test" not in database and "smoke" not in database:
        raise RuntimeError(
            "Stage06 migration smoke requires a disposable database name "
            "containing stage06, test or smoke"
        )
    return LocalPostgresClassification(
        host=url.host or "",
        database=database,
        safe_url=url.render_as_string(hide_password=True),
    )


def classify_local_postgres_schema_target(
    database_url: str,
    schema: str,
) -> LocalPostgresClassification:
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        raise RuntimeError("Stage06 migration smoke requires PostgreSQL")
    if url.host not in {"localhost", "127.0.0.1"}:
        raise RuntimeError("Stage06 migration smoke only allows local PostgreSQL")
    if not _is_disposable_name(schema):
        raise RuntimeError(
            "Stage06 migration smoke schema must be disposable and contain "
            "stage06, test or smoke"
        )
    return LocalPostgresClassification(
        host=url.host or "",
        database=url.database or "",
        safe_url=url.render_as_string(hide_password=True),
        schema=schema,
    )


def main() -> int:
    database_url = os.getenv("STAGE06_LOCAL_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        return _emit(
            {
                "ok": False,
                "status": "blocked",
                "missing": ["STAGE06_LOCAL_DATABASE_URL"],
                "message": "Set STAGE06_LOCAL_DATABASE_URL to a disposable local PostgreSQL database.",
            },
            exit_code=2,
        )
    try:
        schema = os.getenv("STAGE06_LOCAL_DATABASE_SCHEMA")
        try:
            classification = classify_local_postgres_url(database_url)
            migration_url = database_url
            engine = create_engine(database_url, future=True, pool_pre_ping=True)
            _reset_public_schema(engine)
        except RuntimeError as exc:
            if schema is None or "disposable database name" not in str(exc):
                raise
            classification = classify_local_postgres_schema_target(database_url, schema)
            engine = create_engine(database_url, future=True, pool_pre_ping=True)
            _reset_named_schema(engine, schema)
            migration_url = database_url
            os.environ["PGOPTIONS"] = f"-csearch_path={schema}"

        os.environ["DATABASE_URL"] = migration_url
        smoke_engine = create_engine(migration_url, future=True, pool_pre_ping=True)
        command.upgrade(_alembic_config(migration_url), "head")
        inspector = inspect(smoke_engine)
        table_names = set(inspector.get_table_names())
        required_tables = {
            "workspaces",
            "bases",
            "tables",
            "fields",
            "records",
            "views",
            "templates",
            "import_jobs",
            "digital_employees",
            "record_change_drafts",
            "notification_requests",
            "stage06_idempotency_records",
            "agent_runs",
            "ops_audit_events",
        }
        missing_tables = sorted(required_tables - table_names)
        if missing_tables:
            return _emit(
                {
                    "ok": False,
                    "status": "failed",
                    "database": classification.safe_url,
                    "missing_tables": missing_tables,
                },
                exit_code=1,
            )
        with engine.connect() as connection:
            if classification.schema is None:
                version = connection.scalar(text("select version_num from alembic_version"))
            else:
                version = connection.scalar(
                    text(
                        f'select version_num from "{classification.schema}".alembic_version'
                    )
                )
        smoke_engine.dispose()
        engine.dispose()
        return _emit(
            {
                "ok": True,
                "status": "passed",
                "database": classification.safe_url,
                "schema": classification.schema,
                "alembic_version": version,
                "checked_tables": sorted(required_tables),
            }
        )
    except Exception as exc:
        return _emit(
            {
                "ok": False,
                "status": "blocked" if isinstance(exc, RuntimeError) else "failed",
                "error": type(exc).__name__,
                "message": str(exc),
            },
            exit_code=2 if isinstance(exc, RuntimeError) else 1,
        )


def _alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _reset_public_schema(engine) -> None:
    with engine.execution_options(isolation_level="AUTOCOMMIT").connect() as connection:
        connection.execute(text("drop schema if exists public cascade"))
        connection.execute(text("create schema public"))
        connection.execute(text("grant all on schema public to public"))


def _reset_named_schema(engine, schema: str) -> None:
    with engine.execution_options(isolation_level="AUTOCOMMIT").connect() as connection:
        connection.execute(text(f'drop schema if exists "{schema}" cascade'))
        connection.execute(text(f'create schema "{schema}"'))
        connection.execute(text(f'grant all on schema "{schema}" to public'))


def _is_disposable_name(value: str) -> bool:
    return "stage06" in value or "test" in value or "smoke" in value


def _emit(payload: dict[str, object], *, exit_code: int = 0) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
