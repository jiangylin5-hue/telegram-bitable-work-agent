from __future__ import annotations

from dataclasses import is_dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
from uuid import UUID, uuid4

import pytest

from app.models.stage06_runtime import DigitalEmployeeMemberGrant
from app.runtime.stage08_memory_contracts import (
    MemoryMaterializationProjection,
    MemoryScopeProjection,
    MemorySourceRef,
)
from app.runtime.stage08_retrieval_contracts import (
    RetrievalSafeCitation,
    validate_retrieval_safe_citation,
)
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_form_view,
    create_record,
    create_table,
    create_workspace,
)
from app.services.stage08_memory import materialize_memory_from_projection
from app.services.stage08_retrieval import (
    process_knowledge_index_event,
    register_memory_knowledge_source,
)
from app.services.stage08_retrieval_embeddings import TestHashEmbeddingProvider
from app.services.stage08_retrieval_provider import (
    PostgresRetrievalProvider,
    Stage08RetrievalAuthorityFactory,
    _Stage08RetrievalAuthority,
)


NOW = datetime(2026, 7, 21, 9, 0, tzinfo=UTC)


def _fixture(*, text: str = "客户 Acme 已确认报价，下一步安排预算会议。"):
    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(
        uow,
        name=f"D4-{uuid4().hex}",
        owner_user_id=owner.actor_id,
        actor=owner,
    )
    base = create_base(uow, workspace.id, name="CRM", actor=owner)
    customers = create_table(
        uow,
        base.id,
        name="Customers",
        key="customers",
        actor=owner,
    )
    projects = create_table(
        uow,
        base.id,
        name="Projects",
        key="projects",
        actor=owner,
    )
    create_field(
        uow,
        customers.id,
        name="Name",
        key="name",
        field_type="text",
        actor=owner,
    )
    summary_field = create_field(
        uow,
        projects.id,
        name="Summary",
        key="summary",
        field_type="text",
        actor=owner,
    )
    create_field(
        uow,
        projects.id,
        name="Customer",
        key="customer",
        field_type="linked_record",
        options={"target_table_id": str(customers.id)},
        actor=owner,
    )
    customer = create_record(
        uow,
        customers.id,
        values={"name": "Acme"},
        actor=owner,
    )
    project = create_record(
        uow,
        projects.id,
        values={"summary": text, "customer": [str(customer.id)]},
        actor=owner,
    )
    view = create_form_view(
        uow,
        base.id,
        projects.id,
        name="Projects",
        view_type="grid",
        config={"fields": ["summary", "customer"]},
        actor=owner,
    )
    view.version = 1
    employee = create_digital_employee(
        uow,
        base.id,
        name="Retriever",
        description="D4 provider",
        telegram_alias=None,
        accessible_tables=[str(customers.id), str(projects.id)],
        accessible_views=[str(view.id)],
        allowed_actions=["query"],
        actor=owner,
    )
    item = materialize_memory_from_projection(
        uow,
        MemoryMaterializationProjection(
            memory_type="decision",
            scope=MemoryScopeProjection(
                workspace_id=workspace.id,
                base_id=base.id,
                table_id=projects.id,
                customer_record_id=customer.id,
                project_record_id=project.id,
            ),
            payload={"summary": text},
            source_refs=(
                MemorySourceRef(
                    source_kind="platform_record",
                    source_id=project.id,
                    source_version=project.version,
                    field_keys=("summary",),
                ),
            ),
            valid_until=NOW + timedelta(days=2),
        ),
        actor=owner,
        now=NOW,
    )
    registration = register_memory_knowledge_source(
        uow,
        item.id,
        actor=owner,
        now=NOW,
        trace_id="d4-register",
    )
    assert registration is not None
    indexed = process_knowledge_index_event(
        uow,
        registration.event,
        provider=TestHashEmbeddingProvider(),
        now=NOW + timedelta(seconds=1),
    )
    assert indexed.status == "indexed"
    return {
        "uow": uow,
        "owner": owner,
        "workspace": workspace,
        "base": base,
        "customers": customers,
        "projects": projects,
        "summary_field": summary_field,
        "customer": customer,
        "project": project,
        "view": view,
        "employee": employee,
        "item": item,
        "source": registration.source,
    }


def _authority(fixture):
    return Stage08RetrievalAuthorityFactory.build(
        fixture["uow"],
        actor=fixture["owner"],
        workspace_id=fixture["workspace"].id,
        employee_id=fixture["employee"].id,
        customer_record_id=fixture["customer"].id,
        project_record_id=fixture["project"].id,
    )


def _search(fixture, *, provider=None, query="报价", limit=12):
    selected = provider or PostgresRetrievalProvider()
    return selected, selected.search(
        fixture["uow"],
        _authority(fixture),
        query=query,
        limit=limit,
        now=NOW + timedelta(seconds=2),
    )


def test_authority_and_private_results_are_opaque_and_non_serializable() -> None:
    fixture = _fixture()
    from app.services import stage08_retrieval_provider as provider_module

    authority = _authority(fixture)
    provider, result = _search(fixture)

    assert repr(authority) == "<Stage08RetrievalAuthority opaque>"
    assert repr(result) == "<Stage08RetrievalResult opaque>"
    forbidden = " ".join(
        [
            str(fixture["workspace"].id),
            str(fixture["employee"].id),
            str(fixture["customer"].id),
            str(fixture["project"].id),
            "报价",
        ]
    )
    assert all(value not in repr(authority) + repr(result) for value in forbidden.split())
    with pytest.raises(AttributeError):
        _ = authority.workspace_id
    with pytest.raises(TypeError):
        vars(authority)
    with pytest.raises(TypeError):
        json.dumps(authority)
    with pytest.raises(TypeError, match="retrieval_authority_unavailable"):
        _Stage08RetrievalAuthority()

    evidence = provider.render_private_evidence(
        fixture["uow"], result, now=NOW + timedelta(seconds=3)
    )
    assert repr(evidence) == "<Stage08PrivateEvidence opaque>"
    assert is_dataclass(provider_module._HitSnapshot) is False
    assert is_dataclass(evidence) is False
    assert str(fixture["source"].id) not in repr(evidence)
    assert "报价" not in repr(evidence)


@pytest.mark.parametrize(
    "drift",
    [
        "workspace_inactive",
        "employee_inactive",
        "query_removed",
        "base_inactive",
        "table_inactive",
        "view_inactive",
        "member_inactive",
        "business_relation",
    ],
)
def test_factory_and_stale_authority_fail_closed_on_current_scope_drift(drift: str) -> None:
    fixture = _fixture()
    authority = _authority(fixture)
    if drift == "workspace_inactive":
        fixture["workspace"].status = "inactive"
    elif drift == "employee_inactive":
        fixture["employee"].status = "paused"
    elif drift == "query_removed":
        fixture["employee"].allowed_actions = ["summarize"]
    elif drift == "base_inactive":
        fixture["base"].status = "inactive"
    elif drift == "table_inactive":
        fixture["projects"].status = "inactive"
    elif drift == "view_inactive":
        fixture["view"].status = "inactive"
    elif drift == "member_inactive":
        fixture["uow"].list_workspace_members(fixture["workspace"].id)[0].status = "inactive"
    else:
        fixture["project"].values["customer"] = []
        fixture["project"].version += 1

    provider = PostgresRetrievalProvider()
    stale_result = provider.search(
        fixture["uow"],
        authority,
        query="报价",
        limit=12,
        now=NOW + timedelta(seconds=2),
    )
    stale_view = provider.safe_view(
        fixture["uow"], stale_result, now=NOW + timedelta(seconds=3)
    )
    assert stale_view.status == "unavailable"
    assert stale_view.result_count == 0
    assert stale_view.error_code == "authority_changed"

    unavailable = Stage08RetrievalAuthorityFactory.build(
        fixture["uow"],
        actor=fixture["owner"],
        workspace_id=fixture["workspace"].id,
        employee_id=fixture["employee"].id,
        customer_record_id=fixture["customer"].id,
        project_record_id=fixture["project"].id,
    )
    assert repr(unavailable) == "<Stage08RetrievalAuthority opaque>"
    denied = provider.search(
        fixture["uow"],
        unavailable,
        query="报价",
        limit=12,
        now=NOW + timedelta(seconds=4),
    )
    assert provider.safe_citations(
        fixture["uow"], denied, now=NOW + timedelta(seconds=5)
    ) == ()


def test_assigned_employee_requires_current_member_grant() -> None:
    fixture = _fixture()
    employee = fixture["employee"]
    member = fixture["uow"].list_workspace_members(fixture["workspace"].id)[0]
    employee.access_mode = "assigned"
    employee.version += 1

    unavailable = _authority(fixture)
    provider = PostgresRetrievalProvider()
    denied = provider.search(
        fixture["uow"], unavailable, query="报价", limit=12, now=NOW
    )
    assert provider.safe_view(fixture["uow"], denied, now=NOW).error_code == "authority_changed"

    fixture["uow"].add_digital_employee_member_grant(
        DigitalEmployeeMemberGrant(
            id=uuid4(),
            employee_id=employee.id,
            workspace_member_id=member.id,
        )
    )
    authority = _authority(fixture)
    allowed = provider.search(
        fixture["uow"], authority, query="报价", limit=12, now=NOW
    )
    assert provider.safe_view(fixture["uow"], allowed, now=NOW).has_results is True


def test_factory_rejects_forged_actor_role_and_cross_workspace_member_grant() -> None:
    fixture = _fixture()
    provider = PostgresRetrievalProvider()
    forged_role = Actor(
        actor_type="user",
        actor_id=fixture["owner"].actor_id,
        role="admin",
    )
    forged = Stage08RetrievalAuthorityFactory.build(
        fixture["uow"],
        actor=forged_role,
        workspace_id=fixture["workspace"].id,
        employee_id=fixture["employee"].id,
        customer_record_id=fixture["customer"].id,
        project_record_id=fixture["project"].id,
    )
    forged_result = provider.search(
        fixture["uow"], forged, query="报价", limit=12, now=NOW
    )
    assert provider.safe_view(
        fixture["uow"], forged_result, now=NOW
    ).error_code == "authority_changed"

    employee = fixture["employee"]
    member = fixture["uow"].list_workspace_members(fixture["workspace"].id)[0]
    employee.access_mode = "assigned"
    employee.version += 1
    fixture["uow"].add_digital_employee_member_grant(
        DigitalEmployeeMemberGrant(
            id=uuid4(),
            employee_id=employee.id,
            workspace_member_id=member.id,
        )
    )
    foreign_workspace = create_workspace(
        fixture["uow"],
        name=f"Foreign-{uuid4().hex}",
        owner_user_id="foreign-owner",
    )
    foreign_member = fixture["uow"].list_workspace_members(foreign_workspace.id)[0]
    fixture["uow"].add_digital_employee_member_grant(
        DigitalEmployeeMemberGrant(
            id=uuid4(),
            employee_id=employee.id,
            workspace_member_id=foreign_member.id,
        )
    )
    invalid_grants = _authority(fixture)
    denied = provider.search(
        fixture["uow"], invalid_grants, query="报价", limit=12, now=NOW
    )
    assert provider.safe_view(
        fixture["uow"], denied, now=NOW
    ).error_code == "authority_changed"


@pytest.mark.parametrize(
    "carrier",
    [
        "foreign_workspace",
        "foreign_base",
        "foreign_table",
        "foreign_view",
        "foreign_customer",
        "foreign_project",
        "hidden_field",
        "group_chat_ref",
        "telegram_chat_id",
        "identity_token",
        "unknown_scope",
        "telegram_source_ref",
        "malformed_fingerprint",
        "unknown_source_type",
    ],
)
def test_prefilter_rejects_scope_mismatch_and_group_telegram_metadata(carrier: str) -> None:
    fixture = _fixture()
    source = fixture["source"]
    if carrier == "foreign_workspace":
        source.scope["workspace_id"] = str(uuid4())
    elif carrier == "foreign_base":
        source.scope["base_id"] = str(uuid4())
    elif carrier == "foreign_table":
        source.scope["table_id"] = str(uuid4())
    elif carrier == "foreign_view":
        source.scope["view_id"] = str(uuid4())
    elif carrier == "foreign_customer":
        source.scope["customer_record_id"] = str(uuid4())
    elif carrier == "foreign_project":
        source.scope["project_record_id"] = str(uuid4())
    elif carrier == "hidden_field":
        fixture["summary_field"].permission_policy = {"owner": "hidden"}
        source.scope["field_id"] = str(fixture["summary_field"].id)
    elif carrier == "telegram_source_ref":
        source.source_ref["telegram_message_id"] = "body-secret"
    elif carrier == "malformed_fingerprint":
        source.logical_source_fingerprint = "body-secret"
    elif carrier == "unknown_source_type":
        source.source_type = "telegram_message"
    else:
        source.scope[carrier] = "body-secret"

    provider, result = _search(fixture)
    view = provider.safe_view(fixture["uow"], result, now=NOW + timedelta(seconds=3))
    assert view.result_count == 0
    assert provider.safe_citations(
        fixture["uow"], result, now=NOW + timedelta(seconds=3)
    ) == ()
    assert "body-secret" not in repr(result) + repr(view)


@pytest.mark.parametrize(
    "drift",
    [
        "memory_revoked",
        "memory_expired",
        "memory_superseded",
        "memory_version",
        "source_hash",
        "source_scope",
        "record_source",
        "chunk_stale",
    ],
)
def test_post_candidate_reread_drops_memory_source_and_chunk_drift_without_side_effect(
    drift: str,
) -> None:
    fixture = _fixture()
    provider, result = _search(
        fixture,
        provider=PostgresRetrievalProvider(
            embedding_provider=TestHashEmbeddingProvider()
        ),
    )
    audit_snapshot = tuple(fixture["uow"].audit_events)
    if drift == "memory_revoked":
        fixture["item"].status = "revoked"
    elif drift == "memory_expired":
        fixture["item"].valid_until = NOW
    elif drift == "memory_superseded":
        fixture["item"].status = "superseded"
    elif drift == "memory_version":
        fixture["item"].version += 1
    elif drift == "source_hash":
        fixture["source"].projection_hash = "0" * 64
    elif drift == "source_scope":
        fixture["source"].scope["table_id"] = str(uuid4())
    elif drift == "record_source":
        fixture["project"].version += 1
    else:
        fixture["uow"].knowledge_chunks[0].status = "stale"

    assert provider.render_private_evidence(
        fixture["uow"], result, now=NOW + timedelta(seconds=4)
    ) is None
    assert provider.safe_citations(
        fixture["uow"], result, now=NOW + timedelta(seconds=4)
    ) == ()
    assert tuple(fixture["uow"].audit_events) == audit_snapshot


def test_default_is_keyword_only_and_explicit_test_adapter_enables_hybrid() -> None:
    fixture = _fixture()
    keyword_provider, keyword_result = _search(fixture)
    keyword_view = keyword_provider.safe_view(
        fixture["uow"], keyword_result, now=NOW + timedelta(seconds=3)
    )
    assert keyword_view.status == "degraded"
    assert keyword_view.degradation_code == "keyword_only"
    assert keyword_view.has_results is True

    hybrid_provider = PostgresRetrievalProvider(
        embedding_provider=TestHashEmbeddingProvider()
    )
    _, first = _search(fixture, provider=hybrid_provider)
    _, second = _search(fixture, provider=hybrid_provider)
    first_view = hybrid_provider.safe_view(
        fixture["uow"], first, now=NOW + timedelta(seconds=3)
    )
    second_view = hybrid_provider.safe_view(
        fixture["uow"], second, now=NOW + timedelta(seconds=3)
    )
    assert first_view == second_view
    assert first_view.status == "ready"
    assert first_view.degradation_code == "none"
    assert hybrid_provider.safe_citations(
        fixture["uow"], first, now=NOW + timedelta(seconds=3)
    ) == hybrid_provider.safe_citations(
        fixture["uow"], second, now=NOW + timedelta(seconds=3)
    )


def test_query_and_limit_validation_is_fixed_fail_closed_and_redacted() -> None:
    fixture = _fixture()
    provider = PostgresRetrievalProvider()
    authority = _authority(fixture)
    secret = "query-secret-sentinel"
    for query, limit in [("", 12), (secret * 40, 12), (object(), 12), (secret, 0), (secret, 13), (secret, True)]:
        result = provider.search(
            fixture["uow"], authority, query=query, limit=limit, now=NOW
        )
        view = provider.safe_view(fixture["uow"], result, now=NOW)
        assert view.status == "failed"
        assert view.error_code == "retrieval_unavailable"
        assert secret not in repr(result) + repr(view)


def test_search_caps_private_hits_and_safe_citations_at_twelve() -> None:
    fixture = _fixture(text=("报价计划 " * 3000))
    provider, result = _search(
        fixture,
        provider=PostgresRetrievalProvider(
            embedding_provider=TestHashEmbeddingProvider()
        ),
    )
    view = provider.safe_view(fixture["uow"], result, now=NOW + timedelta(seconds=3))
    citations = provider.safe_citations(
        fixture["uow"], result, now=NOW + timedelta(seconds=3)
    )
    assert view.result_count == 12
    assert len(citations) == 12
    assert [citation.display_ordinal for citation in citations] == list(range(1, 13))


def test_safe_citation_exact_shape_and_constructed_model_attack_are_rejected() -> None:
    fixture = _fixture()
    provider, result = _search(fixture)
    citations = provider.safe_citations(
        fixture["uow"], result, now=NOW + timedelta(seconds=3)
    )
    assert len(citations) == 1
    citation = citations[0]
    assert set(citation.model_dump()) == {
        "display_ordinal",
        "label",
        "source_type_category",
        "scope_category",
    }
    assert citation.label == "retrieved_material"
    assert citation.scope_category == "business"
    serialized = repr(citations) + citation.model_dump_json()
    for private in (
        str(fixture["workspace"].id),
        str(fixture["source"].id),
        str(fixture["uow"].knowledge_chunks[0].id),
        "报价",
        "score",
        "embedding",
        "actor",
        "authority",
    ):
        assert private not in serialized

    constructed = RetrievalSafeCitation.model_construct(
        display_ordinal=1,
        label="retrieved_material",
        source_type_category="business_memory",
        scope_category="business",
    )
    constructed.__dict__["source_id"] = str(fixture["source"].id)
    with pytest.raises(ValueError, match="retrieval_safe_citation_shape_invalid"):
        validate_retrieval_safe_citation(constructed)
    with pytest.raises(ValueError):
        RetrievalSafeCitation(
            display_ordinal=1,
            label="retrieved_material",
            source_type_category="mixed",
            scope_category="none",
        )


def test_forged_authority_and_result_objects_never_release_private_evidence() -> None:
    fixture = _fixture()
    provider = PostgresRetrievalProvider()
    forged_authority = object()
    forged = provider.search(
        fixture["uow"], forged_authority, query="报价", limit=12, now=NOW
    )
    assert provider.render_private_evidence(fixture["uow"], forged, now=NOW) is None
    assert provider.safe_citations(fixture["uow"], forged, now=NOW) == ()
    assert provider.safe_view(fixture["uow"], forged, now=NOW).error_code == "authority_changed"
    assert provider.render_private_evidence(fixture["uow"], object(), now=NOW) is None
    assert provider.safe_citations(fixture["uow"], object(), now=NOW) == ()


def test_candidate_verifier_exception_is_dropped_without_raw_error_leak(
    monkeypatch,
) -> None:
    fixture = _fixture()
    from app.services import stage08_retrieval_provider as provider_module

    sentinel = "provider-verifier-body-secret-sentinel"

    def fail_read(*args, **kwargs):
        del args, kwargs
        raise RuntimeError(sentinel)

    monkeypatch.setattr(provider_module, "read_memory_projection", fail_read)
    provider = PostgresRetrievalProvider()
    result = provider.search(
        fixture["uow"],
        _authority(fixture),
        query="报价",
        limit=12,
        now=NOW,
    )
    view = provider.safe_view(fixture["uow"], result, now=NOW)
    assert view.result_count == 0
    assert provider.safe_citations(fixture["uow"], result, now=NOW) == ()
    assert sentinel not in repr(result) + repr(view)


@pytest.mark.parametrize(
    "terminal_fact",
    ["source_revoked_at", "source_deleted_at", "chunk_deleted_at"],
)
def test_terminal_timestamps_exclude_candidates_and_held_results_without_side_effect(
    terminal_fact: str,
) -> None:
    fixture = _fixture()
    provider, held_result = _search(fixture)
    audit_snapshot = tuple(fixture["uow"].audit_events)
    terminal_at = NOW + timedelta(seconds=3)
    if terminal_fact == "source_revoked_at":
        fixture["source"].revoked_at = terminal_at
    elif terminal_fact == "source_deleted_at":
        fixture["source"].deleted_at = terminal_at
    else:
        fixture["uow"].knowledge_chunks[0].deleted_at = terminal_at

    assert provider.render_private_evidence(
        fixture["uow"], held_result, now=NOW + timedelta(seconds=4)
    ) is None
    assert provider.safe_citations(
        fixture["uow"], held_result, now=NOW + timedelta(seconds=4)
    ) == ()
    held_view = provider.safe_view(
        fixture["uow"], held_result, now=NOW + timedelta(seconds=4)
    )
    assert held_view.result_count == 0

    _, fresh_result = _search(fixture)
    fresh_view = provider.safe_view(
        fixture["uow"], fresh_result, now=NOW + timedelta(seconds=4)
    )
    assert fresh_view.result_count == 0
    assert tuple(fixture["uow"].audit_events) == audit_snapshot


@pytest.mark.parametrize(
    "lineage_drift",
    ["wrong_root_fingerprint", "cross_lineage_fingerprint", "current_cycle"],
)
def test_memory_root_lineage_fingerprint_and_current_chain_are_revalidated(
    lineage_drift: str,
) -> None:
    fixture = _fixture()
    provider, valid_result = _search(fixture)
    assert provider.safe_view(
        fixture["uow"], valid_result, now=NOW + timedelta(seconds=3)
    ).result_count == 1

    if lineage_drift == "wrong_root_fingerprint":
        other_root = uuid4()
        fixture["source"].logical_source_fingerprint = hashlib.sha256(
            f"memory_lineage:{other_root}".encode("utf-8")
        ).hexdigest()
    elif lineage_drift == "cross_lineage_fingerprint":
        unrelated = materialize_memory_from_projection(
            fixture["uow"],
            MemoryMaterializationProjection(
                memory_type="preference",
                scope=MemoryScopeProjection(
                    workspace_id=fixture["workspace"].id,
                    base_id=fixture["base"].id,
                    table_id=fixture["customers"].id,
                    customer_record_id=fixture["customer"].id,
                    ),
                    payload={"name": "Acme"},
                source_refs=(
                    MemorySourceRef(
                        source_kind="platform_record",
                        source_id=fixture["customer"].id,
                        source_version=fixture["customer"].version,
                        field_keys=("name",),
                    ),
                ),
            ),
            actor=fixture["owner"],
            now=NOW + timedelta(seconds=1),
        )
        fixture["source"].logical_source_fingerprint = hashlib.sha256(
            f"memory_lineage:{unrelated.id}".encode("utf-8")
        ).hexdigest()
    else:
        fixture["item"].supersedes_id = fixture["item"].id

    _, denied_result = _search(fixture)
    assert provider.render_private_evidence(
        fixture["uow"], denied_result, now=NOW + timedelta(seconds=4)
    ) is None
    assert provider.safe_citations(
        fixture["uow"], denied_result, now=NOW + timedelta(seconds=4)
    ) == ()
    assert provider.safe_view(
        fixture["uow"], denied_result, now=NOW + timedelta(seconds=4)
    ).result_count == 0
