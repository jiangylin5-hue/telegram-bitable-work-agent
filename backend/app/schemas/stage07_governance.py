from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class _GovernanceReadModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GovernanceMemberResponse(_GovernanceReadModel):
    id: str
    user_id: str
    role: str
    status: str


class GovernanceMemberPageResponse(_GovernanceReadModel):
    workspace_id: str
    members: list[GovernanceMemberResponse]
    next_cursor: str | None = None
    has_more: bool = False


class GovernanceAuditEventResponse(_GovernanceReadModel):
    id: str
    occurred_at: datetime
    actor_type: Literal["user", "digital_employee", "system"]
    event_type: str
    entity_type: str


class GovernanceAuditPageResponse(_GovernanceReadModel):
    base_id: str
    events: list[GovernanceAuditEventResponse]
    next_cursor: str | None = None
    has_more: bool = False
