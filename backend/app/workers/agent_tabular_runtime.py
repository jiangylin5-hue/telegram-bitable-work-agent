from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import os
from time import sleep
from typing import Callable

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.routes.stage08_collaboration import (
    complete_assistant_query,
    resume_assistant_query,
)
from app.core.config import Settings, validate_runtime_settings
from app.core.database import get_session_factory
from app.queues.redis_streams import RedisStreams, RedisStreamJob
from app.queues.redis_streams import RedisStreamsClient
from app.schemas.agent_event_runtime import AgentCommandEnvelope
from app.schemas.stage08_collaboration import AssistantQueryRequest
from app.services.agent_event_runtime import SqlAlchemyAgentEventRuntimeUnitOfWork
from app.services.agent_orchestrator import (
    OrchestratorError,
    SpecialistSafeResult,
    build_authorization_hash,
    execute_read_only_specialist,
    fail_specialist_command,
)
from app.services.agent_private_inputs import PrivateInputError, open_agent_private_input
from app.services.stage06_authorization import Stage06AuthorizationError
from app.services.stage06_identity import Stage06RequestIdentity
from app.services.stage06_platform import (
    PlatformValidationError,
    SqlAlchemyStage06PlatformUnitOfWork,
)


DEFAULT_STREAM_NAME = "agent.commands.platform.tabular.analyse"
DEFAULT_GROUP_NAME = "stage10-tabular-workers"


@dataclass(frozen=True, slots=True)
class AgentTabularWorkerResult:
    processed: int = 0
    recovered: int = 0
    dead_lettered: int = 0


class AgentTabularStreamWorker:
    def __init__(
        self,
        *,
        streams: RedisStreams,
        consumer_name: str,
        process: Callable[[AgentCommandEnvelope], None],
        stream_name: str = DEFAULT_STREAM_NAME,
        group_name: str = DEFAULT_GROUP_NAME,
        pending_min_idle_ms: int = 30_000,
    ) -> None:
        self.streams = streams
        self.consumer_name = consumer_name
        self.process = process
        self.stream_name = stream_name
        self.group_name = group_name
        self.pending_min_idle_ms = pending_min_idle_ms

    def run_once(self, limit: int = 10) -> AgentTabularWorkerResult:
        recovered_jobs = self.streams.claim_pending(
            self.stream_name,
            group_name=self.group_name,
            consumer_name=self.consumer_name,
            min_idle_ms=self.pending_min_idle_ms,
            count=limit,
        )
        jobs = recovered_jobs or self.streams.read_group(
            self.stream_name,
            group_name=self.group_name,
            consumer_name=self.consumer_name,
            count=limit,
        )
        processed = 0
        dead_lettered = 0
        for job in jobs:
            try:
                envelope = _parse_job(job)
            except ValueError:
                self.streams.xadd_once(
                    f"{self.stream_name}.dead-letter",
                    idempotency_key=hashlib.sha256(
                        f"{self.stream_name}:{job.entry_id}".encode("utf-8")
                    ).hexdigest(),
                    fields={
                        "source_stream": self.stream_name,
                        "source_entry_id": job.entry_id,
                        "error_code": "agent_command_stream_invalid",
                    },
                )
                self.streams.ack(
                    self.stream_name,
                    group_name=self.group_name,
                    entry_id=job.entry_id,
                )
                dead_lettered += 1
                continue
            self.process(envelope)
            self.streams.ack(
                self.stream_name,
                group_name=self.group_name,
                entry_id=job.entry_id,
            )
            processed += 1
        return AgentTabularWorkerResult(
            processed=processed,
            recovered=len(recovered_jobs),
            dead_lettered=dead_lettered,
        )

    def run_continuously(self) -> None:
        while True:
            if self.run_once() == AgentTabularWorkerResult():
                sleep(0.5)


def process_agent_tabular_command(
    session: Session,
    envelope: AgentCommandEnvelope,
    *,
    settings: Settings,
    worker_id: str,
    now: datetime | None = None,
) -> None:
    now = now or datetime.now(UTC)
    runtime_uow = SqlAlchemyAgentEventRuntimeUnitOfWork(session)
    command = runtime_uow.get_command(envelope.command_id, for_update=True)
    if command is None or command.run_id != envelope.run_id:
        raise OrchestratorError("agent_command_not_found")
    run = runtime_uow.get_run(envelope.run_id, for_update=True)
    if run is None:
        raise OrchestratorError("agent_run_not_found")
    authorization_hash = envelope.scope_proof_ref.removeprefix("scope:sha256:")
    if (
        run.scope_hash != authorization_hash
        or command.target_capability != envelope.target_capability
        or command.command_type != envelope.command_type
        or command.idempotency_key_hash != envelope.idempotency_key_hash
        or command.deadline_at != envelope.deadline_at
    ):
        raise OrchestratorError("agent_command_envelope_mismatch")
    if command.status == "completed":
        execute_read_only_specialist(
            runtime_uow,
            command_id=command.id,
            authorization_hash=authorization_hash,
            worker_id=worker_id,
            now=now,
            execute=lambda: (_ for _ in ()).throw(
                RuntimeError("completed_command_must_not_execute")
            ),
        )
        session.commit()
        return
    prefix = "agent-private-input:"
    if command.payload_ref is None or not command.payload_ref.startswith(prefix):
        raise OrchestratorError("agent_private_input_ref_invalid")
    from uuid import UUID

    try:
        private_input_id = UUID(command.payload_ref.removeprefix(prefix))
    except ValueError as exc:
        raise OrchestratorError("agent_private_input_ref_invalid") from exc
    private_input = runtime_uow.get_private_input(private_input_id, for_update=True)
    if (
        private_input is None
        or private_input.run_id != run.id
        or private_input.command_id != command.id
        or settings.agent_runtime_input_key is None
    ):
        raise OrchestratorError("agent_private_input_unavailable")
    try:
        payload = open_agent_private_input(
            private_input,
            key_b64=settings.agent_runtime_input_key,
            run_id=run.id,
            command_id=command.id,
            scope_hash=authorization_hash,
            now=now,
        )
        if (
            payload.workspace_id != run.workspace_id
            or payload.employee_id != run.root_employee_id
        ):
            raise OrchestratorError("agent_private_input_scope_mismatch")
        request = AssistantQueryRequest.model_validate(
            {
                "workspace_id": str(payload.workspace_id),
                "employee_id": str(payload.employee_id),
                "intent": payload.intent,
                "query": payload.query,
                "requested_action": "read_only",
                "target_record_id": (
                    None
                    if payload.target_record_id is None
                    else str(payload.target_record_id)
                ),
                "idempotency_key": payload.idempotency_key,
                "skill_id": payload.skill_id,
            }
        )
        platform_uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        identity = Stage06RequestIdentity(
            user_id=payload.actor_user_id,
            source="verified_adapter",
        )
        prepared = resume_assistant_query(request, identity, platform_uow)
        current_hash = build_authorization_hash(
            workspace_id=payload.workspace_id,
            employee_id=payload.employee_id,
            target_record_id=payload.target_record_id,
            actor_user_id=prepared.actor.actor_id,
        )
        if current_hash != authorization_hash:
            raise OrchestratorError("agent_command_scope_drift")
    except (
        OrchestratorError,
        PlatformValidationError,
        PrivateInputError,
        Stage06AuthorizationError,
        ValidationError,
    ):
        _fail_terminal_command(
            session,
            command_id=command.id,
            private_input_id=private_input_id,
            authorization_hash=authorization_hash,
            worker_id=worker_id,
        )
        return
    result_storage_ref = f"stage08-idempotency:{prepared.reservation.id}"

    def execute() -> SpecialistSafeResult:
        safe_view = complete_assistant_query(prepared, platform_uow)
        safe_payload = json.dumps(
            safe_view.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return SpecialistSafeResult(
            storage_ref=result_storage_ref,
            content_hash=hashlib.sha256(safe_payload.encode("utf-8")).hexdigest(),
            safe_summary=_bounded_summary(safe_view.answer),
            metrics={"citations": len(safe_view.citations)},
        )

    try:
        execute_read_only_specialist(
            runtime_uow,
            command_id=command.id,
            authorization_hash=authorization_hash,
            worker_id=worker_id,
            now=now,
            execute=execute,
        )
        private_input.consumed_at = datetime.now(UTC)
        session.commit()
    except Exception:
        _fail_terminal_command(
            session,
            command_id=command.id,
            private_input_id=private_input_id,
            authorization_hash=authorization_hash,
            worker_id=worker_id,
        )


def _fail_terminal_command(
    session: Session,
    *,
    command_id: object,
    private_input_id: object,
    authorization_hash: str,
    worker_id: str,
) -> None:
    session.rollback()
    runtime_uow = SqlAlchemyAgentEventRuntimeUnitOfWork(session)
    private_input = runtime_uow.get_private_input(private_input_id, for_update=True)
    if private_input is not None:
        private_input.consumed_at = datetime.now(UTC)
    fail_specialist_command(
        runtime_uow,
        command_id=command_id,
        authorization_hash=authorization_hash,
        worker_id=worker_id,
        now=datetime.now(UTC),
    )
    session.commit()


def _bounded_summary(answer: str | None) -> str:
    normalized = " ".join((answer or "").split())
    return normalized[:240] if normalized else "只读分析已完成"


def _parse_job(job: RedisStreamJob) -> AgentCommandEnvelope:
    try:
        payload = job.fields["payload"]
        envelope = AgentCommandEnvelope.model_validate_json(payload)
    except (KeyError, ValidationError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("agent_command_stream_invalid") from exc
    if job.fields.get("schema_version") != envelope.schema_version:
        raise ValueError("agent_command_stream_invalid")
    return envelope


def main() -> None:
    settings = validate_runtime_settings()
    if settings.agent_event_runtime_mode != "redis_worker":
        raise RuntimeError("Stage10 tabular worker requires redis_worker mode")
    streams = RedisStreamsClient.from_url(settings.redis_url)
    session_factory = get_session_factory()
    consumer_name = os.getenv("AGENT_TABULAR_CONSUMER_NAME", "stage10-tabular-1")

    def process(envelope: AgentCommandEnvelope) -> None:
        with session_factory() as session:
            process_agent_tabular_command(
                session,
                envelope,
                settings=settings,
                worker_id=consumer_name,
            )

    AgentTabularStreamWorker(
        streams=streams,
        consumer_name=consumer_name,
        process=process,
    ).run_continuously()


__all__ = [
    "AgentTabularStreamWorker",
    "AgentTabularWorkerResult",
    "DEFAULT_GROUP_NAME",
    "DEFAULT_STREAM_NAME",
    "process_agent_tabular_command",
]


if __name__ == "__main__":
    main()
