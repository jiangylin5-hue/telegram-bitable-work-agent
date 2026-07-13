from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.stage07_team_bot_knowledge import TeamBotSummaryRequest


def test_team_bot_summary_request_is_closed_and_bounded() -> None:
    payload = {
        "base_id": str(uuid4()),
        "view_id": str(uuid4()),
        "instruction": "summarize the current team knowledge",
    }

    assert TeamBotSummaryRequest.model_validate(payload).model_dump() == payload

    with pytest.raises(ValidationError):
        TeamBotSummaryRequest.model_validate({**payload, "records": []})
    with pytest.raises(ValidationError):
        TeamBotSummaryRequest.model_validate({**payload, "instruction": "x" * 601})
