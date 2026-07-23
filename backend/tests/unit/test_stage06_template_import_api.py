import base64
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
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


def test_stage06_template_import_commit_rejects_duplicate_table_key_without_new_resources() -> None:
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
        client.headers["Idempotency-Key"] = "duplicate-table-key"
        workspace_id = client.post(
            "/workspaces",
            json={"name": "Acme", "owner_user_id": "owner-1"},
        ).json()["id"]
        base_response = client.post(
            f"/workspaces/{workspace_id}/base-initializations",
            json={"base_name": "CRM", "table_name": "Leads"},
        )
        base_id = base_response.json()["base"]["id"]
        existing_table_response = client.post(
            f"/bases/{base_id}/tables",
            json={"name": "Customers", "key": "customers"},
        )
        import_response = client.post(
            f"/workspaces/{workspace_id}/imports",
            json={
                "source_type": "csv",
                "file_name": "customers.csv",
                "content": "Name,Score\nAda,10\n",
                "created_by_user_id": "owner-1",
                "base_id": base_id,
            },
        )

        tables_before = len(uow.tables)
        fields_before = len(uow.fields)
        records_before = len(uow.records)
        commit_response = client.post(
            f"/imports/{import_response.json()['id']}/commit",
            json={
                "base_name": "CRM",
                "table_name": "Imported customers",
                "table_key": "customers",
                "field_mapping": [
                    {"source_key": "name", "target_key": "name", "field_type": "text"},
                    {"source_key": "score", "target_key": "score", "field_type": "number"},
                ],
            },
        )

    assert base_response.status_code == 201
    assert existing_table_response.status_code == 200
    assert import_response.status_code == 200
    assert commit_response.status_code == 409
    assert commit_response.json()["detail"]["code"] == "import_table_key_conflict"
    assert len(uow.tables) == tables_before
    assert len(uow.fields) == fields_before
    assert len(uow.records) == records_before


def test_stage06_template_import_commit_rejects_duplicate_mapping_targets_without_new_resources() -> None:
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
        client.headers["Idempotency-Key"] = "duplicate-mapping-target"
        workspace_id = client.post(
            "/workspaces",
            json={"name": "Acme", "owner_user_id": "owner-1"},
        ).json()["id"]
        client.headers["Idempotency-Key"] = "duplicate-mapping-target-import"
        import_response = client.post(
            f"/workspaces/{workspace_id}/imports",
            json={
                "source_type": "csv",
                "file_name": "customers.csv",
                "content": "Name,Score\nAda,10\n",
                "created_by_user_id": "owner-1",
            },
        )

        tables_before = len(uow.tables)
        fields_before = len(uow.fields)
        records_before = len(uow.records)
        commit_response = client.post(
            f"/imports/{import_response.json()['id']}/commit",
            json={
                "base_name": "Imported CRM",
                "table_name": "Customers",
                "table_key": "customers",
                "field_mapping": [
                    {"source_key": "name", "target_key": "customer", "field_type": "text"},
                    {"source_key": "score", "target_key": "customer", "field_type": "number"},
                ],
            },
        )

    assert import_response.status_code == 200
    assert commit_response.status_code == 422
    assert commit_response.json()["detail"]["code"] == "invalid_import_mapping"
    assert len(uow.tables) == tables_before
    assert len(uow.fields) == fields_before
    assert len(uow.records) == records_before


def test_stage06_template_import_commit_rejects_array_target_key_without_new_resources() -> None:
    uow, import_response, commit_response, counts_before = _commit_import_with_mapping(
        [
            {
                "source_key": "name",
                "target_key": ["customer"],
                "field_type": "text",
            }
        ]
    )

    assert import_response.status_code == 200
    assert commit_response.status_code == 422
    assert commit_response.json()["detail"]["code"] == "invalid_import_mapping"
    assert (len(uow.tables), len(uow.fields), len(uow.records)) == counts_before


def test_stage06_template_import_commit_rejects_object_source_key_without_new_resources() -> None:
    uow, import_response, commit_response, counts_before = _commit_import_with_mapping(
        [
            {
                "source_key": {"unexpected": "key"},
                "target_key": "customer",
                "field_type": "text",
            }
        ]
    )

    assert import_response.status_code == 200
    assert commit_response.status_code == 422
    assert commit_response.json()["detail"]["code"] == "invalid_import_mapping"
    assert (len(uow.tables), len(uow.fields), len(uow.records)) == counts_before


@pytest.mark.parametrize("field_type", [["text"], {"type": "text"}, None, ""])
def test_stage06_template_import_commit_rejects_non_string_or_empty_field_type_without_new_resources(
    field_type: object,
) -> None:
    uow, import_response, commit_response, counts_before = _commit_import_with_mapping(
        [
            {
                "source_key": "name",
                "target_key": "customer",
                "field_type": field_type,
            }
        ]
    )

    assert import_response.status_code == 200
    assert commit_response.status_code == 422
    assert commit_response.json()["detail"]["code"] == "unsupported_field_type"
    assert (len(uow.tables), len(uow.fields), len(uow.records)) == counts_before


@pytest.mark.parametrize("name", [{"display": "Customer"}, ["Customer"], None, ""])
def test_stage06_template_import_commit_rejects_non_string_or_empty_field_name_without_new_resources(
    name: object,
) -> None:
    uow, import_response, commit_response, counts_before = _commit_import_with_mapping(
        [
            {
                "source_key": "name",
                "target_key": "customer",
                "field_type": "text",
                "name": name,
            }
        ]
    )

    assert import_response.status_code == 200
    assert commit_response.status_code == 422
    assert commit_response.json()["detail"]["code"] == "invalid_import_mapping"
    assert (len(uow.tables), len(uow.fields), len(uow.records)) == counts_before


def _commit_import_with_mapping(
    field_mapping: list[dict[str, object]],
) -> tuple[InMemoryStage06PlatformUnitOfWork, object, object, tuple[int, int, int]]:
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
        client.headers["Idempotency-Key"] = "invalid-mapping-import"
        workspace_id = client.post(
            "/workspaces",
            json={"name": "Acme", "owner_user_id": "owner-1"},
        ).json()["id"]
        client.headers["Idempotency-Key"] = "invalid-mapping-import-job"
        import_response = client.post(
            f"/workspaces/{workspace_id}/imports",
            json={
                "source_type": "csv",
                "file_name": "customers.csv",
                "content": "Name,Score\nAda,10\n",
                "created_by_user_id": "owner-1",
            },
        )
        counts_before = (len(uow.tables), len(uow.fields), len(uow.records))
        client.headers["Idempotency-Key"] = "invalid-mapping-import-commit"
        commit_response = client.post(
            f"/imports/{import_response.json()['id']}/commit",
            json={
                "base_name": "Imported CRM",
                "table_name": "Customers",
                "table_key": "customers",
                "field_mapping": field_mapping,
            },
        )

    return uow, import_response, commit_response, counts_before


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
