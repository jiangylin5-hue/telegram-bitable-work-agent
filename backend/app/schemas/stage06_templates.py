from typing import Any

from pydantic import BaseModel, Field


class TemplateResponse(BaseModel):
    id: str
    name: str
    category: str
    description: str
    version: str
    status: str


class TemplateListResponse(BaseModel):
    templates: list[TemplateResponse]


class InstallTemplateRequest(BaseModel):
    template_id: str
    installed_by_user_id: str


class TemplateInstallationResponse(BaseModel):
    id: str
    workspace_id: str
    base_id: str
    template_id: str
    template_version: str
    resource_map: dict[str, Any]


class CreateImportRequest(BaseModel):
    source_type: str
    file_name: str
    content: str
    created_by_user_id: str
    base_id: str | None = None


class ImportJobResponse(BaseModel):
    id: str
    workspace_id: str
    base_id: str | None = None
    source_type: str
    detected_schema: list[dict[str, Any]]
    preview_rows: list[dict[str, Any]]
    mapping: list[dict[str, Any]]
    status: str
    error_summary: str | None = None


class CommitImportRequest(BaseModel):
    base_name: str
    table_name: str
    table_key: str
    field_mapping: list[dict[str, Any]] | None = Field(default=None)


class ImportCommitResponse(BaseModel):
    import_job_id: str
    status: str
    resource_map: dict[str, Any]


class SaveBaseAsTemplateRequest(BaseModel):
    name: str
    category: str = "custom"
    description: str
    created_by_user_id: str
