from uuid import UUID

import pytest

from app.schemas.agent_specialist_results import (
    StructuredFactSetV1,
    specialist_payload_sha256,
)
from app.services.agent_claim_graph import (
    ActionDependencyV1,
    ClaimInputV1,
    ObjectiveOutcomeInputV1,
    build_claim_graph,
)


SCOPE = "a" * 64
TABLE_ID = UUID("36000000-0000-4000-8000-000000000001")
RECORD_ID = UUID("36000000-0000-4000-8000-000000000002")
FIELD_ID = UUID("36000000-0000-4000-8000-000000000003")


def _facts(*, value: object, version: int, evidence: str) -> StructuredFactSetV1:
    payload = {
        "version": "structured-fact-set.v1",
        "objective_id": "facts",
        "records": (
            {
                "record_id": RECORD_ID,
                "table_id": TABLE_ID,
                "values": ({"field_id": FIELD_ID, "value": value},),
            },
        ),
        "groups": (),
        "aggregates": (),
        "relation_paths": (),
        "source_versions": (
            {
                "table_id": TABLE_ID,
                "record_id": RECORD_ID,
                "record_version": version,
            },
        ),
        "evidence_refs": (evidence,),
        "scope_hash": SCOPE,
        "schema_hash": "b" * 64,
        "complete": True,
        "truncated": False,
    }
    payload["content_hash"] = specialist_payload_sha256(payload)
    return StructuredFactSetV1.model_validate(payload)


def _claim(
    *,
    objective: str,
    value: object,
    version: int,
    evidence: str,
) -> ClaimInputV1:
    return ClaimInputV1(
        objective_id=objective,
        subject_ref=f"record:{RECORD_ID}",
        predicate=f"field:{FIELD_ID}",
        value=value,
        evidence_ids=(evidence,),
        source_version=version,
    )


def test_claim_graph_merges_duplicates_and_marks_older_version_stale() -> None:
    graph = build_claim_graph(
        claims=(
            _claim(objective="obj-1", value="blocked", version=1, evidence="ev-1"),
            _claim(objective="obj-2", value="blocked", version=2, evidence="ev-2"),
            _claim(objective="obj-3", value="open", version=1, evidence="ev-3"),
        ),
        outcomes=(
            ObjectiveOutcomeInputV1("obj-1", "completed", True),
            ObjectiveOutcomeInputV1("obj-2", "completed", True),
            ObjectiveOutcomeInputV1("obj-3", "completed", False),
        ),
        actions=(),
        scope_hash=SCOPE,
        source_artifacts=(
            _facts(value="blocked", version=1, evidence="ev-1"),
            _facts(value="blocked", version=2, evidence="ev-2"),
            _facts(value="open", version=1, evidence="ev-3"),
        ),
    )

    blocked = next(item for item in graph.claims if item.value == "blocked")
    opened = next(item for item in graph.claims if item.value == "open")
    assert blocked.status == "valid"
    assert blocked.source_version == 2
    assert blocked.objective_ids == ("obj-1", "obj-2")
    assert blocked.evidence_ids == ("ev-1", "ev-2")
    assert opened.status == "stale"


def test_same_version_conflict_never_selects_winner_and_denies_action() -> None:
    graph = build_claim_graph(
        claims=(
            _claim(objective="obj-1", value="blocked", version=2, evidence="ev-1"),
            _claim(objective="obj-2", value="open", version=2, evidence="ev-2"),
        ),
        outcomes=(
            ObjectiveOutcomeInputV1("obj-1", "completed", True),
            ObjectiveOutcomeInputV1("obj-2", "completed", True),
        ),
        actions=(
            ActionDependencyV1(
                slot_id="slot-1",
                proposal_status="proposed",
                required_claim_refs=((f"record:{RECORD_ID}", f"field:{FIELD_ID}"),),
            ),
        ),
        scope_hash=SCOPE,
        source_artifacts=(
            _facts(value="blocked", version=2, evidence="ev-1"),
            _facts(value="open", version=2, evidence="ev-2"),
        ),
    )

    assert {item.status for item in graph.claims} == {"conflicted"}
    assert graph.action_statuses[0].status == "conflicted"
    assert graph.action_statuses[0].reason_code == "conflicted_claim"


def test_required_failure_blocks_while_optional_failure_and_deadline_degrade() -> None:
    graph = build_claim_graph(
        claims=(),
        outcomes=(
            ObjectiveOutcomeInputV1("required", "failed", True, "query_failed"),
            ObjectiveOutcomeInputV1("optional", "failed", False, "risk_failed"),
            ObjectiveOutcomeInputV1("deadline", "deadline", False),
        ),
        actions=(),
        scope_hash=SCOPE,
        source_artifacts=(),
    )

    statuses = {item.objective_id: item for item in graph.objective_statuses}
    assert statuses["required"].status == "failed"
    assert statuses["optional"].status == "degraded"
    assert statuses["deadline"].status == "degraded"
    assert statuses["deadline"].reason_code == "deadline_exhausted"


@pytest.mark.parametrize(
    ("value", "version", "evidence"),
    (
        ("不存在的值", 3, "ev-1"),
        ("阻塞", 99, "ev-1"),
        ("阻塞", 3, "ev-invented"),
    ),
)
def test_claim_graph_rejects_claim_not_sealed_by_typed_facts(
    value: object,
    version: int,
    evidence: str,
) -> None:
    facts = _facts(value="阻塞", version=3, evidence="ev-1")

    with pytest.raises(ValueError, match="claim_graph_claim_unsupported"):
        build_claim_graph(
            claims=(
                ClaimInputV1(
                    objective_id="facts",
                    subject_ref=f"record:{RECORD_ID}",
                    predicate=f"field:{FIELD_ID}",
                    value=value,
                    evidence_ids=(evidence,),
                    source_version=version,
                ),
            ),
            outcomes=(ObjectiveOutcomeInputV1("facts", "completed", True),),
            actions=(),
            scope_hash=SCOPE,
            source_artifacts=(facts,),
        )
