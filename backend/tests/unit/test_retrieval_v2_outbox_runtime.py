from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.config import Settings


def test_retrieval_outbox_runtime_is_default_off() -> None:
    try:
        from app.workers.retrieval_v2_outbox_runtime import (
            create_retrieval_v2_outbox_dispatcher,
        )
    except ImportError:
        pytest.fail("retrieval_v2_outbox_runtime_missing")

    with pytest.raises(RuntimeError, match="retrieval_v2_outbox_runtime_disabled"):
        create_retrieval_v2_outbox_dispatcher(
            session=object(),
            settings=Settings(),
            token_counter=object(),
            embedding_provider=object(),
            now=lambda: None,
        )


def test_retrieval_ready_query_is_type_and_workspace_filtered() -> None:
    try:
        from app.workers.retrieval_v2_outbox_runtime import (
            RETRIEVAL_V2_EVENT_TYPES,
            build_retrieval_v2_ready_query,
        )
    except ImportError:
        pytest.fail("retrieval_v2_outbox_runtime_missing")
    workspace_id = uuid4()

    statement = build_retrieval_v2_ready_query(
        workspace_ids=frozenset({workspace_id}),
        limit=17,
    )
    compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))

    assert "outbox_events.event_type IN" in compiled
    assert "workspace_id" in compiled
    assert str(workspace_id) in compiled
    assert "LIMIT 17" in compiled
    assert RETRIEVAL_V2_EVENT_TYPES == frozenset(
        {
            "stage12.retrieval_source.changed",
            "stage12.retrieval_projection.requested",
            "stage12.retrieval_projection.revoked",
            "stage12.retrieval_scope.bootstrap_requested",
        }
    )
