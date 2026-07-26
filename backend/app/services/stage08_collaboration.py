from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import hashlib
import math
from threading import Lock
from time import monotonic
from typing import Final, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.runtime.stage08_collaboration_contracts import (
    CollaborationBudget,
    CompressionOutcome,
    ContextCompressor,
    AnalysisProvider,
    AnalysisProviderOutcome,
    AnalysisDecision,
    AssistantQuerySafeCitation,
    AssistantQuerySafeView,
    Stage08CollaborationContractFactory,
    Stage08CollaborationState,
    UnavailableAnalysisProvider,
    UnavailableContextCompressor,
    _command_snapshot,
    _draft_intent_snapshot,
    _read_outcome_snapshot,
    _state_snapshot,
    validate_analysis_decision,
)
from app.models.agent import AgentRun
from app.runtime.stage08_contracts import (
    ExecutionBudget,
    ExecutionPlan,
    ExecutionTicketState,
    ToolInvocation,
)
from app.runtime.stage08_tool_gateway import Stage08ToolGateway
from app.services.audit import record_audit_event
from app.runtime.stage08_context_contracts import ContextBudget, ContextPlanningRequest
from app.services.permissions import Actor
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    PlatformValidationError,
    SqlAlchemyStage06PlatformUnitOfWork,
    Stage06PlatformUnitOfWork,
    can_actor_write_record_fields,
    stage08_e3_safe_execution_boundary,
)
from app.services.stage08_context import build_context_plan
from app.services.stage08_runtime import begin_execution_plan
from app.services.stage08_context_composition import (
    compose_stage08_context,
    prepare_stage08_group_compression_material,
    render_stage08_composite_context,
    validate_stage08_group_compression_digest,
)
from app.services.stage08_retrieval_provider import (
    PostgresRetrievalProvider,
    Stage08RetrievalAuthorityFactory,
    _result_snapshot as _retrieval_result_snapshot,
)


_READ_RESULT_ISSUER: Final[object] = object()
_READ_RESULT_SEAL: Final[object] = object()
_RUNTIME_CONTROL_ISSUER: Final[object] = object()
_RUNTIME_CONTROL_SEAL: Final[object] = object()
_READ_COLLECTOR_ISSUER: Final[object] = object()
_READ_COLLECTOR_SEAL: Final[object] = object()
_READ_UOW_FACTORY_ISSUER: Final[object] = object()
_READ_UOW_FACTORY_SEAL: Final[object] = object()
_STRICT_SAFE_CONFIG = ConfigDict(extra="forbid", frozen=True, strict=True)
_INMEMORY_READ_LOCK: Final[Lock] = Lock()


@dataclass(slots=True)
class _RuntimeControlSnapshot:
    seal: object
    monotonic_now: Callable[[], float]
    cancellation_probe: Callable[[], bool]
    branch_probe: Callable[[str, int | None], None]
    deadline_at: float
    provider_time_seconds: float
    lock: Lock
    terminal_status: Literal["cancelled", "timed_out"] | None = None


class Stage08CollaborationRuntimeControl:
    """Opaque process-local deadline/cancellation carrier; never enters graph state."""

    __slots__ = ("_sealed_snapshot",)

    def __new__(cls, issuer: object = None, snapshot: object = None):
        if issuer is not _RUNTIME_CONTROL_ISSUER:
            raise TypeError("stage08_collaboration_runtime_control_private")
        instance = object.__new__(cls)
        object.__setattr__(instance, "_sealed_snapshot", snapshot)
        return instance

    def __init__(self, issuer: object = None, snapshot: object = None) -> None:
        del issuer, snapshot

    def __getattribute__(self, name: str):
        if name in {"__class__", "__reduce__", "__reduce_ex__"}:
            return object.__getattribute__(self, name)
        raise AttributeError("stage08_collaboration_runtime_control_private")

    def __repr__(self) -> str:
        return "<Stage08CollaborationRuntimeControl opaque>"

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("stage08_collaboration_runtime_control_unavailable")


@dataclass(frozen=True, slots=True)
class _CompositeBranchResult:
    outcome: object | None
    pending_compression: object | None
    composite_text: str | None
    group_status: Literal[
        "not_requested",
        "direct",
        "compressed",
        "compression_unavailable",
        "unavailable",
    ]


@dataclass(frozen=True, slots=True)
class _RetrievalBranchResult:
    outcome: object
    citation_count: int
    source_proof: tuple[tuple[UUID, int, UUID], ...]


@dataclass(slots=True)
class _ReadCollectorSnapshot:
    seal: object
    lock: Lock
    plan: object | None = None
    group_scope_proof: _GroupScopeProof | None = None
    composite: _CompositeBranchResult | None = None
    retrieval: _RetrievalBranchResult | None = None


class _Stage08ReadCollector:
    __slots__ = ("_sealed_snapshot",)

    def __new__(cls, issuer: object = None, snapshot: object = None):
        if issuer is not _READ_COLLECTOR_ISSUER:
            raise TypeError("stage08_collaboration_read_collector_private")
        instance = object.__new__(cls)
        object.__setattr__(instance, "_sealed_snapshot", snapshot)
        return instance

    def __init__(self, issuer: object = None, snapshot: object = None) -> None:
        del issuer, snapshot

    def __getattribute__(self, name: str):
        if name in {"__class__", "__reduce__", "__reduce_ex__"}:
            return object.__getattribute__(self, name)
        raise AttributeError("stage08_collaboration_read_collector_private")

    def __repr__(self) -> str:
        return "<_Stage08ReadCollector opaque>"

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("stage08_collaboration_read_collector_unavailable")


@dataclass(frozen=True, slots=True)
class _ReadUowFactorySnapshot:
    seal: object
    sql_session_factory: sessionmaker[Session] | None
    in_memory_uow: InMemoryStage06PlatformUnitOfWork | None


class _Stage08ReadUowFactory:
    """Coordinator-issued branch factory; workers never inspect request Session."""

    __slots__ = ("_sealed_snapshot",)

    def __new__(cls, issuer: object = None, snapshot: object = None):
        if issuer is not _READ_UOW_FACTORY_ISSUER:
            raise TypeError("stage08_collaboration_read_uow_factory_private")
        instance = object.__new__(cls)
        object.__setattr__(instance, "_sealed_snapshot", snapshot)
        return instance

    def __init__(self, issuer: object = None, snapshot: object = None) -> None:
        del issuer, snapshot

    def __getattribute__(self, name: str):
        if name in {"__class__", "__reduce__", "__reduce_ex__"}:
            return object.__getattribute__(self, name)
        raise AttributeError("stage08_collaboration_read_uow_factory_private")

    def __repr__(self) -> str:
        return "<_Stage08ReadUowFactory opaque>"

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("stage08_collaboration_read_uow_factory_unavailable")


class CollaborationReadSafeView(BaseModel):
    """Count-only E2 result; no query, evidence, identifiers, or authority."""

    model_config = _STRICT_SAFE_CONFIG

    status: Literal["internal_evidence", "general_advice_only", "no_evidence", "degraded"]
    read_child_count: StrictInt = Field(ge=0, le=3)
    retrieval_citation_count: StrictInt = Field(ge=0, le=12)
    group_status: Literal[
        "not_requested",
        "direct",
        "compressed",
        "compression_unavailable",
        "unavailable",
    ]
    degradation_codes: tuple[
        Literal[
            "context_unavailable",
            "retrieval_unavailable",
            "compression_unavailable",
            "no_evidence",
        ],
        ...,
    ] = Field(max_length=4)


@dataclass(frozen=True, slots=True)
class _GroupScopeProof:
    binding_id: UUID | None
    mapping_id: UUID | None
    mapping_version: int | None
    customer_record_id: UUID | None
    project_record_id: UUID | None


def _never_cancelled() -> bool:
    return False


def _ignore_branch_probe(branch: str, session_identity: int | None) -> None:
    del branch, session_identity


def _create_stage08_runtime_control(
    *,
    monotonic_now: Callable[[], float] = monotonic,
    cancellation_probe: Callable[[], bool] = _never_cancelled,
    branch_probe: Callable[[str, int | None], None] = _ignore_branch_probe,
) -> Stage08CollaborationRuntimeControl:
    if not callable(monotonic_now) or not callable(cancellation_probe) or not callable(branch_probe):
        raise TypeError("stage08_collaboration_runtime_control_invalid")
    started_at = monotonic_now()
    if type(started_at) not in {int, float} or not math.isfinite(float(started_at)):
        raise TypeError("stage08_collaboration_runtime_clock_invalid")
    budget = CollaborationBudget()
    return Stage08CollaborationRuntimeControl(
        _RUNTIME_CONTROL_ISSUER,
        _RuntimeControlSnapshot(
            seal=_RUNTIME_CONTROL_SEAL,
            monotonic_now=monotonic_now,
            cancellation_probe=cancellation_probe,
            branch_probe=branch_probe,
            deadline_at=float(started_at) + (budget.max_wall_time_ms / 1000),
            provider_time_seconds=budget.max_provider_time_ms / 1000,
            lock=Lock(),
        ),
    )


def create_stage08_runtime_control() -> Stage08CollaborationRuntimeControl:
    """Create the single deadline carrier shared by one API invocation and provider."""

    return _create_stage08_runtime_control()


def remaining_stage08_runtime_seconds(
    control: Stage08CollaborationRuntimeControl,
) -> float:
    snapshot = _runtime_control_snapshot(control)
    return max(0.0, snapshot.deadline_at - _runtime_now(control))


def _runtime_control_snapshot(value: object) -> _RuntimeControlSnapshot:
    if type(value) is not Stage08CollaborationRuntimeControl:
        raise TypeError("stage08_collaboration_runtime_control_private")
    snapshot = object.__getattribute__(value, "_sealed_snapshot")
    if (
        type(snapshot) is not _RuntimeControlSnapshot
        or snapshot.seal is not _RUNTIME_CONTROL_SEAL
        or not callable(snapshot.monotonic_now)
        or not callable(snapshot.cancellation_probe)
        or not callable(snapshot.branch_probe)
    ):
        raise TypeError("stage08_collaboration_runtime_control_private")
    return snapshot


def _runtime_now(control: object) -> float:
    value = _runtime_control_snapshot(control).monotonic_now()
    if type(value) not in {int, float} or not math.isfinite(float(value)):
        raise TypeError("stage08_collaboration_runtime_clock_invalid")
    return float(value)


def _runtime_terminal_status(
    control: object,
    *,
    provider_started_at: float | None = None,
) -> Literal["cancelled", "timed_out"] | None:
    snapshot = _runtime_control_snapshot(control)
    with snapshot.lock:
        if snapshot.terminal_status is not None:
            return snapshot.terminal_status
        try:
            cancelled = snapshot.cancellation_probe() is True
        except Exception:
            cancelled = True
        if cancelled:
            snapshot.terminal_status = "cancelled"
            return snapshot.terminal_status
        current = _runtime_now(control)
        if current >= snapshot.deadline_at or (
            provider_started_at is not None
            and current - provider_started_at >= snapshot.provider_time_seconds
        ):
            snapshot.terminal_status = "timed_out"
        return snapshot.terminal_status


def _notify_branch_started(
    control: object,
    *,
    branch: str,
    session_identity: int | None,
) -> None:
    snapshot = _runtime_control_snapshot(control)
    snapshot.branch_probe(branch, session_identity)


def _new_read_collector() -> _Stage08ReadCollector:
    return _Stage08ReadCollector(
        _READ_COLLECTOR_ISSUER,
        _ReadCollectorSnapshot(
            seal=_READ_COLLECTOR_SEAL,
            lock=Lock(),
        ),
    )


def _read_collector_snapshot(value: object) -> _ReadCollectorSnapshot:
    if type(value) is not _Stage08ReadCollector:
        raise TypeError("stage08_collaboration_read_collector_private")
    snapshot = object.__getattribute__(value, "_sealed_snapshot")
    if (
        type(snapshot) is not _ReadCollectorSnapshot
        or snapshot.seal is not _READ_COLLECTOR_SEAL
    ):
        raise TypeError("stage08_collaboration_read_collector_private")
    return snapshot


def _collector_record_plan(
    collector: object,
    *,
    plan: object,
    group_scope_proof: _GroupScopeProof,
) -> None:
    snapshot = _read_collector_snapshot(collector)
    with snapshot.lock:
        if snapshot.plan is not None or snapshot.group_scope_proof is not None:
            raise ValueError("stage08_collaboration_plan_duplicate")
        snapshot.plan = plan
        snapshot.group_scope_proof = group_scope_proof


def _collector_plan(
    collector: object,
) -> tuple[object, _GroupScopeProof]:
    snapshot = _read_collector_snapshot(collector)
    with snapshot.lock:
        if snapshot.plan is None or snapshot.group_scope_proof is None:
            raise ValueError("stage08_collaboration_plan_missing")
        return snapshot.plan, snapshot.group_scope_proof


def _collector_record_composite(
    collector: object,
    result: _CompositeBranchResult,
) -> None:
    snapshot = _read_collector_snapshot(collector)
    with snapshot.lock:
        if snapshot.composite is not None:
            raise ValueError("stage08_collaboration_composite_duplicate")
        snapshot.composite = result


def _collector_replace_composite(
    collector: object,
    result: _CompositeBranchResult,
) -> None:
    snapshot = _read_collector_snapshot(collector)
    with snapshot.lock:
        if snapshot.composite is None:
            raise ValueError("stage08_collaboration_composite_missing")
        snapshot.composite = result


def _collector_record_retrieval(
    collector: object,
    result: _RetrievalBranchResult,
) -> None:
    snapshot = _read_collector_snapshot(collector)
    with snapshot.lock:
        if snapshot.retrieval is not None:
            raise ValueError("stage08_collaboration_retrieval_duplicate")
        snapshot.retrieval = result


def _create_stage08_read_uow_factory(
    source_uow: Stage06PlatformUnitOfWork,
) -> _Stage08ReadUowFactory:
    """Resolve the immutable bind once on the coordinator thread before fan-out."""

    if isinstance(source_uow, SqlAlchemyStage06PlatformUnitOfWork):
        bind = source_uow.session.get_bind()
        engine = getattr(bind, "engine", bind)
        return _Stage08ReadUowFactory(
            _READ_UOW_FACTORY_ISSUER,
            _ReadUowFactorySnapshot(
                seal=_READ_UOW_FACTORY_SEAL,
                sql_session_factory=sessionmaker(
                    bind=engine,
                    autoflush=False,
                    expire_on_commit=False,
                    future=True,
                ),
                in_memory_uow=None,
            ),
        )
    if isinstance(source_uow, InMemoryStage06PlatformUnitOfWork):
        return _Stage08ReadUowFactory(
            _READ_UOW_FACTORY_ISSUER,
            _ReadUowFactorySnapshot(
                seal=_READ_UOW_FACTORY_SEAL,
                sql_session_factory=None,
                in_memory_uow=source_uow,
            ),
        )
    raise TypeError("stage08_collaboration_read_uow_unsupported")


def _read_uow_factory_snapshot(value: object) -> _ReadUowFactorySnapshot:
    if type(value) is not _Stage08ReadUowFactory:
        raise TypeError("stage08_collaboration_read_uow_factory_private")
    snapshot = object.__getattribute__(value, "_sealed_snapshot")
    if (
        type(snapshot) is not _ReadUowFactorySnapshot
        or snapshot.seal is not _READ_UOW_FACTORY_SEAL
        or (snapshot.sql_session_factory is None)
        == (snapshot.in_memory_uow is None)
    ):
        raise TypeError("stage08_collaboration_read_uow_factory_private")
    return snapshot


@dataclass(frozen=True, slots=True)
class _ReadResultSnapshot:
    seal: object
    state: Stage08CollaborationState
    view: CollaborationReadSafeView
    plan: object | None
    group_scope_proof: _GroupScopeProof | None
    retrieval_source_proof: tuple[tuple[UUID, int, UUID], ...]


class Stage08CollaborationReadResult:
    __slots__ = ("_sealed_snapshot",)

    def __new__(cls, issuer: object = None, snapshot: object = None):
        if issuer is not _READ_RESULT_ISSUER:
            raise TypeError("stage08_collaboration_read_result_private")
        instance = object.__new__(cls)
        object.__setattr__(instance, "_sealed_snapshot", snapshot)
        return instance

    def __init__(self, issuer: object = None, snapshot: object = None) -> None:
        del issuer, snapshot

    def __getattribute__(self, name: str):
        if name in {"__class__", "safe_view", "__reduce__", "__reduce_ex__"}:
            return object.__getattribute__(self, name)
        raise AttributeError("stage08_collaboration_read_result_private")

    def __repr__(self) -> str:
        return "<Stage08CollaborationReadResult opaque>"

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("stage08_collaboration_read_result_unavailable")

    def safe_view(self) -> CollaborationReadSafeView:
        snapshot = _read_result_snapshot(self)
        return CollaborationReadSafeView.model_validate(
            snapshot.view.model_dump(mode="python")
        )


@dataclass(frozen=True, slots=True)
class Stage08CollaborationReadDependencies:
    context_compressor: ContextCompressor = UnavailableContextCompressor()
    retrieval_provider: PostgresRetrievalProvider = PostgresRetrievalProvider()


@dataclass(frozen=True, slots=True)
class Stage08CollaborationDependencies:
    """E3's in-process ports; all external providers remain unavailable by default."""

    read_dependencies: Stage08CollaborationReadDependencies = (
        Stage08CollaborationReadDependencies()
    )
    analysis_provider: AnalysisProvider = UnavailableAnalysisProvider()
    tool_gateway: Stage08ToolGateway = Stage08ToolGateway()


def execute_collaboration_reads(
    uow: Stage06PlatformUnitOfWork,
    command: object,
    actor: Actor,
    deps: Stage08CollaborationReadDependencies = Stage08CollaborationReadDependencies(),
    *,
    now: datetime,
) -> Stage08CollaborationReadResult:
    """Perform E2's bounded C3/D4 reads without any persistence or provider call."""

    snapshot = _command_snapshot(command)
    if not _valid_actor(actor, snapshot.actor_user_id) or not _valid_dependencies(deps):
        return _result_for_invalid_command(command)
    try:
        plan, group_scope_proof = _build_current_plan(uow, snapshot, actor)
    except (PlatformValidationError, TypeError, ValueError, AttributeError):
        return _result_for_invalid_command(command)

    state = Stage08CollaborationContractFactory.transition(
        Stage08CollaborationContractFactory.initial_state(command),
        status="reading",
    )
    degradation_codes: list[str] = []
    group_status = "not_requested"
    retrieval_citation_count = 0
    has_internal_material = False

    composite = compose_stage08_context(uow, plan, actor=actor, now=now)
    composite_view = composite.view()
    composite_text = render_stage08_composite_context(uow, composite, now=now)
    if composite_view.status == "group_compression_pending":
        group_status = "compression_unavailable"
        pending = prepare_stage08_group_compression_material(uow, composite, now=now)
        if pending is not None:
            try:
                compressor_input = Stage08CollaborationContractFactory.provider_input(
                    Stage08CollaborationContractFactory.private_material(
                        pending, kind="composite_context"
                    )
                )
                compression = deps.context_compressor.compress(
                    compressor_input,
                    budget=CollaborationBudget(),
                )
                if type(compression) is not CompressionOutcome:
                    raise TypeError("compression_outcome_invalid")
                compression = CompressionOutcome.model_validate(
                    compression.model_dump(mode="python")
                )
                accepted_compression = (
                    compression.status == "available"
                    and compression.digest is not None
                    and validate_stage08_group_compression_digest(
                        uow, pending, digest=compression.digest, now=now
                    )
                )
            except Exception:
                compression = None
                accepted_compression = False
            if accepted_compression and compression is not None:
                state = Stage08CollaborationContractFactory.record_compressed_digest(
                    state, compression.digest
                )
                group_status = "compressed"
                combined = Stage08CollaborationContractFactory.private_material(
                    (composite_text or "", compression.digest),
                    kind="analysis_material",
                )
                state = Stage08CollaborationContractFactory.record_read_outcome(
                    state,
                    Stage08CollaborationContractFactory.read_outcome(
                        branch="composite_context",
                        status="available",
                        reason_code="none",
                        material=combined,
                    ),
                )
                has_internal_material = True
            else:
                degradation_codes.append("compression_unavailable")
                state = Stage08CollaborationContractFactory.record_read_outcome(
                    state,
                    Stage08CollaborationContractFactory.read_outcome(
                        branch="composite_context",
                        status="degraded",
                        reason_code="compression_unavailable",
                        material=(
                            None
                            if not composite_text
                            else Stage08CollaborationContractFactory.private_material(
                                composite_text, kind="composite_context"
                            )
                        ),
                    ),
                )
                has_internal_material = bool(composite_text)
        else:
            degradation_codes.append("compression_unavailable")
            state = Stage08CollaborationContractFactory.record_read_outcome(
                state,
                Stage08CollaborationContractFactory.read_outcome(
                    branch="composite_context",
                    status="degraded",
                    reason_code="compression_unavailable",
                    material=None,
                ),
            )
    elif composite_text:
        group_status = "direct" if composite_view.group_status != "group_context_unavailable" else "unavailable"
        state = Stage08CollaborationContractFactory.record_read_outcome(
            state,
            Stage08CollaborationContractFactory.read_outcome(
                branch="composite_context",
                status="available",
                reason_code="none",
                material=Stage08CollaborationContractFactory.private_material(
                    composite_text, kind="composite_context"
                ),
            ),
        )
        has_internal_material = composite_view.status == "internal_evidence"
    else:
        group_status = "unavailable"
        degradation_codes.append("context_unavailable")
        state = Stage08CollaborationContractFactory.record_read_outcome(
            state,
            Stage08CollaborationContractFactory.read_outcome(
                branch="composite_context",
                status="unavailable",
                reason_code="context_unavailable",
                material=None,
            ),
        )

    evidence = None
    safe_retrieval = None
    retrieval_source_proof: tuple[tuple[UUID, int, UUID], ...] = ()
    retrieval_skipped_for_general_advice = snapshot.intent == "general_advice"
    if not retrieval_skipped_for_general_advice:
        try:
            if not _group_scope_proof_is_current(
                uow, snapshot, actor, group_scope_proof
            ):
                raise PlatformValidationError(
                    "stage08_collaboration_group_scope_changed",
                    "stage08_collaboration_group_scope_changed",
                )
            authority = Stage08RetrievalAuthorityFactory.build(
                uow,
                actor=actor,
                workspace_id=snapshot.workspace_id,
                employee_id=snapshot.employee_id,
                customer_record_id=plan.business_scope.customer_record_id,
                project_record_id=plan.business_scope.project_record_id,
            )
            result = deps.retrieval_provider.search(
                uow,
                authority,
                query=snapshot.query,
                limit=12,
                now=now,
            )
            evidence = deps.retrieval_provider.render_private_evidence(
                uow, result, now=now
            )
            retrieval_snapshot = _retrieval_result_snapshot(result)
            if retrieval_snapshot is not None and evidence is not None:
                retrieval_source_proof = tuple(
                    sorted(
                        {
                            (hit.source_id, hit.source_version, hit.chunk_id)
                            for hit in retrieval_snapshot.hits
                        },
                        key=lambda value: (str(value[0]), value[1], str(value[2])),
                    )
                )
            safe_retrieval = deps.retrieval_provider.safe_view(uow, result, now=now)
            retrieval_citation_count = safe_retrieval.result_count
        except Exception:
            evidence = None
            safe_retrieval = None
            retrieval_citation_count = 0
    if retrieval_skipped_for_general_advice:
        state = Stage08CollaborationContractFactory.record_read_outcome(
            state,
            Stage08CollaborationContractFactory.read_outcome(
                branch="retrieval",
                status="degraded",
                reason_code="no_evidence",
                material=None,
            ),
        )
    elif evidence is not None:
        state = Stage08CollaborationContractFactory.record_read_outcome(
            state,
            Stage08CollaborationContractFactory.read_outcome(
                branch="retrieval",
                status="available",
                reason_code="none",
                material=Stage08CollaborationContractFactory.private_material(
                    evidence, kind="retrieval_evidence"
                ),
            ),
        )
        has_internal_material = True
    else:
        retrieval_status = (
            "unavailable"
            if safe_retrieval is None
            or safe_retrieval.status in {"unavailable", "failed"}
            else "degraded"
        )
        reason_code = "retrieval_unavailable" if retrieval_status == "unavailable" else "no_evidence"
        degradation_codes.append(reason_code)
        state = Stage08CollaborationContractFactory.record_read_outcome(
            state,
            Stage08CollaborationContractFactory.read_outcome(
                branch="retrieval",
                status=retrieval_status,
                reason_code=reason_code,
                material=None,
            ),
        )

    if not has_internal_material and snapshot.intent == "general_advice":
        state = Stage08CollaborationContractFactory.record_read_outcome(
            state,
            Stage08CollaborationContractFactory.read_outcome(
                branch="general_advice",
                status="available",
                reason_code="none",
                material=Stage08CollaborationContractFactory.private_material(
                    "general_advice", kind="general_advice"
                ),
            ),
        )
        status = "general_advice_only"
    else:
        status = (
            "internal_evidence"
            if has_internal_material
            else "degraded"
            if degradation_codes
            else "no_evidence"
        )
    if not has_internal_material and status != "general_advice_only" and not degradation_codes:
        degradation_codes.append("no_evidence")
    view = CollaborationReadSafeView(
        status=status,
        read_child_count=Stage08CollaborationContractFactory.read_outcome_count(state),
        retrieval_citation_count=retrieval_citation_count,
        group_status=group_status,
        degradation_codes=tuple(dict.fromkeys(degradation_codes)),
    )
    return Stage08CollaborationReadResult(
        _READ_RESULT_ISSUER,
        _ReadResultSnapshot(
            seal=_READ_RESULT_SEAL,
            state=state,
            view=view,
            plan=plan,
            group_scope_proof=group_scope_proof,
            retrieval_source_proof=retrieval_source_proof,
        ),
    )


@contextmanager
def _isolated_read_uow(
    read_uow_factory: object,
    control: object,
    *,
    branch: Literal["composite_context", "retrieval"],
) -> Iterator[Stage06PlatformUnitOfWork]:
    """Open one isolated SQLAlchemy read transaction or locked test fallback."""

    factory = _read_uow_factory_snapshot(read_uow_factory)
    if factory.sql_session_factory is not None:
        with factory.sql_session_factory() as session:
            try:
                if session.get_bind().dialect.name == "postgresql":
                    session.execute(text("SET TRANSACTION READ ONLY"))
                _notify_branch_started(
                    control,
                    branch=branch,
                    session_identity=id(session),
                )
                yield SqlAlchemyStage06PlatformUnitOfWork(session)
            finally:
                session.rollback()
        return
    if factory.in_memory_uow is not None:
        with _INMEMORY_READ_LOCK:
            _notify_branch_started(
                control,
                branch=branch,
                session_identity=id(factory.in_memory_uow),
            )
            yield factory.in_memory_uow
        return
    raise TypeError("stage08_collaboration_read_uow_unsupported")


def _execute_composite_read_branch(
    uow: Stage06PlatformUnitOfWork,
    plan: object,
    actor: Actor,
    *,
    now: datetime,
) -> _CompositeBranchResult:
    try:
        composite = compose_stage08_context(uow, plan, actor=actor, now=now)
        composite_view = composite.view()
        composite_text = render_stage08_composite_context(uow, composite, now=now)
        if composite_view.status == "group_compression_pending":
            pending = prepare_stage08_group_compression_material(
                uow, composite, now=now
            )
            if pending is not None:
                return _CompositeBranchResult(
                    outcome=None,
                    pending_compression=pending,
                    composite_text=composite_text,
                    group_status="compression_unavailable",
                )
            return _CompositeBranchResult(
                outcome=Stage08CollaborationContractFactory.read_outcome(
                    branch="composite_context",
                    status="degraded",
                    reason_code="compression_unavailable",
                    material=None,
                ),
                pending_compression=None,
                composite_text=None,
                group_status="compression_unavailable",
            )
        if composite_text:
            return _CompositeBranchResult(
                outcome=Stage08CollaborationContractFactory.read_outcome(
                    branch="composite_context",
                    status="available",
                    reason_code="none",
                    material=Stage08CollaborationContractFactory.private_material(
                        composite_text, kind="composite_context"
                    ),
                ),
                pending_compression=None,
                composite_text=composite_text,
                group_status=(
                    "direct"
                    if composite_view.group_status != "group_context_unavailable"
                    else "unavailable"
                ),
            )
    except Exception:
        pass
    return _CompositeBranchResult(
        outcome=Stage08CollaborationContractFactory.read_outcome(
            branch="composite_context",
            status="unavailable",
            reason_code="context_unavailable",
            material=None,
        ),
        pending_compression=None,
        composite_text=None,
        group_status="unavailable",
    )


def _execute_retrieval_read_branch(
    uow: Stage06PlatformUnitOfWork,
    command: object,
    actor: Actor,
    plan: object,
    group_scope_proof: _GroupScopeProof,
    provider: PostgresRetrievalProvider,
    *,
    now: datetime,
) -> _RetrievalBranchResult:
    command_snapshot = _command_snapshot(command)
    if command_snapshot.intent == "general_advice":
        return _RetrievalBranchResult(
            outcome=Stage08CollaborationContractFactory.read_outcome(
                branch="retrieval",
                status="degraded",
                reason_code="no_evidence",
                material=None,
            ),
            citation_count=0,
            source_proof=(),
        )
    try:
        if not _group_scope_proof_is_current(
            uow, command_snapshot, actor, group_scope_proof
        ):
            raise PlatformValidationError(
                "stage08_collaboration_group_scope_changed",
                "stage08_collaboration_group_scope_changed",
            )
        authority = Stage08RetrievalAuthorityFactory.build(
            uow,
            actor=actor,
            workspace_id=command_snapshot.workspace_id,
            employee_id=command_snapshot.employee_id,
            customer_record_id=plan.business_scope.customer_record_id,
            project_record_id=plan.business_scope.project_record_id,
        )
        result = provider.search(
            uow,
            authority,
            query=command_snapshot.query,
            limit=12,
            now=now,
        )
        evidence = provider.render_private_evidence(uow, result, now=now)
        retrieval_snapshot = _retrieval_result_snapshot(result)
        source_proof = (
            ()
            if retrieval_snapshot is None or evidence is None
            else tuple(
                sorted(
                    {
                        (hit.source_id, hit.source_version, hit.chunk_id)
                        for hit in retrieval_snapshot.hits
                    },
                    key=lambda value: (str(value[0]), value[1], str(value[2])),
                )
            )
        )
        safe = provider.safe_view(uow, result, now=now)
        if evidence is not None:
            return _RetrievalBranchResult(
                outcome=Stage08CollaborationContractFactory.read_outcome(
                    branch="retrieval",
                    status="available",
                    reason_code="none",
                    material=Stage08CollaborationContractFactory.private_material(
                        evidence, kind="retrieval_evidence"
                    ),
                ),
                citation_count=safe.result_count,
                source_proof=source_proof,
            )
        status = (
            "unavailable"
            if safe.status in {"unavailable", "failed"}
            else "degraded"
        )
        return _RetrievalBranchResult(
            outcome=Stage08CollaborationContractFactory.read_outcome(
                branch="retrieval",
                status=status,
                reason_code=(
                    "retrieval_unavailable" if status == "unavailable" else "no_evidence"
                ),
                material=None,
            ),
            citation_count=safe.result_count,
            source_proof=(),
        )
    except Exception:
        return _RetrievalBranchResult(
            outcome=Stage08CollaborationContractFactory.read_outcome(
                branch="retrieval",
                status="unavailable",
                reason_code="retrieval_unavailable",
                material=None,
            ),
            citation_count=0,
            source_proof=(),
        )


def _general_advice_outcome(command: object) -> object | None:
    if _command_snapshot(command).intent != "general_advice":
        return None
    return Stage08CollaborationContractFactory.read_outcome(
        branch="general_advice",
        status="available",
        reason_code="none",
        material=Stage08CollaborationContractFactory.private_material(
            "general_advice", kind="general_advice"
        ),
    )


def _compress_pending_group_context(
    read_uow_factory: object,
    state: Stage08CollaborationState,
    collector: object,
    deps: Stage08CollaborationReadDependencies,
    control: object,
    *,
    now: datetime,
) -> Stage08CollaborationState:
    collector_snapshot = _read_collector_snapshot(collector)
    with collector_snapshot.lock:
        composite = collector_snapshot.composite
    if composite is None:
        raise ValueError("stage08_collaboration_composite_missing")
    if composite.pending_compression is None:
        return state
    pending = composite.pending_compression
    accepted = False
    compression = None
    try:
        provider_started_at = _runtime_now(control)
        compressor_input = Stage08CollaborationContractFactory.provider_input(
            Stage08CollaborationContractFactory.private_material(
                pending, kind="composite_context"
            )
        )
        compression = deps.context_compressor.compress(
            compressor_input,
            budget=CollaborationBudget(),
        )
        stopped = _runtime_terminal_status(
            control, provider_started_at=provider_started_at
        )
        if stopped is not None:
            return Stage08CollaborationContractFactory.transition(
                state, status=stopped
            )
        if type(compression) is not CompressionOutcome:
            raise TypeError("compression_outcome_invalid")
        compression = CompressionOutcome.model_validate(
            compression.model_dump(mode="python")
        )
        if compression.status == "available" and compression.digest is not None:
            with _isolated_read_uow(
                read_uow_factory, control, branch="composite_context"
            ) as read_uow:
                accepted = validate_stage08_group_compression_digest(
                    read_uow,
                    pending,
                    digest=compression.digest,
                    now=now,
                )
            stopped = _runtime_terminal_status(control)
            if stopped is not None:
                return Stage08CollaborationContractFactory.transition(
                    state, status=stopped
                )
    except Exception:
        accepted = False
    if accepted and compression is not None:
        outcome = Stage08CollaborationContractFactory.read_outcome(
            branch="composite_context",
            status="available",
            reason_code="none",
            material=Stage08CollaborationContractFactory.private_material(
                (composite.composite_text or "", compression.digest),
                kind="analysis_material",
            ),
        )
        state = Stage08CollaborationContractFactory.record_compressed_digest(
            state, compression.digest
        )
        group_status = "compressed"
    else:
        outcome = Stage08CollaborationContractFactory.read_outcome(
            branch="composite_context",
            status="degraded",
            reason_code="compression_unavailable",
            material=(
                None
                if not composite.composite_text
                else Stage08CollaborationContractFactory.private_material(
                    composite.composite_text, kind="composite_context"
                )
            ),
        )
        group_status = "compression_unavailable"
    _collector_replace_composite(
        collector,
        _CompositeBranchResult(
            outcome=outcome,
            pending_compression=None,
            composite_text=composite.composite_text,
            group_status=group_status,
        ),
    )
    return Stage08CollaborationContractFactory.record_read_outcome(state, outcome)


def _read_result_from_collector(
    state: Stage08CollaborationState,
    collector: object,
) -> Stage08CollaborationReadResult:
    collector_snapshot = _read_collector_snapshot(collector)
    with collector_snapshot.lock:
        plan = collector_snapshot.plan
        proof = collector_snapshot.group_scope_proof
        composite = collector_snapshot.composite
        retrieval = collector_snapshot.retrieval
    if plan is None or proof is None or composite is None or retrieval is None:
        raise ValueError("stage08_collaboration_read_result_incomplete")
    state_snapshot = _state_snapshot(state)
    reads = tuple(_read_outcome_snapshot(item) for item in state_snapshot.read_outcomes)
    has_internal_material = any(
        read.branch in {"composite_context", "retrieval"}
        and read.material is not None
        for read in reads
    )
    has_general_advice = any(
        read.branch == "general_advice"
        and read.status == "available"
        and read.material is not None
        for read in reads
    )
    command_snapshot = _command_snapshot(state_snapshot.command)
    degradation_codes = tuple(
        dict.fromkeys(
            read.reason_code
            for read in reads
            if read.reason_code
            in {
                "context_unavailable",
                "retrieval_unavailable",
                "compression_unavailable",
                "no_evidence",
            }
            and not (
                command_snapshot.intent == "general_advice"
                and read.branch == "retrieval"
                and read.reason_code == "no_evidence"
            )
        )
    )
    status = (
        "internal_evidence"
        if has_internal_material
        else "general_advice_only"
        if has_general_advice
        else "degraded"
        if degradation_codes
        else "no_evidence"
    )
    if status == "no_evidence" and not degradation_codes:
        degradation_codes = ("no_evidence",)
    view = CollaborationReadSafeView(
        status=status,
        read_child_count=len(reads),
        retrieval_citation_count=retrieval.citation_count,
        group_status=composite.group_status,
        degradation_codes=degradation_codes,
    )
    return Stage08CollaborationReadResult(
        _READ_RESULT_ISSUER,
        _ReadResultSnapshot(
            seal=_READ_RESULT_SEAL,
            state=state,
            view=view,
            plan=plan,
            group_scope_proof=proof,
            retrieval_source_proof=retrieval.source_proof,
        ),
    )


def run_stage08_collaboration(
    uow: Stage06PlatformUnitOfWork,
    command: object,
    actor: Actor,
    deps: Stage08CollaborationDependencies = Stage08CollaborationDependencies(),
    *,
    now: datetime,
    runtime_control: Stage08CollaborationRuntimeControl | None = None,
) -> AssistantQuerySafeView:
    """Run the bounded production graph without persisting private runtime state."""

    started_at = now
    started_monotonic = monotonic()
    trace_hash = _trace_hash(command)
    try:
        if not _valid_collaboration_dependencies(deps):
            raise TypeError("collaboration_dependencies_invalid")
        control = (
            create_stage08_runtime_control()
            if runtime_control is None
            else runtime_control
        )
        _runtime_control_snapshot(control)
        read_uow_factory = _create_stage08_read_uow_factory(uow)
        from app.agents.stage08_collaboration import (
            Stage08CollaborationNodes,
            build_stage08_collaboration_graph,
        )

        collector = _new_read_collector()
        read_result: Stage08CollaborationReadResult | None = None

        def plan_request(state: Stage08CollaborationState) -> Stage08CollaborationState:
            stopped = _runtime_terminal_status(control)
            if stopped is not None:
                return Stage08CollaborationContractFactory.transition(
                    state, status=stopped
                )
            state = Stage08CollaborationContractFactory.transition(
                state, status="planning"
            )
            command_snapshot = _command_snapshot(command)
            if not _valid_actor(actor, command_snapshot.actor_user_id):
                return Stage08CollaborationContractFactory.transition(
                    state, status="failed"
                )
            try:
                plan, proof = _build_current_plan(uow, command_snapshot, actor)
                _collector_record_plan(
                    collector,
                    plan=plan,
                    group_scope_proof=proof,
                )
            except (PlatformValidationError, TypeError, ValueError, AttributeError):
                return Stage08CollaborationContractFactory.transition(
                    state, status="failed"
                )
            stopped = _runtime_terminal_status(control)
            return (
                state
                if stopped is None
                else Stage08CollaborationContractFactory.transition(
                    state, status=stopped
                )
            )

        def read_composite_context(
            state: Stage08CollaborationState,
        ) -> Stage08CollaborationState:
            state = Stage08CollaborationContractFactory.transition(
                state, status="reading"
            )
            if _runtime_terminal_status(control) is not None:
                return state
            plan, _ = _collector_plan(collector)
            with _isolated_read_uow(
                read_uow_factory, control, branch="composite_context"
            ) as read_uow:
                branch_result = _execute_composite_read_branch(
                    read_uow,
                    plan,
                    actor,
                    now=now,
                )
            _collector_record_composite(collector, branch_result)
            _runtime_terminal_status(control)
            if branch_result.outcome is None:
                return state
            return Stage08CollaborationContractFactory.record_read_outcome(
                state, branch_result.outcome
            )

        def read_retrieval(
            state: Stage08CollaborationState,
        ) -> Stage08CollaborationState:
            state = Stage08CollaborationContractFactory.transition(
                state, status="reading"
            )
            if _runtime_terminal_status(control) is not None:
                return state
            plan, proof = _collector_plan(collector)
            with _isolated_read_uow(
                read_uow_factory, control, branch="retrieval"
            ) as read_uow:
                branch_result = _execute_retrieval_read_branch(
                    read_uow,
                    command,
                    actor,
                    plan,
                    proof,
                    deps.read_dependencies.retrieval_provider,
                    now=now,
                )
            _collector_record_retrieval(collector, branch_result)
            _runtime_terminal_status(control)
            return Stage08CollaborationContractFactory.record_read_outcome(
                state, branch_result.outcome
            )

        def mark_general_advice(
            state: Stage08CollaborationState,
        ) -> Stage08CollaborationState:
            state = Stage08CollaborationContractFactory.transition(
                state, status="reading"
            )
            if _runtime_terminal_status(control) is not None:
                return state
            _notify_branch_started(
                control,
                branch="general_advice",
                session_identity=None,
            )
            outcome = _general_advice_outcome(command)
            _runtime_terminal_status(control)
            if outcome is None:
                return state
            return Stage08CollaborationContractFactory.record_read_outcome(
                state, outcome
            )

        def fan_in(state: Stage08CollaborationState) -> Stage08CollaborationState:
            stopped = _runtime_terminal_status(control)
            return (
                state
                if stopped is None
                else Stage08CollaborationContractFactory.transition(
                    state, status=stopped
                )
            )

        def compress_group_context(
            state: Stage08CollaborationState,
        ) -> Stage08CollaborationState:
            nonlocal read_result
            stopped = _runtime_terminal_status(control)
            if stopped is not None:
                return Stage08CollaborationContractFactory.transition(
                    state, status=stopped
                )
            state = _compress_pending_group_context(
                read_uow_factory,
                state,
                collector,
                deps.read_dependencies,
                control,
                now=now,
            )
            if Stage08CollaborationContractFactory.terminal_status(state) is None:
                stopped = _runtime_terminal_status(control)
                if stopped is not None:
                    return Stage08CollaborationContractFactory.transition(
                        state, status=stopped
                    )
                read_result = _read_result_from_collector(state, collector)
            return state

        def analyse(state: Stage08CollaborationState) -> Stage08CollaborationState:
            return _analyse_state(
                state,
                command,
                deps.analysis_provider,
                runtime_control=control,
            )

        def policy_gate(state: Stage08CollaborationState) -> Stage08CollaborationState:
            return _policy_gate_state(
                uow,
                state,
                actor,
                runtime_control=control,
            )

        def materialize_draft(state: Stage08CollaborationState) -> Stage08CollaborationState:
            return _materialize_draft_state(
                uow,
                state,
                actor,
                deps.tool_gateway,
                trace_hash=trace_hash,
                read_result=read_result,
                runtime_control=control,
            )

        def finalize(state: Stage08CollaborationState) -> Stage08CollaborationState:
            if Stage08CollaborationContractFactory.terminal_status(state) is None:
                stopped = _runtime_terminal_status(control)
                if stopped is not None:
                    state = Stage08CollaborationContractFactory.transition(
                        state, status=stopped
                    )
            return _finalize_state(state, read_result)

        graph = build_stage08_collaboration_graph(
            Stage08CollaborationNodes(
                plan_request=plan_request,
                read_composite_context=read_composite_context,
                read_retrieval=read_retrieval,
                mark_general_advice=mark_general_advice,
                fan_in=fan_in,
                compress_group_context=compress_group_context,
                analyse=analyse,
                policy_gate=policy_gate,
                materialize_draft=materialize_draft,
                finalize=finalize,
            )
        )
        state = graph.invoke(Stage08CollaborationContractFactory.initial_state(command))
        view = _state_snapshot(state).safe_view
        if view is None:
            raise RuntimeError("collaboration_safe_view_missing")
    except Exception:
        view = AssistantQuerySafeView(
            status="failed",
            answer=None,
            citations=(),
            degradation_codes=("internal_failure",),
            draft_id=None,
        )
    skill_summary = Stage08CollaborationContractFactory.safe_skill_summary(command)
    if skill_summary is not None:
        view = view.model_copy(update={"skill": skill_summary})
    _record_terminal_run(
        uow,
        command=command,
        view=view,
        started_at=started_at,
        trace_hash=trace_hash,
        latency_ms=max(0, int((monotonic() - started_monotonic) * 1000)),
    )
    return view


def _analyse_state(
    state: Stage08CollaborationState,
    command: object,
    provider: AnalysisProvider,
    *,
    runtime_control: Stage08CollaborationRuntimeControl | None = None,
) -> Stage08CollaborationState:
    if runtime_control is not None:
        stopped = _runtime_terminal_status(runtime_control)
        if stopped is not None:
            return Stage08CollaborationContractFactory.transition(
                state, status=stopped
            )
    state = Stage08CollaborationContractFactory.transition(state, status="analysing")
    snapshot = _state_snapshot(state)
    material = Stage08CollaborationContractFactory.private_material(
        tuple(
            _read_outcome_snapshot(outcome).material
            for outcome in snapshot.read_outcomes
            if _read_outcome_snapshot(outcome).material is not None
        ),
        kind="analysis_material",
    )
    try:
        provider_started_at = (
            None if runtime_control is None else _runtime_now(runtime_control)
        )
        outcome = provider.analyse(
            Stage08CollaborationContractFactory.provider_input(material),
            command,
            budget=snapshot.budget,
        )
        if runtime_control is not None:
            stopped = _runtime_terminal_status(
                runtime_control,
                provider_started_at=provider_started_at,
            )
            if stopped is not None:
                return Stage08CollaborationContractFactory.transition(
                    state, status=stopped
                )
        if (
            type(outcome) is not AnalysisProviderOutcome
            or set(object.__getattribute__(outcome, "__dict__"))
            != set(AnalysisProviderOutcome.model_fields)
        ):
            raise TypeError("analysis_outcome_invalid")
        outcome = AnalysisProviderOutcome.model_validate(
            outcome.model_dump(mode="python")
        )
        if outcome.status == "unavailable":
            return Stage08CollaborationContractFactory.transition(
                state, status="degraded"
            )
        if outcome.decision is None:
            return Stage08CollaborationContractFactory.transition(state, status="failed")
        if outcome.reason_code != "none":
            raise ValueError("analysis_outcome_invalid")
        decision = validate_analysis_decision(outcome.decision)
        if not _decision_citations_are_current(decision, state):
            return Stage08CollaborationContractFactory.transition(state, status="denied")
        return Stage08CollaborationContractFactory.record_analysis(state, decision)
    except Exception:
        return Stage08CollaborationContractFactory.transition(state, status="failed")


def _policy_gate_state(
    uow: Stage06PlatformUnitOfWork,
    state: Stage08CollaborationState,
    actor: Actor,
    *,
    runtime_control: Stage08CollaborationRuntimeControl | None = None,
) -> Stage08CollaborationState:
    if Stage08CollaborationContractFactory.terminal_status(state) is not None:
        return state
    if runtime_control is not None:
        stopped = _runtime_terminal_status(runtime_control)
        if stopped is not None:
            return Stage08CollaborationContractFactory.transition(
                state, status=stopped
            )
    state = Stage08CollaborationContractFactory.transition(state, status="policy_check")
    snapshot = _state_snapshot(state)
    command_carrier = snapshot.command
    command = _command_snapshot(command_carrier)
    decision = snapshot.analysis_decision
    if decision is None:
        return Stage08CollaborationContractFactory.transition(state, status="failed")
    if command.requested_action == "draft_update":
        if decision.action != "draft_update" or decision.draft_intent is None:
            return Stage08CollaborationContractFactory.transition(state, status="denied")
        if not _draft_scope_is_current(uow, command_carrier, actor):
            return Stage08CollaborationContractFactory.transition(state, status="denied")
        if runtime_control is not None:
            stopped = _runtime_terminal_status(runtime_control)
            if stopped is not None:
                return Stage08CollaborationContractFactory.transition(
                    state, status=stopped
                )
        return Stage08CollaborationContractFactory.record_policy_result(
            state, draft_allowed=True
        )
    if decision.action == "draft_update":
        return Stage08CollaborationContractFactory.transition(state, status="denied")
    return Stage08CollaborationContractFactory.record_policy_result(state, draft_allowed=False)


def _materialize_draft_state(
    uow: Stage06PlatformUnitOfWork,
    state: Stage08CollaborationState,
    actor: Actor,
    gateway: Stage08ToolGateway,
    *,
    trace_hash: str,
    read_result: Stage08CollaborationReadResult | None,
    runtime_control: Stage08CollaborationRuntimeControl | None = None,
) -> Stage08CollaborationState:
    if runtime_control is not None:
        stopped = _runtime_terminal_status(runtime_control)
        if stopped is not None:
            return Stage08CollaborationContractFactory.transition(
                state, status=stopped
            )
    snapshot = _state_snapshot(state)
    command_carrier = snapshot.command
    command = _command_snapshot(command_carrier)
    decision = snapshot.analysis_decision
    if decision is None or decision.draft_intent is None or read_result is None:
        return Stage08CollaborationContractFactory.transition(state, status="denied")
    intent = _draft_intent_snapshot(decision.draft_intent)
    safe_context = Stage08CollaborationContractFactory.safe_execution_context(
        trace_hash=trace_hash
    )
    plan = ExecutionPlan(
        ticket_id="stage08-collaboration",
        workspace_id=str(command.workspace_id),
        employee_id=str(command.employee_id),
        actor=f"user:{command.actor_user_id}",
        action="record_change_draft.create",
        trace_id=trace_hash,
        idempotency_key=command.idempotency_key,
        state=ExecutionTicketState.planned,
        budget=ExecutionBudget(
            max_tool_calls=1,
            max_wall_time_ms=30_000,
            max_graph_depth=3,
            max_retries=0,
            max_retrieval_chunks=0,
        ),
        invocations=[
            ToolInvocation(
                tool_name="record_change_draft.create",
                input={
                    "record_id": str(command.target_record_id),
                    "proposed_values": {intent.field_key: intent.value},
                },
            )
        ],
    )
    try:
        with stage08_e3_safe_execution_boundary(uow):
            _raise_if_runtime_stopped(runtime_control)
            _lock_and_revalidate_draft_scope(
                uow,
                command_carrier,
                actor,
                intent_field_key=intent.field_key,
                read_snapshot=_read_result_snapshot(read_result),
            )
            _raise_if_runtime_stopped(runtime_control)
            replay_draft_id = _safe_replay_draft_id(
                uow,
                command=command,
                actor=actor,
                trace_hash=trace_hash,
                proposed_values={intent.field_key: intent.value},
            )
            if replay_draft_id is None:
                _raise_if_runtime_stopped(runtime_control)
                ticket = begin_execution_plan(
                    uow,
                    plan,
                    safe_context=safe_context,
                )
                _raise_if_runtime_stopped(runtime_control)
                ticket = gateway.execute_plan(
                    uow,
                    ticket,
                    plan.invocations,
                    safe_context=safe_context,
                )
                _raise_if_runtime_stopped(runtime_control)
                if ticket.status != ExecutionTicketState.succeeded.value:
                    if ticket.status == ExecutionTicketState.denied.value:
                        raise _SafeDraftDenied
                    raise _SafeDraftFailed
                draft = uow.get_pending_record_change_draft_by_trace(trace_hash)
                if (
                    draft is None
                    or draft.record_id != command.target_record_id
                    or draft.created_by_id != str(command.employee_id)
                    or draft.proposed_values != {intent.field_key: intent.value}
                ):
                    raise _SafeDraftFailed
                replay_draft_id = draft.id
            _raise_if_runtime_stopped(runtime_control)
            safe = AssistantQuerySafeView(
                status="draft_pending",
                answer=None,
                citations=_safe_citations(snapshot.analysis_decision, state),
                degradation_codes=(),
                draft_id=replay_draft_id,
            )
            next_state = Stage08CollaborationContractFactory.record_safe_view(
                Stage08CollaborationContractFactory.transition(
                    state, status="draft_pending"
                ),
                safe,
            )
            _raise_if_runtime_stopped(runtime_control)
        return next_state
    except _CoordinatorStopped as stopped:
        return Stage08CollaborationContractFactory.transition(
            state, status=stopped.status
        )
    except _SafeDraftDenied:
        return Stage08CollaborationContractFactory.transition(state, status="denied")
    except Exception:
        return Stage08CollaborationContractFactory.transition(state, status="failed")


class _SafeDraftDenied(Exception):
    pass


class _SafeDraftFailed(Exception):
    pass


class _CoordinatorStopped(Exception):
    def __init__(self, status: Literal["cancelled", "timed_out"]) -> None:
        super().__init__("stage08_collaboration_stopped")
        self.status = status


def _raise_if_runtime_stopped(
    runtime_control: Stage08CollaborationRuntimeControl | None,
) -> None:
    if runtime_control is None:
        return
    stopped = _runtime_terminal_status(runtime_control)
    if stopped is not None:
        raise _CoordinatorStopped(stopped)


def _lock_and_revalidate_draft_scope(
    uow: Stage06PlatformUnitOfWork,
    command: object,
    actor: Actor,
    *,
    intent_field_key: str,
    read_snapshot: _ReadResultSnapshot,
) -> None:
    snapshot = _command_snapshot(command)
    workspace = uow.lock_workspace_for_stage08_execution(snapshot.workspace_id)
    members = sorted(
        (
            member
            for member in uow.list_workspace_members(snapshot.workspace_id)
            if member.user_id == actor.actor_id and member.status == "active"
        ),
        key=lambda member: str(member.id),
    )
    if workspace is None or workspace.status != "active" or len(members) != 1:
        raise _SafeDraftDenied
    member = uow.lock_workspace_member_for_mutation(members[0].id)
    employee = uow.lock_digital_employee_for_management(snapshot.employee_id)
    uow.lock_digital_employee_member_grants_for_stage08_execution(
        snapshot.employee_id
    )
    record = uow.lock_record_for_stage08_execution(snapshot.target_record_id)
    if (
        member is None
        or member.status != "active"
        or member.workspace_id != snapshot.workspace_id
        or member.user_id != actor.actor_id
        or employee is None
        or employee.workspace_id != snapshot.workspace_id
        or employee.status != "active"
        or "draft_update" not in set(employee.allowed_actions)
        or record is None
        or record.record_status != "active"
    ):
        raise _SafeDraftDenied
    table = uow.lock_table_for_stage08_execution(record.table_id)
    if (
        table is None
        or table.status != "active"
        or str(table.id) not in set(employee.accessible_tables)
    ):
        raise _SafeDraftDenied
    fields = [
        field
        for field in uow.list_fields(table.id)
        if field.key == intent_field_key and field.status == "active"
    ]
    if len(fields) != 1:
        raise _SafeDraftDenied
    field = uow.lock_field_for_mutation(fields[0].id)
    if (
        field is None
        or field.status != "active"
        or field.table_id != table.id
        or field.key != intent_field_key
        or not can_actor_write_record_fields(
            uow,
            table.id,
            (intent_field_key,),
            actor=actor,
        )
        or not _employee_field_is_current(
            uow,
            employee,
            table_id=table.id,
            field_key=intent_field_key,
        )
    ):
        raise _SafeDraftDenied

    proof = read_snapshot.group_scope_proof
    if proof is not None and proof.binding_id is not None:
        binding = uow.lock_telegram_binding_for_stage08_execution(proof.binding_id)
        mapping = (
            None
            if proof.mapping_id is None
            else uow.lock_group_business_context_binding_for_lifecycle(
                proof.mapping_id
            )
        )
        if (
            binding is None
            or binding.status != "active"
            or binding.workspace_id != snapshot.workspace_id
            or binding.workspace_member_id != member.id
            or mapping is None
            or mapping.status != "active"
            or mapping.workspace_id != snapshot.workspace_id
            or mapping.telegram_binding_id != binding.id
            or mapping.mapping_version != proof.mapping_version
            or mapping.customer_record_id != proof.customer_record_id
            or mapping.project_record_id != proof.project_record_id
        ):
            raise _SafeDraftDenied

    for source_id, source_version, chunk_id in read_snapshot.retrieval_source_proof:
        source = uow.lock_knowledge_source_for_lifecycle(source_id)
        chunks = (
            []
            if source is None
            else uow.list_knowledge_chunks(source.id, source.content_version)
        )
        chunk = next((candidate for candidate in chunks if candidate.id == chunk_id), None)
        if (
            source is None
            or source.workspace_id != snapshot.workspace_id
            or source.status != "active"
            or source.content_version != source_version
            or source.deleted_at is not None
            or chunk is None
            or chunk.status != "indexed"
            or chunk.deleted_at is not None
            or chunk.source_version != source_version
        ):
            raise _SafeDraftDenied

    try:
        current_plan, current_group_proof = _build_current_plan(uow, snapshot, actor)
    except (PlatformValidationError, TypeError, ValueError, AttributeError) as exc:
        raise _SafeDraftDenied from exc
    if (
        read_snapshot.plan is None
        or current_plan != read_snapshot.plan
        or current_group_proof != read_snapshot.group_scope_proof
    ):
        raise _SafeDraftDenied


def _employee_field_is_current(
    uow: Stage06PlatformUnitOfWork,
    employee: object,
    *,
    table_id: UUID,
    field_key: str,
) -> bool:
    try:
        view_ids = tuple(sorted(UUID(value) for value in employee.accessible_views))
    except (TypeError, ValueError, AttributeError):
        return False
    for view_id in view_ids:
        view = uow.get_view(view_id)
        if view is None or view.status != "active" or view.table_id != table_id:
            continue
        fields = view.config.get("fields") if isinstance(view.config, dict) else None
        if isinstance(fields, list) and field_key in fields:
            return True
    return False


def _safe_replay_draft_id(
    uow: Stage06PlatformUnitOfWork,
    *,
    command: object,
    actor: Actor,
    trace_hash: str,
    proposed_values: dict[str, object],
) -> UUID | None:
    ticket = uow.get_execution_ticket_by_trace(command.workspace_id, trace_hash)
    if ticket is None:
        return None
    draft = uow.get_pending_record_change_draft_by_trace(trace_hash)
    safe_ticket_audit = any(
        event.trace_id == trace_hash
        and event.event_type == "stage08.execution_ticket_created"
        and event.entity_type == "stage08_safe_execution"
        and event.entity_id is None
        for event in uow.list_audit_events()
    )
    if (
        ticket.workspace_id != command.workspace_id
        or ticket.employee_id != command.employee_id
        or ticket.actor_id != f"user:{actor.actor_id}"
        or ticket.action != "record_change_draft.create"
        or ticket.status != ExecutionTicketState.succeeded.value
        or draft is None
        or draft.record_id != command.target_record_id
        or draft.created_by_id != str(command.employee_id)
        or draft.proposed_values != proposed_values
        or not safe_ticket_audit
    ):
        raise _SafeDraftDenied
    return draft.id


def _finalize_state(
    state: Stage08CollaborationState,
    read_result: Stage08CollaborationReadResult | None,
) -> Stage08CollaborationState:
    snapshot = _state_snapshot(state)
    if snapshot.safe_view is not None:
        return state
    terminal = snapshot.status
    decision = snapshot.analysis_decision
    if terminal == "denied":
        view = AssistantQuerySafeView(status="denied", answer=None, citations=(), degradation_codes=("policy_denied",))
    elif terminal == "degraded":
        view = AssistantQuerySafeView(
            status="degraded",
            answer=None,
            citations=(),
            degradation_codes=("analysis_unavailable",),
            draft_id=None,
        )
    elif terminal in {"failed", "timed_out", "cancelled"}:
        code = "analysis_unavailable" if terminal == "failed" else terminal
        view = AssistantQuerySafeView(status="failed" if terminal == "failed" else terminal, answer=None, citations=(), degradation_codes=(code,))
    elif decision is None:
        view = AssistantQuerySafeView(status="failed", answer=None, citations=(), degradation_codes=("analysis_unavailable",))
        state = Stage08CollaborationContractFactory.transition(state, status="failed")
    else:
        view = AssistantQuerySafeView(
            status="completed",
            answer=decision.answer,
            citations=_safe_citations(decision, state),
            degradation_codes=(),
        )
        state = Stage08CollaborationContractFactory.transition(state, status="completed")
    del read_result
    return Stage08CollaborationContractFactory.record_safe_view(state, view)


def _decision_citations_are_current(
    decision: AnalysisDecision,
    state: Stage08CollaborationState,
) -> bool:
    return set(decision.citation_ordinals).issubset(
        {citation.ordinal for citation in _safe_citations(decision, state)}
    )


def _safe_citations(
    decision: AnalysisDecision | None,
    state: Stage08CollaborationState,
) -> tuple[AssistantQuerySafeCitation, ...]:
    if decision is None:
        return ()
    snapshot = _state_snapshot(state)
    labels: list[str] = []
    for outcome in snapshot.read_outcomes:
        read = _read_outcome_snapshot(outcome)
        if read.status != "available" or read.material is None:
            continue
        if read.branch == "general_advice":
            labels.append("general_advice")
        elif read.branch == "composite_context":
            labels.append("analysis_from_current_material")
        elif read.branch == "retrieval":
            # E2 exposes only a count, never the per-item evidence identity.
            # One aggregate safe ordinal is therefore the strictest valid label.
            labels.append("retrieved_material")
    available = {
        index: label for index, label in enumerate(labels[:12], start=1)
    }
    return tuple(
        AssistantQuerySafeCitation(ordinal=ordinal, label=available[ordinal])
        for ordinal in decision.citation_ordinals
        if ordinal in available
    )


def _draft_scope_is_current(
    uow: Stage06PlatformUnitOfWork,
    command: object,
    actor: Actor,
) -> bool:
    try:
        snapshot = _command_snapshot(command)
        if not _valid_actor(actor, snapshot.actor_user_id):
            return False
        members = [
            member
            for member in uow.list_workspace_members(snapshot.workspace_id)
            if member.user_id == actor.actor_id and member.status == "active"
        ]
        employee = uow.get_digital_employee(snapshot.employee_id)
        record = uow.get_record(snapshot.target_record_id)
        table = uow.get_table(record.table_id) if record is not None else None
        if (
            len(members) != 1
            or employee is None
            or employee.status != "active"
            or employee.workspace_id != snapshot.workspace_id
            or "draft_update" not in set(employee.allowed_actions)
            or record is None
            or table is None
            or str(table.id) not in set(employee.accessible_tables)
        ):
            return False
        # Rebuilds current C1/C2/C3/D4 scope before ticket creation. A revoked
        # member, binding, mapping, source or target scope therefore fails closed.
        _build_current_plan(uow, snapshot, actor)
        return True
    except (PlatformValidationError, TypeError, ValueError, AttributeError):
        return False


def _trace_hash(command: object) -> str:
    try:
        snapshot = _command_snapshot(command)
        payload = "\x1f".join(
            (
                str(snapshot.workspace_id),
                str(snapshot.employee_id),
                snapshot.actor_user_id,
                snapshot.idempotency_key,
                snapshot.query,
            )
        )
    except (TypeError, AttributeError):
        payload = "invalid"
    return "stage08:collaboration:" + hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()[:32]


def _record_terminal_run(
    uow: Stage06PlatformUnitOfWork,
    *,
    command: object,
    view: AssistantQuerySafeView,
    started_at: datetime,
    trace_hash: str,
    latency_ms: int,
) -> None:
    try:
        command_snapshot = _command_snapshot(command)
        action = command_snapshot.requested_action
        skill_profile = command_snapshot.skill_profile
    except (TypeError, AttributeError):
        action = "invalid"
        skill_profile = None
    skill_metadata = (
        {}
        if skill_profile is None
        else {
            "skill_manifest_version": skill_profile.manifest_version,
            "primary_skill_id": skill_profile.primary_skill_id,
            "skill_selection_mode": skill_profile.selection_mode,
            "supporting_skill_ids": list(skill_profile.supporting_skill_ids),
        }
    )
    safe_summary = {
        "graph": "stage08_collaboration_e3",
        "status": view.status,
        "citation_count": len(view.citations),
        "degradation_count": len(view.degradation_codes),
        "action": action,
        "ticket_present": int(view.status == "draft_pending"),
        "draft_present": int(view.draft_id is not None),
        "trace_hash": trace_hash,
        "latency_ms": latency_ms,
        **skill_metadata,
    }
    uow.add_agent_run(
        AgentRun(
            agent_name="stage08_collaboration",
            graph_name="stage08_collaboration_e3",
            model_provider="controlled",
            model_name="analysis_provider_port",
            prompt_version="stage08-e3",
            input_summary={
                "graph": "stage08_collaboration_e3",
                "action": action,
                **skill_metadata,
            },
            output_summary=safe_summary,
            tool_calls=[{"name": "policy_gate", "status": view.status}],
            status=view.status,
            trace_id=trace_hash,
            started_at=started_at,
            completed_at=datetime.now(started_at.tzinfo),
            usage_summary={"provider_calls": 0},
            cost_summary={"provider_cost": 0},
            latency_ms=latency_ms,
            created_entity_refs=[],
            redaction_policy="stage08_e3_whitelist",
        )
    )
    record_audit_event(
        getattr(uow, "session", uow),
        trace_id=trace_hash,
        actor_type="system",
        actor_id="stage08_e3_safe",
        event_type="stage08.collaboration_terminal",
        entity_type="stage08_collaboration",
        after_state=safe_summary,
        permission_snapshot=None,
    )


def _valid_collaboration_dependencies(value: object) -> bool:
    return (
        type(value) is Stage08CollaborationDependencies
        and _valid_dependencies(value.read_dependencies)
        and hasattr(value.analysis_provider, "analyse")
        and isinstance(value.tool_gateway, Stage08ToolGateway)
    )


def _build_current_plan(
    uow: Stage06PlatformUnitOfWork,
    snapshot: object,
    actor: Actor,
):
    employee = uow.get_digital_employee(snapshot.employee_id)
    if employee is None or employee.workspace_id != snapshot.workspace_id:
        raise PlatformValidationError("context_authority_denied", "context_authority_denied")
    views = tuple(sorted(UUID(value) for value in employee.accessible_views))[:3]
    if snapshot.intent == "general_advice":
        views = ()
        customer_id = None
        project_id = None
        group_scope_proof = _GroupScopeProof(
            binding_id=None,
            mapping_id=None,
            mapping_version=None,
            customer_record_id=None,
            project_record_id=None,
        )
    else:
        customer_id, project_id, group_scope_proof = _derive_business_scope_ids(
            uow, snapshot, actor
        )
    plan = build_context_plan(
        uow,
        ContextPlanningRequest(
            workspace_id=snapshot.workspace_id,
            employee_id=snapshot.employee_id,
            intent=snapshot.intent,
            view_ids=views if snapshot.intent in {"business_fact", "mixed"} else (),
            customer_record_id=customer_id,
            project_record_id=project_id,
            allow_general_advice=snapshot.intent == "general_advice",
            budget=ContextBudget(
                max_table_records=20,
                max_memory_items=12,
                max_evidence_items=24,
                max_item_chars=2000,
                max_total_chars=12000,
            ),
        ),
        actor=actor,
    )
    return plan, group_scope_proof


def _derive_business_scope_ids(
    uow: Stage06PlatformUnitOfWork,
    snapshot: object,
    actor: Actor,
) -> tuple[UUID | None, UUID | None, _GroupScopeProof]:
    members = [
        member
        for member in uow.list_workspace_members(snapshot.workspace_id)
        if member.user_id == actor.actor_id and member.status == "active"
    ]
    if len(members) == 1:
        bindings = [
            binding
            for binding in uow.list_telegram_bindings()
            if binding.workspace_id == snapshot.workspace_id
            and binding.workspace_member_id == members[0].id
            and binding.status == "active"
            and binding.binding_type == "chat_user"
        ]
        if len(bindings) == 1:
            mappings = [
                mapping
                for mapping in uow.list_group_business_context_bindings(bindings[0].id)
                if mapping.workspace_id == snapshot.workspace_id and mapping.status == "active"
            ]
            if len(mappings) == 1 and snapshot.target_record_id in {
                None,
                mappings[0].customer_record_id,
                mappings[0].project_record_id,
            }:
                mapping = mappings[0]
                return (
                    mapping.customer_record_id,
                    mapping.project_record_id,
                    _GroupScopeProof(
                        binding_id=bindings[0].id,
                        mapping_id=mapping.id,
                        mapping_version=mapping.mapping_version,
                        customer_record_id=mapping.customer_record_id,
                        project_record_id=mapping.project_record_id,
                    ),
                )
    if snapshot.target_record_id is not None:
        raise PlatformValidationError(
            "stage08_collaboration_target_scope_denied",
            "stage08_collaboration_target_scope_denied",
        )
    return None, None, _GroupScopeProof(
        binding_id=None,
        mapping_id=None,
        mapping_version=None,
        customer_record_id=None,
        project_record_id=None,
    )


def _group_scope_proof_is_current(
    uow: Stage06PlatformUnitOfWork,
    snapshot: object,
    actor: Actor,
    proof: _GroupScopeProof,
) -> bool:
    try:
        _, _, current = _derive_business_scope_ids(uow, snapshot, actor)
    except (PlatformValidationError, TypeError, ValueError, AttributeError):
        return False
    return current == proof


def _valid_actor(actor: object, actor_user_id: str) -> bool:
    return (
        type(actor) is Actor
        and actor.actor_type == "user"
        and actor.actor_id == actor_user_id
        and type(actor.role) is str
    )


def _valid_dependencies(value: object) -> bool:
    return (
        type(value) is Stage08CollaborationReadDependencies
        and hasattr(value.context_compressor, "compress")
        and isinstance(value.retrieval_provider, PostgresRetrievalProvider)
    )


def _result_for_invalid_command(command: object) -> Stage08CollaborationReadResult:
    state = Stage08CollaborationContractFactory.initial_state(command)
    view = CollaborationReadSafeView(
        status="degraded",
        read_child_count=0,
        retrieval_citation_count=0,
        group_status="unavailable",
        degradation_codes=("context_unavailable",),
    )
    return Stage08CollaborationReadResult(
        _READ_RESULT_ISSUER,
        _ReadResultSnapshot(
            seal=_READ_RESULT_SEAL,
            state=state,
            view=view,
            plan=None,
            group_scope_proof=None,
            retrieval_source_proof=(),
        ),
    )


def _read_result_snapshot(value: object) -> _ReadResultSnapshot:
    if type(value) is not Stage08CollaborationReadResult:
        raise TypeError("stage08_collaboration_read_result_private")
    snapshot = object.__getattribute__(value, "_sealed_snapshot")
    if (
        type(snapshot) is not _ReadResultSnapshot
        or snapshot.seal is not _READ_RESULT_SEAL
    ):
        raise TypeError("stage08_collaboration_read_result_private")
    _state_snapshot(snapshot.state)
    return snapshot


__all__ = [
    "CollaborationReadSafeView",
    "Stage08CollaborationDependencies",
    "Stage08CollaborationReadDependencies",
    "Stage08CollaborationReadResult",
    "execute_collaboration_reads",
    "run_stage08_collaboration",
]
