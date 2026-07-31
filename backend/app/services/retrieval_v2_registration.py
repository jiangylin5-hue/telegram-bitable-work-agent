"""Durable authorized-projection registrations for Retrieval V2."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from app.models.outbox import OutboxEvent
from app.models.stage12_retrieval import (
    Stage12RelationEdge,
    Stage12RetrievalScopeRegistration,
)
from app.schemas.retrieval_v2 import canonical_retrieval_sha256
from app.services.agent_field_policy_v2 import (
    Stage12FieldPolicyError,
    parse_stage12_field_policy_v2,
)
from app.services.agent_schema_binding import (
    build_authorized_relation_catalog,
    build_authorized_schema_snapshot,
)
from app.services.authorized_query_records import (
    AuthorizedQueryContext,
    AuthorizedQueryDenied,
    build_authorized_query_context,
    scan_authorized_records,
)
from app.services.permissions import Actor
from app.services.retrieval_v2_indexing import (
    RetrievalIndexUnitOfWork,
    request_retrieval_projection,
    request_retrieval_scope_bootstrap,
    revoke_retrieval_source,
)
from app.services.retrieval_v2_projection import (
    build_record_field_projections,
    build_record_projection,
    build_relation_projections,
    build_schema_projections,
)
from app.services.retrieval_v2_scope import effective_retrieval_scope_hash
from app.services.stage06_platform import (
    PlatformValidationError,
    Stage06PlatformUnitOfWork,
)


_REGISTRATION_TTL = timedelta(minutes=15)
_MAX_REGISTRATIONS_PER_WORKSPACE = 256
_MAX_RELATION_EDGES_PER_REGISTRATION = 512
_BOOTSTRAP_EVENT = "stage12.retrieval_scope.bootstrap_requested"
_BOOTSTRAP_PAGE_SIZE = 200
_REFERENCE_KEYS = frozenset(
    {
        "workspace_id",
        "base_id",
        "table_id",
        "record_id",
        "source_type",
        "source_id",
        "source_version",
        "mutation_kind",
        "trace_id",
    }
)


class RetrievalRegistrationDenied(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RetrievalBootstrapResult:
    status: str
    requested_projection_count: int = 0
    continuation_enqueued: bool = False


def register_authorized_retrieval_scope(
    uow: RetrievalIndexUnitOfWork,
    *,
    context: AuthorizedQueryContext,
    now: datetime,
) -> Stage12RetrievalScopeRegistration:
    if now.tzinfo is None or context.actor.actor_type != "user":
        raise RetrievalRegistrationDenied("retrieval_registration_actor_denied")
    employee = context.uow.get_digital_employee(context.employee_id)
    member = next(
        (
            item
            for item in context.uow.list_workspace_members(context.workspace_id)
            if item.user_id == context.actor.actor_id and item.status == "active"
        ),
        None,
    )
    if (
        employee is None
        or employee.status != "active"
        or employee.workspace_id != context.workspace_id
        or employee.base_id != context.base_id
        or context.snapshot.employee_id != employee.id
        or member is None
        or member.role != context.actor.role
    ):
        raise RetrievalRegistrationDenied("retrieval_registration_scope_denied")
    proof = _registration_proof(context, employee=employee, member=member)
    retrieval_scope_hash = str(proof["retrieval_scope_hash"])
    registration_hash = canonical_retrieval_sha256(proof)
    active = [
        registration
        for registration in uow.list_registrations(workspace_id=context.workspace_id)
        if registration.employee_id == employee.id
        and registration.actor_type == context.actor.actor_type
        and registration.actor_id == context.actor.actor_id
        and registration.retrieval_scope_hash == retrieval_scope_hash
        and registration.status == "active"
        and registration.revoked_at is None
    ]
    if len(active) > 1:
        raise RetrievalRegistrationDenied("retrieval_registration_duplicate")
    with uow.atomic():
        if active:
            current = active[0]
            if (
                current.expires_at > now
                and current.registration_hash == registration_hash
            ):
                current.last_seen_at = now
                current.expires_at = now + _REGISTRATION_TTL
                uow.flush()
                return current
            current.status = "revoked"
            current.revoked_at = now
        stored = {key: value for key, value in proof.items() if key != "version"}
        stored["scope_view_ids"] = list(proof["scope_view_ids"])
        registration = Stage12RetrievalScopeRegistration(
            id=uuid4(),
            **stored,
            registration_hash=registration_hash,
            status="active",
            last_seen_at=now,
            expires_at=now + _REGISTRATION_TTL,
            revoked_at=None,
        )
        uow.add_registration(registration)
        uow.flush()
        request_retrieval_scope_bootstrap(
            uow,
            workspace_id=context.workspace_id,
            registration_id=registration.id,
            cursor=None,
            page_size=_BOOTSTRAP_PAGE_SIZE,
            trace_id=registration_hash,
            now=now,
        )
        uow.flush()
    return registration


def process_registered_scope_bootstrap(
    platform_uow: Stage06PlatformUnitOfWork,
    index_uow: RetrievalIndexUnitOfWork,
    *,
    event: OutboxEvent,
    now: datetime,
) -> RetrievalBootstrapResult:
    parsed = _parse_bootstrap_event(event)
    if event.status == "processed":
        return RetrievalBootstrapResult(status="replayed")
    registrations = [
        item
        for item in index_uow.list_registrations(workspace_id=parsed["workspace_id"])
        if item.id == parsed["registration_id"]
    ]
    if len(registrations) > 1:
        raise RetrievalRegistrationDenied("retrieval_registration_duplicate")
    if not registrations:
        _mark_bootstrap_processed(event, now=now)
        return RetrievalBootstrapResult(status="discarded")
    registration = registrations[0]
    with index_uow.atomic():
        if registration.status != "active" or registration.revoked_at is not None:
            _mark_bootstrap_processed(event, now=now)
            index_uow.flush()
            return RetrievalBootstrapResult(status="discarded")
        if registration.expires_at <= now:
            _revoke_registration_scope(
                index_uow,
                registration=registration,
                now=now,
            )
            _mark_bootstrap_processed(event, now=now)
            index_uow.flush()
            return RetrievalBootstrapResult(status="discarded")
        try:
            context, employee, member = _rebuild_context(
                platform_uow,
                registration=registration,
            )
            proof = _registration_proof(
                context,
                employee=employee,
                member=member,
            )
        except (
            AuthorizedQueryDenied,
            PlatformValidationError,
            Stage12FieldPolicyError,
            RetrievalRegistrationDenied,
            ValueError,
        ):
            _revoke_registration_scope(
                index_uow,
                registration=registration,
                now=now,
            )
            _mark_bootstrap_processed(event, now=now)
            index_uow.flush()
            return RetrievalBootstrapResult(status="discarded")
        if not _registration_matches_proof(registration, proof):
            _revoke_registration_scope(
                index_uow,
                registration=registration,
                now=now,
            )
            _mark_bootstrap_processed(event, now=now)
            index_uow.flush()
            return RetrievalBootstrapResult(status="discarded")

        candidates = _bootstrap_candidates(platform_uow, context=context)
        cursor = parsed["cursor"]
        remaining = tuple(
            candidate
            for candidate in candidates
            if cursor is None or candidate["cursor"] > cursor
        )
        page = remaining[: parsed["page_size"]]
        projections = _bootstrap_page_projections(
            platform_uow,
            context=context,
            retrieval_scope_hash=registration.retrieval_scope_hash,
            candidates=page,
        )
        for projection in projections:
            request_retrieval_projection(
                index_uow,
                projection,
                trace_id=canonical_retrieval_sha256(
                    {
                        "version": "retrieval-bootstrap-projection-trace.v1",
                        "event_trace_id": event.trace_id,
                        "source_id": projection.source_id,
                        "content_hash": projection.content_hash,
                    }
                ),
                now=now,
            )
        _sync_relation_index(
            platform_uow,
            index_uow,
            context=context,
            retrieval_scope_hash=registration.retrieval_scope_hash,
            now=now,
        )
        continuation = len(remaining) > len(page)
        if continuation:
            request_retrieval_scope_bootstrap(
                index_uow,
                workspace_id=registration.workspace_id,
                registration_id=registration.id,
                cursor=str(page[-1]["cursor"]),
                page_size=parsed["page_size"],
                trace_id=event.trace_id,
                now=now,
            )
        _mark_bootstrap_processed(event, now=now)
        index_uow.flush()
    return RetrievalBootstrapResult(
        status="expanded" if projections else "discarded",
        requested_projection_count=len(projections),
        continuation_enqueued=continuation,
    )


def build_registered_source_projections(
    platform_uow: Stage06PlatformUnitOfWork,
    index_uow: RetrievalIndexUnitOfWork,
    *,
    reference: dict[str, object],
    now: datetime,
):
    parsed = _parse_reference(reference)
    registrations = index_uow.list_registrations(workspace_id=parsed["workspace_id"])
    if len(registrations) > _MAX_REGISTRATIONS_PER_WORKSPACE:
        raise RetrievalRegistrationDenied("retrieval_registration_budget_exceeded")
    projections = {}
    with index_uow.atomic():
        for registration in registrations:
            if registration.status != "active" or registration.revoked_at is not None:
                continue
            if registration.expires_at <= now:
                _revoke_registration_scope(
                    index_uow,
                    registration=registration,
                    now=now,
                )
                continue
            try:
                context, employee, member = _rebuild_context(
                    platform_uow,
                    registration=registration,
                )
                proof = _registration_proof(
                    context,
                    employee=employee,
                    member=member,
                )
            except (
                AuthorizedQueryDenied,
                PlatformValidationError,
                Stage12FieldPolicyError,
                RetrievalRegistrationDenied,
                ValueError,
            ):
                _revoke_registration_scope(
                    index_uow,
                    registration=registration,
                    now=now,
                )
                continue
            if not _registration_matches_proof(registration, proof):
                _revoke_registration_scope(
                    index_uow,
                    registration=registration,
                    now=now,
                )
                continue
            _sync_relation_index(
                platform_uow,
                index_uow,
                context=context,
                retrieval_scope_hash=registration.retrieval_scope_hash,
                now=now,
            )
            projection = _projection_for_reference(
                platform_uow,
                context=context,
                retrieval_scope_hash=registration.retrieval_scope_hash,
                reference=parsed,
            )
            if projection is None:
                continue
            key = (
                projection.visibility_profile_hash,
                projection.scope_hash,
                projection.content_hash,
            )
            projections[key] = projection
        index_uow.flush()
    return tuple(projections[key] for key in sorted(projections))


def read_registered_projection(
    platform_uow: Stage06PlatformUnitOfWork,
    index_uow: RetrievalIndexUnitOfWork,
    *,
    reference: dict[str, object],
    now: datetime,
):
    parsed = _parse_projection_reference(reference)
    registrations = [
        registration
        for registration in index_uow.list_registrations(
            workspace_id=parsed["workspace_id"]
        )
        if registration.status == "active"
        and registration.revoked_at is None
        and registration.retrieval_scope_hash == parsed["scope_hash"]
    ]
    if len(registrations) > _MAX_REGISTRATIONS_PER_WORKSPACE:
        raise RetrievalRegistrationDenied("retrieval_registration_budget_exceeded")
    selected = {}
    with index_uow.atomic():
        for registration in registrations:
            if registration.expires_at <= now:
                _revoke_registration_scope(
                    index_uow,
                    registration=registration,
                    now=now,
                )
                continue
            try:
                context, employee, member = _rebuild_context(
                    platform_uow,
                    registration=registration,
                )
                proof = _registration_proof(
                    context,
                    employee=employee,
                    member=member,
                )
            except (
                AuthorizedQueryDenied,
                PlatformValidationError,
                Stage12FieldPolicyError,
                RetrievalRegistrationDenied,
                ValueError,
            ):
                _revoke_registration_scope(
                    index_uow,
                    registration=registration,
                    now=now,
                )
                continue
            if not _registration_matches_proof(registration, proof):
                _revoke_registration_scope(
                    index_uow,
                    registration=registration,
                    now=now,
                )
                continue
            projection = _projection_for_reference(
                platform_uow,
                context=context,
                retrieval_scope_hash=registration.retrieval_scope_hash,
                reference=parsed,
            )
            if projection is None or not _projection_matches_request(
                projection, parsed
            ):
                continue
            selected[projection.content_hash] = projection
        index_uow.flush()
    if len(selected) > 1:
        raise RetrievalRegistrationDenied("retrieval_projection_ambiguous")
    return next(iter(selected.values()), None)


def _registration_proof(context, *, employee, member) -> dict[str, object]:
    field_policy = parse_stage12_field_policy_v2(employee.field_policy)
    retrieval_scope_hash = effective_retrieval_scope_hash(context)
    actor_role_hash = canonical_retrieval_sha256(
        {
            "version": "retrieval-actor-role.v1",
            "workspace_id": context.workspace_id,
            "actor_type": context.actor.actor_type,
            "actor_id": context.actor.actor_id,
            "role": member.role,
            "member_version": member.version,
        }
    )
    return {
        "version": "retrieval-scope-registration.v1",
        "workspace_id": context.workspace_id,
        "base_id": context.base_id,
        "employee_id": employee.id,
        "actor_type": context.actor.actor_type,
        "actor_id": context.actor.actor_id,
        "actor_role_hash": actor_role_hash,
        "member_version": member.version,
        "employee_version": employee.version,
        "scope_view_ids": tuple(sorted(context.scope_view_ids, key=str)),
        "allow_whole_table": context.allow_whole_table,
        "schema_scope_hash": context.snapshot.scope_hash,
        "retrieval_scope_hash": retrieval_scope_hash,
        "schema_hash": context.snapshot.schema_hash,
        "field_policy_version": field_policy.version,
        "field_policy_hash": field_policy.policy_hash,
    }


def _rebuild_context(platform_uow, *, registration):
    employee = platform_uow.get_digital_employee(registration.employee_id)
    member = next(
        (
            item
            for item in platform_uow.list_workspace_members(registration.workspace_id)
            if item.user_id == registration.actor_id and item.status == "active"
        ),
        None,
    )
    if (
        employee is None
        or employee.status != "active"
        or employee.workspace_id != registration.workspace_id
        or employee.base_id != registration.base_id
        or member is None
    ):
        raise RetrievalRegistrationDenied("retrieval_registration_scope_drift")
    actor = Actor(
        actor_type=registration.actor_type,
        actor_id=registration.actor_id,
        role=member.role,
    )
    snapshot = build_authorized_schema_snapshot(
        platform_uow,
        workspace_id=registration.workspace_id,
        employee_id=registration.employee_id,
        actor=actor,
        require_field_policy_v2=True,
    )
    context = build_authorized_query_context(
        platform_uow,
        workspace_id=registration.workspace_id,
        base_id=registration.base_id,
        employee_id=registration.employee_id,
        actor=actor,
        snapshot=snapshot,
        chat_authorized_view_ids=(
            None
            if registration.allow_whole_table
            else tuple(registration.scope_view_ids)
        ),
        allow_whole_table=registration.allow_whole_table,
    )
    return context, employee, member


def _registration_matches_proof(registration, proof) -> bool:
    expected_hash = canonical_retrieval_sha256(proof)
    stored = {
        "workspace_id": registration.workspace_id,
        "base_id": registration.base_id,
        "employee_id": registration.employee_id,
        "actor_type": registration.actor_type,
        "actor_id": registration.actor_id,
        "actor_role_hash": registration.actor_role_hash,
        "member_version": registration.member_version,
        "employee_version": registration.employee_version,
        "scope_view_ids": tuple(registration.scope_view_ids),
        "allow_whole_table": registration.allow_whole_table,
        "schema_scope_hash": registration.schema_scope_hash,
        "retrieval_scope_hash": registration.retrieval_scope_hash,
        "schema_hash": registration.schema_hash,
        "field_policy_version": registration.field_policy_version,
        "field_policy_hash": registration.field_policy_hash,
    }
    expected = {key: value for key, value in proof.items() if key != "version"}
    return stored == expected and registration.registration_hash == expected_hash


def _projection_for_reference(
    platform_uow,
    *,
    context,
    retrieval_scope_hash,
    reference,
):
    table = next(
        (
            item
            for item in context.snapshot.tables
            if item.table_id == reference["table_id"]
        ),
        None,
    )
    if table is None or table.base_id != reference["base_id"]:
        return None
    visible_ids = frozenset(field.field_id for field in table.fields)
    positions = {
        field.id: field.order_index
        for field in platform_uow.list_fields(table.table_id)
    }
    long_text_ids = frozenset(
        field.id
        for field in platform_uow.list_fields(table.table_id)
        if (field.options or {}).get("retrieval_mode") == "long_text"
        and field.id in visible_ids
    )
    if reference["source_type"] in {"record", "record_field"}:
        record_id = reference["record_id"]
        if record_id is None:
            return None
        record = next(
            (
                item
                for item in scan_authorized_records(
                    context=context,
                    table_id=table.table_id,
                    required_field_ids=tuple(sorted(visible_ids, key=str)),
                ).records
                if item.record_id == record_id
            ),
            None,
        )
        if record is None or record.version != reference["source_version"]:
            return None
        if reference["source_type"] == "record":
            candidates = (
                build_record_projection(
                    context.snapshot,
                    record,
                    retrieval_scope_hash=retrieval_scope_hash,
                    retrievable_field_ids=visible_ids,
                    long_text_field_ids=long_text_ids,
                    field_positions=positions,
                ),
            )
        else:
            candidates = build_record_field_projections(
                context.snapshot,
                record,
                retrieval_scope_hash=retrieval_scope_hash,
                retrievable_field_ids=visible_ids,
                long_text_field_ids=long_text_ids,
            )
    else:
        raw_table = platform_uow.get_table(table.table_id)
        source_version = (raw_table.settings or {}).get("stage12_schema_version", 1)
        if source_version != reference["source_version"]:
            return None
        candidates = build_schema_projections(
            context.snapshot,
            retrieval_scope_hash=retrieval_scope_hash,
            field_positions=positions,
            retrievable_field_ids=visible_ids,
            source_version=source_version,
        )
    return next(
        (
            projection
            for projection in candidates
            if _normalized_source_id(projection.source_id)
            == _normalized_source_id(reference["source_id"])
        ),
        None,
    )


def _sync_relation_index(
    platform_uow,
    index_uow,
    *,
    context,
    retrieval_scope_hash,
    now,
):
    catalog = build_authorized_relation_catalog(platform_uow, context.snapshot)
    records = tuple(
        record
        for table in context.snapshot.tables
        for record in scan_authorized_records(
            context=context,
            table_id=table.table_id,
            required_field_ids=tuple(
                sorted((field.field_id for field in table.fields), key=str)
            ),
        ).records
    )
    current = build_relation_projections(
        context.snapshot,
        retrieval_scope_hash=retrieval_scope_hash,
        records=records,
        catalog=catalog,
    )
    if len(current) > _MAX_RELATION_EDGES_PER_REGISTRATION:
        raise RetrievalRegistrationDenied("retrieval_relation_budget_exceeded")
    current_by_hash = {edge.edge_hash: edge for edge in current}
    existing = index_uow.list_relation_edges(
        workspace_id=context.workspace_id,
        scope_hash=retrieval_scope_hash,
    )
    existing_by_hash = {edge.edge_hash: edge for edge in existing}
    for edge in existing:
        projection = current_by_hash.get(edge.edge_hash)
        if projection is None or not _relation_row_matches(edge, projection):
            if edge.status != "revoked":
                edge.status = "revoked"
                edge.revoked_at = now
    for projection in current:
        existing_edge = existing_by_hash.get(projection.edge_hash)
        if existing_edge is not None:
            if _relation_row_matches(existing_edge, projection):
                existing_edge.status = "active"
                existing_edge.revoked_at = None
            continue
        index_uow.add_relation_edge(
            Stage12RelationEdge(
                id=uuid4(),
                workspace_id=context.workspace_id,
                relation_id=projection.relation_id,
                source_table_id=projection.source_table_id,
                source_record_id=projection.source_record_id,
                link_field_id=projection.link_field_id,
                target_table_id=projection.target_table_id,
                target_record_id=projection.target_record_id,
                direction=projection.direction,
                source_version=projection.source_version,
                target_version=projection.target_version,
                visibility_profile_hash=projection.visibility_profile_hash,
                scope_hash=projection.scope_hash,
                edge_hash=projection.edge_hash,
                status="active",
                revoked_at=None,
            )
        )


def _relation_row_matches(row, projection) -> bool:
    return (
        row.relation_id == projection.relation_id
        and row.source_table_id == projection.source_table_id
        and row.source_record_id == projection.source_record_id
        and row.link_field_id == projection.link_field_id
        and row.target_table_id == projection.target_table_id
        and row.target_record_id == projection.target_record_id
        and row.direction == projection.direction
        and row.source_version == projection.source_version
        and row.target_version == projection.target_version
        and row.visibility_profile_hash == projection.visibility_profile_hash
        and row.scope_hash == projection.scope_hash
        and row.edge_hash == projection.edge_hash
    )


def _bootstrap_candidates(platform_uow, *, context) -> tuple[dict[str, object], ...]:
    candidates: list[dict[str, object]] = []
    for table in sorted(context.snapshot.tables, key=lambda item: str(item.table_id)):
        raw_table = platform_uow.get_table(table.table_id)
        if raw_table is None or raw_table.status != "active":
            raise RetrievalRegistrationDenied("retrieval_bootstrap_table_drift")
        source_version = (raw_table.settings or {}).get("stage12_schema_version", 1)
        if (
            isinstance(source_version, bool)
            or not isinstance(source_version, int)
            or source_version < 1
        ):
            raise RetrievalRegistrationDenied("retrieval_bootstrap_schema_invalid")
        candidates.append(
            _bootstrap_candidate(
                source_type="schema_table",
                source_id=f"schema-table:{table.table_id}",
                source_version=source_version,
                table_id=table.table_id,
                record=None,
            )
        )
        for field in sorted(table.fields, key=lambda item: str(item.field_id)):
            candidates.append(
                _bootstrap_candidate(
                    source_type="schema_field",
                    source_id=f"schema-field:{field.field_id}",
                    source_version=source_version,
                    table_id=table.table_id,
                    record=None,
                )
            )
        field_ids = tuple(sorted((field.field_id for field in table.fields), key=str))
        records = scan_authorized_records(
            context=context,
            table_id=table.table_id,
            required_field_ids=field_ids,
        ).records
        long_text_ids = frozenset(
            field.id
            for field in platform_uow.list_fields(table.table_id)
            if field.id in field_ids
            and field.field_type == "text"
            and (field.options or {}).get("retrieval_mode") == "long_text"
        )
        for record in records:
            candidates.append(
                _bootstrap_candidate(
                    source_type="record",
                    source_id=f"record:{record.record_id}",
                    source_version=record.version,
                    table_id=table.table_id,
                    record=record,
                )
            )
            for field_id in sorted(long_text_ids, key=str):
                candidates.append(
                    _bootstrap_candidate(
                        source_type="record_field",
                        source_id=f"record-field:{record.record_id}:{field_id}",
                        source_version=record.version,
                        table_id=table.table_id,
                        record=record,
                    )
                )
    unique = {str(candidate["cursor"]): candidate for candidate in candidates}
    if len(unique) != len(candidates):
        raise RetrievalRegistrationDenied("retrieval_bootstrap_source_duplicate")
    return tuple(unique[key] for key in sorted(unique))


def _bootstrap_candidate(
    *,
    source_type: str,
    source_id: str,
    source_version: int,
    table_id: UUID,
    record,
) -> dict[str, object]:
    return {
        "cursor": f"{source_type}|{source_id}",
        "source_type": source_type,
        "source_id": source_id,
        "source_version": source_version,
        "table_id": table_id,
        "record": record,
    }


def _bootstrap_page_projections(
    platform_uow,
    *,
    context,
    retrieval_scope_hash,
    candidates,
):
    projections = {}
    schema_cache: dict[tuple[UUID, int], dict[str, object]] = {}
    record_field_cache: dict[UUID, dict[str, object]] = {}
    for candidate in candidates:
        table_id = candidate["table_id"]
        table = next(
            item for item in context.snapshot.tables if item.table_id == table_id
        )
        visible_ids = frozenset(field.field_id for field in table.fields)
        raw_fields = platform_uow.list_fields(table.table_id)
        positions = {field.id: field.order_index for field in raw_fields}
        long_text_ids = frozenset(
            field.id
            for field in raw_fields
            if field.id in visible_ids
            and field.field_type == "text"
            and (field.options or {}).get("retrieval_mode") == "long_text"
        )
        source_type = str(candidate["source_type"])
        source_id = str(candidate["source_id"])
        projection = None
        if source_type in {"schema_table", "schema_field"}:
            cache_key = (table.table_id, int(candidate["source_version"]))
            if cache_key not in schema_cache:
                schema_cache[cache_key] = {
                    item.source_id: item
                    for item in build_schema_projections(
                        context.snapshot,
                        retrieval_scope_hash=retrieval_scope_hash,
                        field_positions=positions,
                        retrievable_field_ids=visible_ids,
                        source_version=int(candidate["source_version"]),
                    )
                }
            projection = schema_cache[cache_key].get(source_id)
        elif source_type == "record":
            projection = build_record_projection(
                context.snapshot,
                candidate["record"],
                retrieval_scope_hash=retrieval_scope_hash,
                retrievable_field_ids=visible_ids,
                long_text_field_ids=long_text_ids,
                field_positions=positions,
            )
        else:
            record = candidate["record"]
            if record.record_id not in record_field_cache:
                record_field_cache[record.record_id] = {
                    item.source_id: item
                    for item in build_record_field_projections(
                        context.snapshot,
                        record,
                        retrieval_scope_hash=retrieval_scope_hash,
                        retrievable_field_ids=visible_ids,
                        long_text_field_ids=long_text_ids,
                    )
                }
            projection = record_field_cache[record.record_id].get(source_id)
        if projection is not None:
            projections[
                (
                    projection.visibility_profile_hash,
                    projection.scope_hash,
                    projection.content_hash,
                )
            ] = projection
    return tuple(projections[key] for key in sorted(projections))


def _parse_bootstrap_event(event: OutboxEvent) -> dict[str, object]:
    payload = event.payload
    expected = {
        "workspace_id",
        "registration_id",
        "cursor",
        "page_size",
        "trace_id",
    }
    if not (
        event.event_type == _BOOTSTRAP_EVENT
        and event.aggregate_type == "stage12_retrieval_scope_registration"
        and event.status in {"pending", "processing", "processed"}
        and isinstance(payload, dict)
        and set(payload) == expected
        and payload.get("trace_id") == event.trace_id
        and isinstance(payload.get("trace_id"), str)
        and len(str(payload["trace_id"])) == 64
        and all(character in "0123456789abcdef" for character in payload["trace_id"])
        and isinstance(payload.get("page_size"), int)
        and not isinstance(payload.get("page_size"), bool)
        and 1 <= int(payload["page_size"]) <= _BOOTSTRAP_PAGE_SIZE
        and (
            payload.get("cursor") is None
            or (
                isinstance(payload.get("cursor"), str)
                and payload["cursor"] == payload["cursor"].strip()
                and bool(payload["cursor"])
                and len(payload["cursor"]) <= 500
                and "|" in payload["cursor"]
                and "\r" not in payload["cursor"]
                and "\n" not in payload["cursor"]
            )
        )
    ):
        raise RetrievalRegistrationDenied("retrieval_scope_bootstrap_event_invalid")
    try:
        workspace_id = UUID(str(payload["workspace_id"]))
        registration_id = UUID(str(payload["registration_id"]))
    except (TypeError, ValueError, AttributeError) as exc:
        raise RetrievalRegistrationDenied(
            "retrieval_scope_bootstrap_event_invalid"
        ) from exc
    if (
        event.aggregate_id != str(registration_id)
        or str(payload["registration_id"]) != str(registration_id)
        or str(payload["workspace_id"]) != str(workspace_id)
    ):
        raise RetrievalRegistrationDenied("retrieval_scope_bootstrap_event_invalid")
    return {
        "workspace_id": workspace_id,
        "registration_id": registration_id,
        "cursor": payload["cursor"],
        "page_size": int(payload["page_size"]),
    }


def _mark_bootstrap_processed(event: OutboxEvent, *, now: datetime) -> None:
    event.status = "processed"
    event.processed_at = now
    event.last_error = None
    event.last_error_redacted = None


def _parse_reference(reference):
    if not isinstance(reference, dict) or set(reference) != _REFERENCE_KEYS:
        raise RetrievalRegistrationDenied("retrieval_registration_reference_invalid")
    try:
        parsed = dict(reference)
        parsed["workspace_id"] = UUID(str(reference["workspace_id"]))
        parsed["base_id"] = UUID(str(reference["base_id"]))
        parsed["table_id"] = UUID(str(reference["table_id"]))
        parsed["record_id"] = (
            None
            if reference["record_id"] is None
            else UUID(str(reference["record_id"]))
        )
    except (TypeError, ValueError) as exc:
        raise RetrievalRegistrationDenied(
            "retrieval_registration_reference_invalid"
        ) from exc
    if (
        parsed["source_type"]
        not in {"schema_table", "schema_field", "record", "record_field"}
        or not isinstance(parsed["source_id"], str)
        or not parsed["source_id"]
        or not isinstance(parsed["source_version"], int)
        or isinstance(parsed["source_version"], bool)
        or parsed["source_version"] < 1
        or (parsed["source_type"] in {"record", "record_field"})
        != (parsed["record_id"] is not None)
    ):
        raise RetrievalRegistrationDenied("retrieval_registration_reference_invalid")
    return parsed


def _parse_projection_reference(reference):
    expected = {
        "workspace_id",
        "base_id",
        "table_id",
        "record_id",
        "source_type",
        "source_id",
        "source_version",
        "content_hash",
        "visibility_profile_hash",
        "scope_hash",
        "trace_id",
    }
    if not isinstance(reference, dict) or set(reference) != expected:
        raise RetrievalRegistrationDenied("retrieval_projection_reference_invalid")
    translated = {
        "workspace_id": reference["workspace_id"],
        "base_id": reference["base_id"],
        "table_id": reference["table_id"],
        "record_id": reference["record_id"],
        "source_type": reference["source_type"],
        "source_id": reference["source_id"],
        "source_version": reference["source_version"],
        "mutation_kind": "projection_requested",
        "trace_id": reference["trace_id"],
    }
    parsed = _parse_reference(translated)
    for key in ("content_hash", "visibility_profile_hash", "scope_hash"):
        value = reference[key]
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise RetrievalRegistrationDenied("retrieval_projection_reference_invalid")
        parsed[key] = value
    return parsed


def _projection_matches_request(projection, reference) -> bool:
    return (
        projection.workspace_id == reference["workspace_id"]
        and projection.base_id == reference["base_id"]
        and projection.table_id == reference["table_id"]
        and projection.record_id == reference["record_id"]
        and projection.source_type == reference["source_type"]
        and projection.source_id == reference["source_id"]
        and projection.source_version == reference["source_version"]
        and projection.content_hash == reference["content_hash"]
        and projection.visibility_profile_hash == reference["visibility_profile_hash"]
        and projection.scope_hash == reference["scope_hash"]
    )


def _revoke_registration(registration, *, now):
    registration.status = "revoked"
    registration.revoked_at = now


def _revoke_registration_scope(index_uow, *, registration, now):
    matching_sources = [
        source
        for source in index_uow.list_sources(workspace_id=registration.workspace_id)
        if source.scope_hash == registration.retrieval_scope_hash
        and source.status != "revoked"
    ]
    source_profiles = {
        (
            source.source_type,
            source.source_identity,
            source.visibility_profile_hash,
        )
        for source in matching_sources
    }
    for source_type, source_identity, visibility_profile_hash in sorted(
        source_profiles
    ):
        revoke_retrieval_source(
            index_uow,
            workspace_id=registration.workspace_id,
            source_type=source_type,
            source_identity=source_identity,
            visibility_profile_hash=visibility_profile_hash,
            reason_code="authorized_scope_contracted",
            now=now,
        )
    for edge in index_uow.list_relation_edges(
        workspace_id=registration.workspace_id,
        scope_hash=registration.retrieval_scope_hash,
    ):
        if edge.status != "revoked":
            edge.status = "revoked"
            edge.revoked_at = now
    _revoke_registration(registration, now=now)


def _normalized_source_id(value: str) -> str:
    return (
        value.replace("schema-table:", "schema_table:")
        .replace("schema-field:", "schema_field:")
        .replace("record-field:", "record_field:")
    )


__all__ = [
    "RetrievalBootstrapResult",
    "RetrievalRegistrationDenied",
    "build_registered_source_projections",
    "process_registered_scope_bootstrap",
    "read_registered_projection",
    "register_authorized_retrieval_scope",
]
