from __future__ import annotations

from hashlib import sha256
from uuid import UUID

from app.schemas.agent_task_spec_v2 import (
    AuthorizedFieldSpec,
    AuthorizedSchemaSnapshot,
    AuthorizedTableSpec,
    authorized_schema_sha256,
)
from app.schemas.authorized_query_plan import (
    AuthorizedRelationSpec,
    StructuredFieldValue,
)
from app.services.authorized_query_records import AuthorizedRecord
from app.services.retrieval_v2_projection import (
    build_record_field_projections,
    build_record_projection,
    build_relation_projections,
    build_schema_projections,
    chunk_projection,
)


WORKSPACE_ID = UUID("10000000-0000-0000-0000-000000000001")
EMPLOYEE_ID = UUID("10000000-0000-0000-0000-000000000002")
BASE_ID = UUID("10000000-0000-0000-0000-000000000003")
WORK_TABLE_ID = UUID("10000000-0000-0000-0000-000000000010")
PROJECT_TABLE_ID = UUID("10000000-0000-0000-0000-000000000020")
CODE_ID = UUID("10000000-0000-0000-0000-000000000101")
TITLE_ID = UUID("10000000-0000-0000-0000-000000000102")
SUMMARY_ID = UUID("10000000-0000-0000-0000-000000000103")
SENSITIVE_ID = UUID("10000000-0000-0000-0000-000000000104")
LINK_ID = UUID("10000000-0000-0000-0000-000000000105")
PROJECT_CODE_ID = UUID("10000000-0000-0000-0000-000000000201")
WORK_RECORD_ID = UUID("10000000-0000-0000-0000-000000000301")
PROJECT_RECORD_ID = UUID("10000000-0000-0000-0000-000000000302")
SCOPE_HASH = "a" * 64
RETRIEVAL_SCOPE_HASH = (
    "f69452c776cadfa5e233dd6838a19658b8c19f8b6265ebd69e8a27a0480d50e9"
)


class CharacterTokenCounter:
    def encode(self, text: str) -> tuple[int, ...]:
        return tuple(ord(character) for character in text)

    def decode(self, token_ids: tuple[int, ...]) -> str:
        return "".join(chr(token_id) for token_id in token_ids)


def _field(
    field_id: UUID,
    *,
    table_id: UUID,
    key: str,
    name: str,
    field_type: str = "text",
    aliases: tuple[str, ...] = (),
) -> AuthorizedFieldSpec:
    return AuthorizedFieldSpec(
        field_id=field_id,
        table_id=table_id,
        key=key,
        name=name,
        field_type=field_type,
        aliases=aliases,
        choices=(),
        writable=False,
        default_value=None,
    )


def _snapshot() -> AuthorizedSchemaSnapshot:
    work_fields = (
        _field(CODE_ID, table_id=WORK_TABLE_ID, key="ticket_code", name="编号"),
        _field(TITLE_ID, table_id=WORK_TABLE_ID, key="title", name="标题"),
        _field(SUMMARY_ID, table_id=WORK_TABLE_ID, key="summary", name="摘要"),
        _field(
            SENSITIVE_ID,
            table_id=WORK_TABLE_ID,
            key="customer_contact",
            name="客户联系方式",
        ),
        _field(
            LINK_ID,
            table_id=WORK_TABLE_ID,
            key="project_link",
            name="关联项目",
            field_type="linked_record",
        ),
    )
    tables = (
        AuthorizedTableSpec(
            table_id=PROJECT_TABLE_ID,
            base_id=BASE_ID,
            key="projects",
            name="项目",
            aliases=("项目表",),
            fields=(
                _field(
                    PROJECT_CODE_ID,
                    table_id=PROJECT_TABLE_ID,
                    key="project_code",
                    name="项目编号",
                ),
            ),
            identity_field_id=PROJECT_CODE_ID,
        ),
        AuthorizedTableSpec(
            table_id=WORK_TABLE_ID,
            base_id=BASE_ID,
            key="work_items",
            name="工作项",
            aliases=("事项", "工单"),
            fields=work_fields,
            identity_field_id=CODE_ID,
        ),
    )
    values = {
        "version": "authorized-schema-snapshot.v1",
        "workspace_id": WORKSPACE_ID,
        "employee_id": EMPLOYEE_ID,
        "scope_hash": SCOPE_HASH,
        "tables": tables,
    }
    return AuthorizedSchemaSnapshot(
        **values,
        schema_hash=authorized_schema_sha256(**values),
    )


def _work_record(*, summary: str = "等待范围确认") -> AuthorizedRecord:
    values = tuple(
        sorted(
            (
                StructuredFieldValue(field_id=CODE_ID, value="MT-001"),
                StructuredFieldValue(field_id=TITLE_ID, value="Atlas checklist"),
                StructuredFieldValue(field_id=SUMMARY_ID, value=summary),
                StructuredFieldValue(
                    field_id=SENSITIVE_ID,
                    value="hidden-secret@example.com",
                ),
                StructuredFieldValue(
                    field_id=LINK_ID,
                    value=[str(PROJECT_RECORD_ID)],
                ),
            ),
            key=lambda item: str(item.field_id),
        )
    )
    return AuthorizedRecord(
        record_id=WORK_RECORD_ID,
        table_id=WORK_TABLE_ID,
        values=values,
        version=3,
        source_view_ids=(),
    )


def _project_record() -> AuthorizedRecord:
    return AuthorizedRecord(
        record_id=PROJECT_RECORD_ID,
        table_id=PROJECT_TABLE_ID,
        values=(StructuredFieldValue(field_id=PROJECT_CODE_ID, value="PRJ-ATLAS"),),
        version=2,
        source_view_ids=(),
    )


def test_schema_projection_is_position_stable_and_visible_only() -> None:
    snapshot = _snapshot()
    projections = build_schema_projections(
        snapshot,
        retrieval_scope_hash=RETRIEVAL_SCOPE_HASH,
        field_positions={
            TITLE_ID: 0,
            CODE_ID: 1,
            SUMMARY_ID: 2,
            LINK_ID: 3,
            PROJECT_CODE_ID: 0,
        },
        retrievable_field_ids=frozenset(
            {TITLE_ID, CODE_ID, SUMMARY_ID, LINK_ID, PROJECT_CODE_ID}
        ),
    )
    work_table = next(
        item
        for item in projections
        if item.source_id == f"schema-table:{WORK_TABLE_ID}"
    )

    assert work_table.canonical_text.index(
        "[field] 标题"
    ) < work_table.canonical_text.index("[field] 编号")
    assert "事项 工单" in work_table.canonical_text
    assert "客户联系方式" not in work_table.canonical_text
    assert "customer_contact" not in work_table.canonical_text
    assert (
        work_table.content_hash
        == sha256(work_table.canonical_text.encode("utf-8")).hexdigest()
    )


def test_record_projection_excludes_sensitive_link_uuid_and_long_field() -> None:
    snapshot = _snapshot()
    projection = build_record_projection(
        snapshot,
        _work_record(),
        retrieval_scope_hash=RETRIEVAL_SCOPE_HASH,
        retrievable_field_ids=frozenset({CODE_ID, TITLE_ID, SUMMARY_ID, LINK_ID}),
        long_text_field_ids=frozenset({SUMMARY_ID}),
        field_positions={TITLE_ID: 0, CODE_ID: 1, SUMMARY_ID: 2, LINK_ID: 3},
    )

    assert projection.source_type == "record"
    assert projection.source_version == 3
    assert projection.canonical_text.startswith("[table] 工作项\n[record] MT-001")
    assert "Atlas checklist" in projection.canonical_text
    assert "等待范围确认" not in projection.canonical_text
    assert "hidden-secret@example.com" not in projection.canonical_text
    assert str(PROJECT_RECORD_ID) not in projection.canonical_text
    assert SENSITIVE_ID not in projection.field_ids
    assert LINK_ID not in projection.field_ids
    assert projection.scope_hash == RETRIEVAL_SCOPE_HASH


def test_long_field_projection_is_nfc_and_chunks_do_not_cross_records() -> None:
    decomposed = "Cafe\u0301 " + "范围待确认" * 12
    projections = build_record_field_projections(
        _snapshot(),
        _work_record(summary=decomposed),
        retrieval_scope_hash=RETRIEVAL_SCOPE_HASH,
        retrievable_field_ids=frozenset({SUMMARY_ID}),
        long_text_field_ids=frozenset({SUMMARY_ID}),
    )
    assert len(projections) == 1
    assert projections[0].source_type == "record_field"
    assert "Café" in projections[0].canonical_text

    chunks = chunk_projection(
        projections[0],
        token_counter=CharacterTokenCounter(),
        max_tokens=24,
        overlap_tokens=4,
    )
    assert len(chunks) > 1
    assert all(chunk.source_id == projections[0].source_id for chunk in chunks)
    assert all(chunk.record_id == WORK_RECORD_ID for chunk in chunks)
    assert all(chunk.field_ids == (SUMMARY_ID,) for chunk in chunks)
    assert all(chunk.end_token - chunk.start_token <= 24 for chunk in chunks)
    assert chunks[0].start_token == 0
    assert chunks[1].start_token == chunks[0].end_token - 4


def test_relation_projection_keeps_structured_direction_and_versions() -> None:
    edges = build_relation_projections(
        _snapshot(),
        retrieval_scope_hash=RETRIEVAL_SCOPE_HASH,
        records=(_work_record(), _project_record()),
        catalog=(
            AuthorizedRelationSpec(
                relation_id=f"relation:{LINK_ID}",
                link_source_table_id=WORK_TABLE_ID,
                link_field_id=LINK_ID,
                link_target_table_id=PROJECT_TABLE_ID,
            ),
        ),
    )

    assert len(edges) == 1
    edge = edges[0]
    assert edge.direction == "forward"
    assert edge.source_record_id == WORK_RECORD_ID
    assert edge.target_record_id == PROJECT_RECORD_ID
    assert edge.source_version == 3
    assert edge.target_version == 2
    assert edge.scope_hash == RETRIEVAL_SCOPE_HASH
