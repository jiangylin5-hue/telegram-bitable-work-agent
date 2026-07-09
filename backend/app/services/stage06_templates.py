import csv
from dataclasses import dataclass
from io import BytesIO, StringIO
import re
from typing import Any, Protocol
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from app.models.stage06_templates import (
    ImportJob,
    PlatformTemplate,
    TemplateInstallation,
)
from app.services.audit import record_audit_event
from app.services.permissions import Actor
from app.services.stage06_audit import sanitize_stage06_audit_state
from app.services.stage06_platform import (
    STAGE06_FIELD_TYPES,
    PlatformValidationError,
    Stage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_form_view,
    create_record,
    create_table,
    read_base,
)


class Stage06TemplateImportUnitOfWork(Stage06PlatformUnitOfWork, Protocol):
    pass


@dataclass(frozen=True)
class ImportLimits:
    csv_bytes: int = 5 * 1024 * 1024
    excel_bytes: int = 10 * 1024 * 1024
    rows: int = 10_000
    columns: int = 200
    cell_chars: int = 65_536
    preview_rows: int = 20


DEFAULT_IMPORT_LIMITS = ImportLimits()


@dataclass(frozen=True)
class ImportCommitResult:
    import_job_id: UUID
    status: str
    resource_map: dict[str, Any]


OFFICIAL_TEMPLATE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "key": "crm_customer_management",
        "name": "CRM / Customer Management",
        "category": "crm",
        "description": "Customers, status, owner and follow-up basics.",
        "version": "1.0.0",
        "manifest": {
            "base": {"name": "CRM"},
            "tables": [
                {
                    "key": "customers",
                    "name": "Customers",
                    "fields": [
                        {"key": "name", "name": "Name", "field_type": "text"},
                        {"key": "status", "name": "Status", "field_type": "status"},
                        {"key": "owner", "name": "Owner", "field_type": "user"},
                    ],
                    "views": [
                        {
                            "name": "Customer Grid",
                            "view_type": "grid",
                            "config": {"fields": ["name", "status", "owner"]},
                        }
                    ],
                    "records": [
                        {
                            "name": "Example Customer",
                            "status": "new",
                            "owner": "owner",
                        }
                    ],
                }
            ],
        },
    },
    {
        "key": "project_task",
        "name": "Project / Task",
        "category": "project",
        "description": "Projects, tasks, assignees, progress and due dates.",
        "version": "1.0.0",
        "manifest": {
            "base": {"name": "Projects"},
            "tables": [
                {
                    "key": "tasks",
                    "name": "Tasks",
                    "fields": [
                        {"key": "title", "name": "Title", "field_type": "text"},
                        {"key": "assignee", "name": "Assignee", "field_type": "user"},
                        {"key": "due", "name": "Due", "field_type": "date"},
                    ],
                    "views": [
                        {
                            "name": "Task Grid",
                            "view_type": "grid",
                            "config": {"fields": ["title", "assignee", "due"]},
                        }
                    ],
                    "records": [{"title": "Example Task", "assignee": "owner"}],
                }
            ],
        },
    },
    {
        "key": "customer_service_ticket",
        "name": "Customer Service / Ticket",
        "category": "ticket",
        "description": "Tickets, priority, status, handler and reply draft.",
        "version": "1.0.0",
        "manifest": {
            "base": {"name": "Customer Service"},
            "tables": [
                {
                    "key": "tickets",
                    "name": "Tickets",
                    "fields": [
                        {"key": "title", "name": "Title", "field_type": "text"},
                        {"key": "priority", "name": "Priority", "field_type": "status"},
                        {"key": "status", "name": "Status", "field_type": "status"},
                    ],
                    "views": [
                        {
                            "name": "Ticket Grid",
                            "view_type": "grid",
                            "config": {"fields": ["title", "priority", "status"]},
                        }
                    ],
                    "records": [{"title": "Example Ticket", "priority": "normal"}],
                }
            ],
        },
    },
    {
        "key": "inventory_asset",
        "name": "Inventory / Asset",
        "category": "inventory",
        "description": "Assets, assignment, condition and inventory status.",
        "version": "1.0.0",
        "manifest": {
            "base": {"name": "Inventory"},
            "tables": [
                {
                    "key": "assets",
                    "name": "Assets",
                    "fields": [
                        {"key": "name", "name": "Name", "field_type": "text"},
                        {"key": "status", "name": "Status", "field_type": "status"},
                        {"key": "owner", "name": "Owner", "field_type": "user"},
                    ],
                    "views": [
                        {
                            "name": "Asset Grid",
                            "view_type": "grid",
                            "config": {"fields": ["name", "status", "owner"]},
                        }
                    ],
                    "records": [{"name": "Example Asset", "status": "available"}],
                }
            ],
        },
    },
    {
        "key": "advertising_agency_sample",
        "name": "Advertising Agency Sample",
        "category": "sample",
        "description": "Historical ad-agency workflow sample, not the default path.",
        "version": "1.0.0",
        "manifest": {
            "base": {"name": "Advertising Agency Sample"},
            "tables": [
                {
                    "key": "accounts",
                    "name": "Accounts",
                    "fields": [
                        {"key": "name", "name": "Name", "field_type": "text"},
                        {"key": "status", "name": "Status", "field_type": "status"},
                    ],
                    "views": [
                        {
                            "name": "Account Grid",
                            "view_type": "grid",
                            "config": {"fields": ["name", "status"]},
                        }
                    ],
                    "records": [{"name": "Example Account", "status": "sample"}],
                }
            ],
        },
    },
)


def list_templates(
    uow: Stage06TemplateImportUnitOfWork,
) -> list[PlatformTemplate]:
    official = [_official_template(definition) for definition in OFFICIAL_TEMPLATE_DEFINITIONS]
    official_ids = {template.id for template in official}
    custom = [template for template in uow.list_templates() if template.id not in official_ids]
    return official + sorted(custom, key=lambda template: template.name)


def create_import_job_from_csv(
    uow: Stage06TemplateImportUnitOfWork,
    workspace_id: UUID,
    *,
    file_name: str,
    content: str | bytes,
    created_by_user_id: str,
    base_id: UUID | None = None,
) -> ImportJob:
    _validate_import_payload_size(content, DEFAULT_IMPORT_LIMITS.csv_bytes)
    rows = _parse_csv_rows(content)
    validate_import_rows(rows, DEFAULT_IMPORT_LIMITS)
    return _create_import_job(
        uow,
        workspace_id,
        base_id=base_id,
        source_type="csv",
        file_name=file_name,
        rows=rows,
        created_by_user_id=created_by_user_id,
    )


def create_import_job_from_excel(
    uow: Stage06TemplateImportUnitOfWork,
    workspace_id: UUID,
    *,
    file_name: str,
    content: bytes,
    created_by_user_id: str,
    base_id: UUID | None = None,
) -> ImportJob:
    _validate_import_payload_size(content, DEFAULT_IMPORT_LIMITS.excel_bytes)
    rows = _parse_xlsx_rows(content)
    validate_import_rows(rows, DEFAULT_IMPORT_LIMITS)
    return _create_import_job(
        uow,
        workspace_id,
        base_id=base_id,
        source_type="excel",
        file_name=file_name,
        rows=rows,
        created_by_user_id=created_by_user_id,
    )


def commit_import_job(
    uow: Stage06TemplateImportUnitOfWork,
    import_job_id: UUID,
    *,
    base_name: str,
    table_name: str,
    table_key: str,
    field_mapping: list[dict[str, Any]] | None,
    actor: Actor,
) -> ImportCommitResult:
    job = _require_import_job(uow, import_job_id)
    if job.status != "awaiting_confirmation":
        raise PlatformValidationError("import_job_invalid_state", str(import_job_id))

    mapping = field_mapping or _default_field_mapping(job.detected_schema)
    _validate_field_mapping(mapping)
    base = (
        create_base(uow, job.workspace_id, name=base_name, actor=actor)
        if job.base_id is None
        else read_base(uow, job.base_id)
    )
    table = create_table(uow, base.id, name=table_name, key=table_key, actor=actor)
    for item in mapping:
        create_field(
            uow,
            table.id,
            name=item.get("name") or _titleize(item["target_key"]),
            key=item["target_key"],
            field_type=item["field_type"],
            actor=actor,
        )

    for row in job.file_ref["rows"]:
        values = {
            item["target_key"]: _coerce_value(
                row.get(item["source_key"]),
                item["field_type"],
            )
            for item in mapping
        }
        create_record(uow, table.id, values=values, actor=actor)

    resource_map = {
        "base_id": str(base.id),
        "table_id": str(table.id),
        "table_key": table.key,
        "record_count": len(job.file_ref["rows"]),
    }
    job.base_id = base.id
    job.mapping = mapping
    job.status = "committed"
    _record_package3_audit(
        uow,
        actor=actor,
        event_type="stage06.import_committed",
        entity_type="import_job",
        entity_id=job.id,
        after_state={"resource_map": resource_map},
    )
    return ImportCommitResult(
        import_job_id=job.id,
        status=job.status,
        resource_map=resource_map,
    )


def read_import_job(
    uow: Stage06TemplateImportUnitOfWork,
    import_job_id: UUID,
) -> ImportJob:
    return _require_import_job(uow, import_job_id)


def install_template(
    uow: Stage06TemplateImportUnitOfWork,
    workspace_id: UUID,
    template_id: UUID,
    *,
    installed_by_user_id: str,
    actor: Actor,
) -> TemplateInstallation:
    template = _get_or_persist_template(uow, template_id)
    manifest = template.manifest
    base = create_base(
        uow,
        workspace_id,
        name=manifest["base"]["name"],
        actor=actor,
    )
    resource_map: dict[str, Any] = {
        "base_id": str(base.id),
        "tables": {},
        "fields": {},
        "views": {},
        "records": {},
    }
    for table_spec in manifest.get("tables", []):
        table = create_table(
            uow,
            base.id,
            name=table_spec["name"],
            key=table_spec["key"],
            actor=actor,
        )
        resource_map["tables"][table.key] = str(table.id)
        resource_map["fields"][table.key] = {}
        for field_spec in table_spec.get("fields", []):
            field = create_field(
                uow,
                table.id,
                name=field_spec["name"],
                key=field_spec["key"],
                field_type=field_spec["field_type"],
                options=field_spec.get("options"),
                actor=actor,
            )
            resource_map["fields"][table.key][field.key] = str(field.id)
        resource_map["views"][table.key] = []
        for view_spec in table_spec.get("views", []):
            view = create_form_view(
                uow,
                base.id,
                table.id,
                name=view_spec["name"],
                view_type=view_spec["view_type"],
                config=view_spec.get("config", {}),
                actor=actor,
            )
            resource_map["views"][table.key].append(str(view.id))
        resource_map["records"][table.key] = []
        for record_values in table_spec.get("records", []):
            record = create_record(uow, table.id, values=record_values, actor=actor)
            resource_map["records"][table.key].append(str(record.id))

    installation = TemplateInstallation(
        id=uuid4(),
        workspace_id=workspace_id,
        base_id=base.id,
        template_id=template.id,
        template_version=template.version,
        resource_map=resource_map,
        installed_by_user_id=installed_by_user_id,
    )
    uow.add_template_installation(installation)
    _record_package3_audit(
        uow,
        actor=actor,
        event_type="stage06.template_installed",
        entity_type="template_installation",
        entity_id=installation.id,
        after_state={"template_id": str(template.id), "resource_map": resource_map},
    )
    return installation


def save_base_as_template(
    uow: Stage06TemplateImportUnitOfWork,
    base_id: UUID,
    *,
    name: str,
    category: str,
    description: str,
    created_by_user_id: str,
) -> PlatformTemplate:
    base = read_base(uow, base_id)
    manifest_tables = []
    for table in uow.list_tables(base.id):
        fields = uow.list_fields(table.id)
        views = uow.list_views(table.id)
        records = uow.list_records(table.id)
        manifest_tables.append(
            {
                "key": table.key,
                "name": table.name,
                "fields": [
                    {
                        "key": field.key,
                        "name": field.name,
                        "field_type": field.field_type,
                        "options": field.options,
                    }
                    for field in fields
                ],
                "views": [
                    {
                        "name": view.name,
                        "view_type": view.view_type,
                        "config": view.config,
                    }
                    for view in views
                ],
                "records": [dict(record.values) for record in records],
            }
        )
    template = PlatformTemplate(
        id=uuid4(),
        name=name,
        category=category,
        description=description,
        version="1.0.0",
        manifest={
            "base": {"name": base.name},
            "tables": manifest_tables,
            "created_by_user_id": created_by_user_id,
        },
        status="draft",
    )
    uow.add_template(template)
    return template


def _create_import_job(
    uow: Stage06TemplateImportUnitOfWork,
    workspace_id: UUID,
    *,
    base_id: UUID | None,
    source_type: str,
    file_name: str,
    rows: list[dict[str, Any]],
    created_by_user_id: str,
) -> ImportJob:
    if not rows:
        raise PlatformValidationError("import_has_no_rows", file_name)
    _require_workspace(uow, workspace_id)
    if base_id is not None:
        base = read_base(uow, base_id)
        if base.workspace_id != workspace_id:
            raise PlatformValidationError("resource_scope_mismatch", "import_base_workspace")
    detected_schema = _infer_schema(rows)
    job = ImportJob(
        id=uuid4(),
        workspace_id=workspace_id,
        base_id=base_id,
        source_type=source_type,
        file_ref={"file_name": file_name, "rows": rows},
        detected_schema=detected_schema,
        preview_rows=rows[: DEFAULT_IMPORT_LIMITS.preview_rows],
        mapping=[],
        status="awaiting_confirmation",
        created_by_user_id=created_by_user_id,
    )
    uow.add_import_job(job)
    return job


def _parse_csv_rows(content: str | bytes) -> list[dict[str, Any]]:
    text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames:
        raise PlatformValidationError("import_missing_header", "csv")
    return _normalize_rows(reader.fieldnames, [dict(row) for row in reader])


def _parse_xlsx_rows(content: bytes) -> list[dict[str, Any]]:
    with ZipFile(BytesIO(content)) as archive:
        required_size = sum(
            item.file_size
            for item in archive.infolist()
            if item.filename == "xl/sharedStrings.xml"
            or item.filename.startswith("xl/worksheets/")
        )
        if required_size > DEFAULT_IMPORT_LIMITS.excel_bytes:
            raise PlatformValidationError(
                "import_payload_limit_exceeded",
                "excel_uncompressed_content",
            )
        sheet_name = _first_sheet_name(archive)
        shared_strings = _shared_strings(archive)
        sheet_rows = _read_sheet_rows(archive.read(sheet_name), shared_strings)
    if not sheet_rows:
        raise PlatformValidationError("import_missing_header", "excel")
    headers = [str(value or "") for value in sheet_rows[0]]
    data_rows = [
        {headers[index]: value for index, value in enumerate(row) if index < len(headers)}
        for row in sheet_rows[1:]
    ]
    return _normalize_rows(headers, data_rows)


def _first_sheet_name(archive: ZipFile) -> str:
    for name in archive.namelist():
        if name.startswith("xl/worksheets/") and name.endswith(".xml"):
            return name
    raise PlatformValidationError("import_missing_sheet", "excel")


def _shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(node.itertext()) for node in root]


def _read_sheet_rows(sheet_xml: bytes, shared_strings: list[str]) -> list[list[Any]]:
    root = ET.fromstring(sheet_xml)
    rows: list[list[Any]] = []
    for row in _iter_by_local_name(root, "row"):
        values: dict[int, Any] = {}
        for cell in _children_by_local_name(row, "c"):
            column = _column_index(cell.attrib.get("r", "A1"))
            values[column] = _cell_value(cell, shared_strings)
        if values:
            max_column = max(values)
            rows.append([values.get(index, "") for index in range(1, max_column + 1)])
    return rows


def _cell_value(cell: ET.Element, shared_strings: list[str]) -> Any:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        inline_text = next(_iter_by_local_name(cell, "t"), None)
        return "" if inline_text is None else "".join(inline_text.itertext())
    value_node = next(_iter_by_local_name(cell, "v"), None)
    if value_node is None or value_node.text is None:
        return ""
    if cell_type == "s":
        index = int(value_node.text)
        return shared_strings[index] if index < len(shared_strings) else ""
    return value_node.text


def _iter_by_local_name(element: ET.Element, local_name: str) -> Any:
    return (node for node in element.iter() if _local_name(node.tag) == local_name)


def _children_by_local_name(element: ET.Element, local_name: str) -> list[ET.Element]:
    return [node for node in list(element) if _local_name(node.tag) == local_name]


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _column_index(cell_ref: str) -> int:
    letters = re.sub(r"[^A-Z]", "", cell_ref.upper())
    index = 0
    for char in letters:
        index = index * 26 + ord(char) - 64
    return index or 1


def _normalize_rows(
    headers: list[str],
    raw_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    keys = [_unique_key(_slugify(header), index) for index, header in enumerate(headers)]
    rows: list[dict[str, Any]] = []
    for raw_row in raw_rows:
        rows.append(
            {
                keys[index]: raw_row.get(header, "")
                for index, header in enumerate(headers)
                if keys[index]
            }
        )
    return rows


def validate_import_rows(
    rows: list[dict[str, Any]],
    limits: ImportLimits = DEFAULT_IMPORT_LIMITS,
) -> None:
    if len(rows) > limits.rows:
        raise PlatformValidationError("import_row_limit_exceeded", str(len(rows)))
    maximum_columns = max((len(row) for row in rows), default=0)
    if maximum_columns > limits.columns:
        raise PlatformValidationError(
            "import_column_limit_exceeded",
            str(maximum_columns),
        )
    for row in rows:
        for value in row.values():
            if len(str(value)) > limits.cell_chars:
                raise PlatformValidationError(
                    "import_cell_limit_exceeded",
                    str(limits.cell_chars),
                )


def _validate_import_payload_size(content: str | bytes, maximum: int) -> None:
    size = len(content.encode("utf-8")) if isinstance(content, str) else len(content)
    if size > maximum:
        raise PlatformValidationError("import_payload_limit_exceeded", str(maximum))


def _infer_schema(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    schema = []
    for key in rows[0]:
        values = [row.get(key) for row in rows]
        schema.append(
            {
                "key": key,
                "name": _titleize(key),
                "field_type": _infer_field_type(values),
            }
        )
    return schema


def _infer_field_type(values: list[Any]) -> str:
    non_empty = [str(value).strip() for value in values if str(value).strip()]
    if non_empty and all(_is_bool(value) for value in non_empty):
        return "checkbox"
    if non_empty and all(_is_number(value) for value in non_empty):
        return "number"
    if non_empty and all(_is_date(value) for value in non_empty):
        return "date"
    return "text"


def _default_field_mapping(schema: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "source_key": field["key"],
            "target_key": field["key"],
            "field_type": field["field_type"],
            "name": field["name"],
        }
        for field in schema
    ]


def _validate_field_mapping(mapping: list[dict[str, Any]]) -> None:
    for item in mapping:
        if item.get("field_type") not in STAGE06_FIELD_TYPES:
            raise PlatformValidationError("unsupported_field_type", str(item))
        if not item.get("source_key") or not item.get("target_key"):
            raise PlatformValidationError("invalid_import_mapping", str(item))


def _coerce_value(value: Any, field_type: str) -> Any:
    if value is None or value == "":
        return None
    if field_type == "number":
        number = float(value)
        return int(number) if number.is_integer() else number
    if field_type == "checkbox":
        return str(value).strip().lower() in {"true", "1", "yes", "y"}
    return value


def _is_number(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def _is_bool(value: str) -> bool:
    return value.strip().lower() in {"true", "false", "1", "0", "yes", "no", "y", "n"}


def _is_date(value: str) -> bool:
    return re.match(r"^\d{4}-\d{2}-\d{2}", value.strip()) is not None


def _get_or_persist_template(
    uow: Stage06TemplateImportUnitOfWork,
    template_id: UUID,
) -> PlatformTemplate:
    template = uow.get_template(template_id)
    if template is not None:
        return template
    for definition in OFFICIAL_TEMPLATE_DEFINITIONS:
        official = _official_template(definition)
        if official.id == template_id:
            uow.add_template(official)
            return official
    raise PlatformValidationError("template_not_found", str(template_id))


def _official_template(definition: dict[str, Any]) -> PlatformTemplate:
    return PlatformTemplate(
        id=uuid5(NAMESPACE_URL, f"stage06-template:{definition['key']}"),
        name=definition["name"],
        category=definition["category"],
        description=definition["description"],
        version=definition["version"],
        manifest=definition["manifest"],
        status="published",
    )


def _require_import_job(
    uow: Stage06TemplateImportUnitOfWork,
    import_job_id: UUID,
) -> ImportJob:
    job = uow.get_import_job(import_job_id)
    if job is None:
        raise PlatformValidationError("import_job_not_found", str(import_job_id))
    return job


def _require_workspace(
    uow: Stage06TemplateImportUnitOfWork,
    workspace_id: UUID,
) -> None:
    if uow.get_workspace(workspace_id) is None:
        raise PlatformValidationError("workspace_not_found", str(workspace_id))


def _record_package3_audit(
    uow: Stage06TemplateImportUnitOfWork,
    *,
    actor: Actor,
    event_type: str,
    entity_type: str,
    entity_id: UUID,
    after_state: dict[str, Any],
) -> None:
    record_audit_event(
        getattr(uow, "session", uow),
        trace_id=f"stage06:{entity_type}:{entity_id}",
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        after_state=sanitize_stage06_audit_state(after_state),
        permission_snapshot={"role": actor.role, "actor_type": actor.actor_type},
    )


def _slugify(value: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in value)
    return "-".join(part for part in slug.split("-") if part) or "field"


def _titleize(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split("_"))


def _unique_key(key: str, index: int) -> str:
    return key or f"field_{index + 1}"
