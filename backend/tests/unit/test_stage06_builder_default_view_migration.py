from pathlib import Path

from app.models.stage06_platform import PlatformView


MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260710_0021_stage07_builder_defaults.py"
)


def test_builder_default_view_migration_has_linear_revision_chain() -> None:
    assert MIGRATION.exists()

    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision = "20260710_0021"' in source
    assert 'down_revision = "20260710_0020"' in source
    assert '"uq_views_one_default_per_table"' in source
    assert 'postgresql_where=sa.text("is_default IS TRUE")' in source


def test_platform_view_declares_one_default_per_table_partial_index() -> None:
    indexes = {index.name: index for index in PlatformView.__table__.indexes}
    default_index = indexes.get("uq_views_one_default_per_table")

    assert default_index is not None
    assert default_index.unique is True
    assert [column.name for column in default_index.columns] == ["table_id"]
    assert (
        str(default_index.dialect_options["postgresql"]["where"])
        == "is_default IS TRUE"
    )


def test_builder_default_view_migration_downgrade_removes_only_the_new_index() -> None:
    assert MIGRATION.exists()

    upgrade, downgrade = MIGRATION.read_text(encoding="utf-8").split(
        "def downgrade", 1
    )

    assert "drop_table" not in upgrade
    assert 'op.drop_index("uq_views_one_default_per_table", table_name="views")' in downgrade
