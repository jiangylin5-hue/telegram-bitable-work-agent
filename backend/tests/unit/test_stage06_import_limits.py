import pytest

from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    PlatformValidationError,
    create_workspace,
)
from app.services.stage06_templates import (
    ImportLimits,
    create_import_job_from_csv,
    validate_import_rows,
)


def test_stage06_csv_payload_over_five_mib_is_rejected_before_parse() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    content = "x" * (5 * 1024 * 1024 + 1)

    with pytest.raises(PlatformValidationError) as denied:
        create_import_job_from_csv(
            uow,
            workspace.id,
            file_name="large.csv",
            content=content,
            created_by_user_id="owner-1",
        )

    assert denied.value.code == "import_payload_limit_exceeded"
    assert uow.import_jobs == []


@pytest.mark.parametrize(
    ("rows", "limits", "code"),
    [
        ([{"a": "1"}, {"a": "2"}], ImportLimits(rows=1), "import_row_limit_exceeded"),
        ([{"a": "1", "b": "2"}], ImportLimits(columns=1), "import_column_limit_exceeded"),
        ([{"a": "long"}], ImportLimits(cell_chars=3), "import_cell_limit_exceeded"),
    ],
)
def test_stage06_import_shape_limits_are_enforced(
    rows: list[dict[str, str]],
    limits: ImportLimits,
    code: str,
) -> None:
    with pytest.raises(PlatformValidationError) as denied:
        validate_import_rows(rows, limits)

    assert denied.value.code == code


def test_stage06_import_preview_uses_twenty_rows() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    content = "name\n" + "\n".join(f"row-{index}" for index in range(25))

    job = create_import_job_from_csv(
        uow,
        workspace.id,
        file_name="rows.csv",
        content=content,
        created_by_user_id="owner-1",
    )

    assert len(job.preview_rows) == 20
