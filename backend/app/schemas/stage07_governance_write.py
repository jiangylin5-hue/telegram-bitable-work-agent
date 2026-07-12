from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt


GovernanceRole = Literal["owner", "admin", "builder", "operator", "viewer"]
GovernanceAssignableRole = Literal["admin", "builder", "operator", "viewer"]
GovernanceFieldPermissionMode = Literal["hidden", "read", "write"]


class _GovernanceWriteModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GovernanceEditableMemberResponse(_GovernanceWriteModel):
    id: str
    user_id: str
    role: GovernanceRole
    status: Literal["active"]
    version: StrictInt = Field(ge=1)
    assignable_roles: list[GovernanceAssignableRole] = Field(min_length=1)


class GovernanceEditableMemberPageResponse(_GovernanceWriteModel):
    workspace_id: str
    members: list[GovernanceEditableMemberResponse]
    next_cursor: str | None = None
    has_more: bool = False


class GovernanceMemberRoleRequest(_GovernanceWriteModel):
    role: GovernanceAssignableRole
    expected_version: StrictInt = Field(ge=1)


class GovernanceMemberRoleReceipt(_GovernanceWriteModel):
    id: str
    user_id: str
    role: GovernanceRole
    status: Literal["active"]
    version: StrictInt = Field(ge=1)


class GovernanceFieldPermissionResponse(_GovernanceWriteModel):
    id: str
    key: str
    label: str
    field_type: str
    policy: dict[GovernanceRole, GovernanceFieldPermissionMode]
    permission_version: StrictInt = Field(ge=1)


class GovernanceFieldPermissionListResponse(_GovernanceWriteModel):
    table_id: str
    fields: list[GovernanceFieldPermissionResponse]


class GovernanceFieldPermissionRequest(_GovernanceWriteModel):
    expected_permission_version: StrictInt = Field(ge=1)
    policy: dict[GovernanceRole, GovernanceFieldPermissionMode]


class GovernanceFieldPermissionReceipt(_GovernanceWriteModel):
    id: str
    key: str
    policy: dict[GovernanceRole, GovernanceFieldPermissionMode]
    permission_version: StrictInt = Field(ge=1)
