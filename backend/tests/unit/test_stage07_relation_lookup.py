from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.stage06_platform import (
    InitializeLookupFieldRequest,
    InitializeRelationFieldRequest,
    RelationCandidatePageResponse,
)


def test_f2_schema_initializer_models_forbid_raw_configuration_and_candidate_page_is_safe() -> None:
    relation = InitializeRelationFieldRequest.model_validate(
        {
            "name": "关联客户",
            "target_table_id": str(uuid4()),
            "required": True,
        }
    )

    assert relation.required is True
    with pytest.raises(ValidationError):
        InitializeLookupFieldRequest.model_validate(
            {
                "name": "金额",
                "source_relation_field_id": str(uuid4()),
                "target_field_id": str(uuid4()),
                "aggregation": "sum",
                "options": {},
            }
        )

    page = RelationCandidatePageResponse.model_validate(
        {
            "field_id": str(uuid4()),
            "records": [{"id": str(uuid4()), "label": "Acme"}],
            "next_cursor": None,
            "has_more": False,
        }
    )

    assert page.model_dump() == {
        "field_id": page.field_id,
        "records": [{"id": page.records[0].id, "label": "Acme"}],
        "next_cursor": None,
        "has_more": False,
    }
