from pydantic import BaseModel, Field


class ViewRecord(BaseModel):
    id: str
    fields: dict[str, object] = Field(default_factory=dict)


class ViewResponse(BaseModel):
    view_key: str
    records: list[ViewRecord]
    trace_id: str
