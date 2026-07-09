import base64
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient

from app.api.deps import get_system_actor
from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.api.routes.stage06_templates import get_stage06_template_import_uow
from app.main import create_app
from app.services.permissions import Actor
from app.services.stage06_platform import InMemoryStage06PlatformUnitOfWork


def test_stage06_template_import_api_lists_installs_and_imports_csv() -> None:
    app = create_app()
    uow = InMemoryStage06PlatformUnitOfWork()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[get_stage06_template_import_uow] = lambda: uow
    app.dependency_overrides[get_system_actor] = lambda: Actor(
        actor_type="user",
        actor_id="owner-1",
        role="owner",
    )

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = "owner-1"
        client.headers["Idempotency-Key"] = "template-import-api"
        workspace_response = client.post(
            "/workspaces",
            json={"name": "Acme", "owner_user_id": "owner-1"},
        )
        workspace_id = workspace_response.json()["id"]

        templates_response = client.get("/templates")
        crm_template_id = next(
            template["id"]
            for template in templates_response.json()["templates"]
            if template["category"] == "crm"
        )

        installation_response = client.post(
            f"/workspaces/{workspace_id}/template-installations",
            json={"template_id": crm_template_id, "installed_by_user_id": "owner-1"},
        )

        import_response = client.post(
            f"/workspaces/{workspace_id}/imports",
            json={
                "source_type": "csv",
                "file_name": "customers.csv",
                "content": "Name,Score\nAda,10\n",
                "created_by_user_id": "owner-1",
            },
        )
        import_job_id = import_response.json()["id"]

        commit_response = client.post(
            f"/imports/{import_job_id}/commit",
            json={
                "base_name": "Imported CRM",
                "table_name": "Customers",
                "table_key": "customers_imported",
                "field_mapping": [
                    {
                        "source_key": "name",
                        "target_key": "name",
                        "field_type": "text",
                    },
                    {
                        "source_key": "score",
                        "target_key": "score",
                        "field_type": "number",
                    },
                ],
            },
        )

    assert templates_response.status_code == 200
    assert templates_response.json()["templates"][0]["category"] != "sample"
    assert installation_response.status_code == 200
    assert installation_response.json()["resource_map"]["tables"]["customers"]
    assert import_response.status_code == 200
    assert import_response.json()["status"] == "awaiting_confirmation"
    assert commit_response.status_code == 200
    assert commit_response.json()["status"] == "committed"
    assert commit_response.json()["resource_map"]["table_key"] == "customers_imported"


def test_stage06_template_import_api_imports_excel_after_preview_confirmation() -> None:
    app = create_app()
    uow = InMemoryStage06PlatformUnitOfWork()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[get_stage06_template_import_uow] = lambda: uow
    app.dependency_overrides[get_system_actor] = lambda: Actor(
        actor_type="user",
        actor_id="owner-1",
        role="owner",
    )

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = "owner-1"
        client.headers["Idempotency-Key"] = "template-import-excel"
        workspace_id = client.post(
            "/workspaces",
            json={"name": "Acme", "owner_user_id": "owner-1"},
        ).json()["id"]
        import_response = client.post(
            f"/workspaces/{workspace_id}/imports",
            json={
                "source_type": "excel",
                "file_name": "tasks.xlsx",
                "content": base64.b64encode(
                    _simple_xlsx_bytes([["Title", "Due"], ["Launch", "2026-07-10"]])
                ).decode("ascii"),
                "created_by_user_id": "owner-1",
            },
        )
        import_job_id = import_response.json()["id"]
        commit_response = client.post(
            f"/imports/{import_job_id}/commit",
            json={
                "base_name": "Imported Projects",
                "table_name": "Tasks",
                "table_key": "tasks",
                "field_mapping": [
                    {"source_key": "title", "target_key": "title", "field_type": "text"},
                    {"source_key": "due", "target_key": "due", "field_type": "date"},
                ],
            },
        )

    assert import_response.status_code == 200
    assert import_response.json()["status"] == "awaiting_confirmation"
    assert import_response.json()["preview_rows"] == [
        {"title": "Launch", "due": "2026-07-10"}
    ]
    assert commit_response.status_code == 200
    assert uow.records[0].values == {"title": "Launch", "due": "2026-07-10"}


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
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return output.getvalue()


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name
