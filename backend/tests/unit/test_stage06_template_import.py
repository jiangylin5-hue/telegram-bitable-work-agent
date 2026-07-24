from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from app.services.permissions import Actor
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_form_view,
    create_record,
    create_table,
    create_workspace,
)
from app.services.stage06_templates import (
    commit_import_job,
    create_import_job_from_csv,
    create_import_job_from_excel,
    install_template,
    list_templates,
    save_base_as_template,
)


def test_stage06_csv_import_previews_then_commits_records_after_confirmation() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")

    job = create_import_job_from_csv(
        uow,
        workspace.id,
        file_name="customers.csv",
        content="Name,Score,Active\nAda,10,true\nLin,8,false\n",
        created_by_user_id="owner-1",
    )

    assert job.status == "awaiting_confirmation"
    assert uow.tables == []
    assert [field["field_type"] for field in job.detected_schema] == [
        "text",
        "number",
        "checkbox",
    ]

    result = commit_import_job(
        uow,
        job.id,
        base_name="Imported CRM",
        table_name="Customers",
        table_key="customers",
        field_mapping=[
            {"source_key": "name", "target_key": "name", "field_type": "text"},
            {"source_key": "score", "target_key": "score", "field_type": "number"},
            {"source_key": "active", "target_key": "active", "field_type": "checkbox"},
        ],
        actor=Actor(actor_type="user", actor_id="owner-1", role="owner"),
    )

    assert job.status == "committed"
    assert result.resource_map["table_key"] == "customers"
    assert [field.key for field in uow.fields] == ["name", "score", "active"]
    assert uow.records[0].values == {"name": "Ada", "score": 10, "active": True}
    assert uow.records[1].values == {"name": "Lin", "score": 8, "active": False}
    assert uow.audit_events[-1].event_type == "stage06.import_committed"


def test_stage06_import_recognizes_common_business_status_and_choice_columns() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")

    job = create_import_job_from_csv(
        uow,
        workspace.id,
        file_name="customer_pipeline.csv",
        content="客户名称,状态,优先级,预计金额\n晨光,跟进中,高,68000\n",
        created_by_user_id="owner-1",
    )

    assert [field["field_type"] for field in job.detected_schema] == [
        "text",
        "status",
        "single_select",
        "number",
    ]

    result = commit_import_job(
        uow,
        job.id,
        base_name="Stage09 UI 验收样例",
        table_name="客户管道",
        table_key="customer_pipeline",
        field_mapping=None,
        actor=Actor(actor_type="user", actor_id="owner-1", role="owner"),
    )

    assert result.resource_map["record_count"] == 1
    assert [field.field_type for field in uow.fields] == [
        "text",
        "status",
        "single_select",
        "number",
    ]


def test_stage06_excel_import_previews_then_commits_records_after_confirmation() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")

    job = create_import_job_from_excel(
        uow,
        workspace.id,
        file_name="tasks.xlsx",
        content=_simple_xlsx_bytes(
            [
                ["Title", "Due"],
                ["Launch", "2026-07-10"],
            ]
        ),
        created_by_user_id="owner-1",
    )

    assert job.status == "awaiting_confirmation"
    assert job.preview_rows == [{"title": "Launch", "due": "2026-07-10"}]

    result = commit_import_job(
        uow,
        job.id,
        base_name="Imported Projects",
        table_name="Tasks",
        table_key="tasks",
        field_mapping=[
            {"source_key": "title", "target_key": "title", "field_type": "text"},
            {"source_key": "due", "target_key": "due", "field_type": "date"},
        ],
        actor=Actor(actor_type="user", actor_id="owner-1", role="owner"),
    )

    assert result.import_job_id == job.id
    assert uow.records[0].values == {"title": "Launch", "due": "2026-07-10"}


def test_stage06_official_templates_are_generic_first_and_install_ordinary_resources() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")

    templates = list_templates(uow)
    crm_template = next(template for template in templates if template.category == "crm")

    assert templates[0].category != "sample"
    assert templates[-1].category == "sample"

    installation = install_template(
        uow,
        workspace.id,
        crm_template.id,
        installed_by_user_id="owner-1",
        actor=Actor(actor_type="user", actor_id="owner-1", role="owner"),
    )

    assert installation.template_id == crm_template.id
    assert installation.base_id == uow.bases[0].id
    assert installation.resource_map["base_id"] == str(uow.bases[0].id)
    assert {table.key for table in uow.tables} == {"customers"}
    assert {field.key for field in uow.fields} >= {"name", "status", "owner"}
    assert uow.views[0].view_type == "grid"
    assert uow.records[0].values["name"] == "Example Customer"
    assert uow.audit_events[-1].event_type == "stage06.template_installed"


def test_stage06_save_base_as_template_creates_custom_manifest() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    base = create_base(uow, workspace.id, name="Ops")
    table = create_table(uow, base.id, name="Tasks", key="tasks")
    create_field(uow, table.id, name="Title", key="title", field_type="text")
    create_form_view(
        uow,
        base.id,
        table.id,
        name="Task Grid",
        view_type="grid",
        config={"fields": ["title"]},
    )
    create_record(uow, table.id, values={"title": "Launch"})

    template = save_base_as_template(
        uow,
        base.id,
        name="Ops Template",
        category="custom",
        description="Reusable ops base",
        created_by_user_id="owner-1",
    )

    assert template.category == "custom"
    assert template.manifest["base"]["name"] == "Ops"
    assert template.manifest["tables"][0]["key"] == "tasks"
    assert template.manifest["tables"][0]["records"] == [{"title": "Launch"}]


def _simple_xlsx_bytes(rows: list[list[str]]) -> bytes:
    sheet_rows = []
    for row_number, row in enumerate(rows, start=1):
        cells = []
        for column_number, value in enumerate(row, start=1):
            cell_ref = f"{_column_name(column_number)}{row_number}"
            cells.append(
                f'<c r="{cell_ref}" t="inlineStr"><is><t>{value}</t></is></c>'
            )
        sheet_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheets><sheet name=\"Sheet1\" sheetId=\"1\" r:id=\"rId1\" /></sheets>"
        "</workbook>"
    )
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return output.getvalue()


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name
