import pytest

from app.schemas.stage06_platform import (
    FormViewPresentationCommand,
    GridViewPresentationCommand,
    ViewFilterCondition,
    ViewSortRule,
)
from app.services.permissions import Actor
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    PlatformValidationError,
    create_base,
    create_field,
    create_form_view,
    create_table,
    create_workspace,
)
from app.services import stage06_platform


def test_canonical_presentation_rejects_more_than_twelve_filters_even_if_schema_is_bypassed() -> None:
    uow, table, _ = _table_with_v1_fields()
    command = GridViewPresentationCommand.model_construct(
        view_type="grid",
        visible_field_keys=["title"],
        filter_conjunction="and",
        filters=[
            ViewFilterCondition(field_key="title", operator="equals", value="x")
            for _ in range(13)
        ],
        sort_rules=[],
        group_by_field_key=None,
    )

    with pytest.raises(PlatformValidationError) as exc:
        stage06_platform.canonicalize_v1_presentation(
            uow,
            table.id,
            actor=_owner(),
            command=command,
        )

    assert exc.value.code == "view_filter_invalid"


def test_safe_v1_projection_omits_hidden_configured_field_and_query_metadata() -> None:
    uow, table, fields = _table_with_v1_fields()
    view = create_form_view(
        uow,
        uow.get_base(table.base_id).id,
        table.id,
        name="Restricted Grid",
        view_type="grid",
        config={
            "fields": ["title", "secret", "state"],
            "filters": [{"field_key": "secret", "operator": "equals", "value": "x"}],
            "sort_rules": [{"field_key": "secret", "direction": "asc"}],
            "group_by_field_key": "secret",
        },
    )

    projection = stage06_platform.build_v1_safe_view_projection(
        uow,
        view,
        actor=Actor(actor_type="user", actor_id="viewer-1", role="viewer"),
    )

    assert projection["visible_field_keys"] == ["title", "state"]
    assert projection["filters"] == []
    assert projection["sort_rules"] == []
    assert projection["group_by_field_key"] is None
    assert "secret" not in str(projection)
    assert "config" not in projection
    assert fields["secret"].key == "secret"


def test_canonical_presentation_enforces_f2_relation_and_lookup_eligibility() -> None:
    uow, table, _ = _table_with_v1_fields()

    numeric_lookup_sort = GridViewPresentationCommand.model_validate(
        {
            "view_type": "grid",
            "visible_field_keys": ["title", "lookup_sum"],
            "filters": [],
            "sort_rules": [{"field_key": "lookup_sum", "direction": "desc"}],
            "group_by_field_key": None,
        }
    )
    canonical = stage06_platform.canonicalize_v1_presentation(
        uow,
        table.id,
        actor=_owner(),
        command=numeric_lookup_sort,
    )
    assert canonical["sort_rules"] == [
        {"field_key": "lookup_sum", "direction": "desc"}
    ]

    relation_group = GridViewPresentationCommand.model_validate(
        {
            "view_type": "grid",
            "visible_field_keys": ["title", "related"],
            "filters": [],
            "sort_rules": [],
            "group_by_field_key": "related",
        }
    )
    with pytest.raises(PlatformValidationError) as group_exc:
        stage06_platform.canonicalize_v1_presentation(
            uow,
            table.id,
            actor=_owner(),
            command=relation_group,
        )
    assert group_exc.value.code == "view_group_invalid"

    nonnumeric_lookup_filter = GridViewPresentationCommand.model_validate(
        {
            "view_type": "grid",
            "visible_field_keys": ["title", "lookup_values"],
            "filters": [
                {"field_key": "lookup_values", "operator": "equals", "value": 1}
            ],
            "sort_rules": [],
            "group_by_field_key": None,
        }
    )
    with pytest.raises(PlatformValidationError) as filter_exc:
        stage06_platform.canonicalize_v1_presentation(
            uow,
            table.id,
            actor=_owner(),
            command=nonnumeric_lookup_filter,
        )
    assert filter_exc.value.code == "view_filter_invalid"


def test_canonical_form_requires_nonempty_readable_and_writable_fields() -> None:
    uow, table, _ = _table_with_v1_fields()
    create_field(
        uow,
        table.id,
        name="Read-only form field",
        key="read_only",
        field_type="text",
        permission_policy={"owner": "read"},
    )

    empty_form = FormViewPresentationCommand.model_construct(
        view_type="form",
        visible_field_keys=[],
        form_field_keys=[],
    )
    with pytest.raises(PlatformValidationError) as empty_exc:
        stage06_platform.canonicalize_v1_presentation(
            uow,
            table.id,
            actor=_owner(),
            command=empty_form,
        )
    assert empty_exc.value.code == "view_form_field_invalid"

    read_only_form = FormViewPresentationCommand.model_validate(
        {
            "view_type": "form",
            "visible_field_keys": ["read_only"],
            "form_field_keys": ["read_only"],
        }
    )
    with pytest.raises(PlatformValidationError) as read_only_exc:
        stage06_platform.canonicalize_v1_presentation(
            uow,
            table.id,
            actor=_owner(),
            command=read_only_form,
        )
    assert read_only_exc.value.code == "view_form_field_invalid"


def test_canonical_choice_filter_rejects_values_outside_safe_choices() -> None:
    uow, table, _ = _table_with_v1_fields()
    command = GridViewPresentationCommand.model_validate(
        {
            "view_type": "grid",
            "visible_field_keys": ["title", "state"],
            "filters": [{"field_key": "state", "operator": "is", "value": "closed"}],
            "sort_rules": [],
            "group_by_field_key": None,
        }
    )

    with pytest.raises(PlatformValidationError) as exc:
        stage06_platform.canonicalize_v1_presentation(
            uow,
            table.id,
            actor=_owner(),
            command=command,
        )

    assert exc.value.code == "view_filter_invalid"


def _table_with_v1_fields() -> tuple[InMemoryStage06PlatformUnitOfWork, object, dict[str, object]]:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    base = create_base(uow, workspace.id, name="CRM")
    table = create_table(uow, base.id, name="Customers", key="customers")
    fields = {
        "title": create_field(uow, table.id, name="Title", key="title", field_type="text"),
        "secret": create_field(
            uow,
            table.id,
            name="Secret",
            key="secret",
            field_type="text",
            permission_policy={"viewer": "hidden"},
        ),
        "state": create_field(
            uow,
            table.id,
            name="State",
            key="state",
            field_type="status",
            options={"choices": ["open"]},
        ),
        "related": create_field(
            uow,
            table.id,
            name="Related",
            key="related",
            field_type="linked_record",
        ),
        "lookup_sum": create_field(
            uow,
            table.id,
            name="Lookup sum",
            key="lookup_sum",
            field_type="lookup",
            options={"aggregation": "sum"},
        ),
        "lookup_values": create_field(
            uow,
            table.id,
            name="Lookup values",
            key="lookup_values",
            field_type="lookup",
            options={"aggregation": "values"},
        ),
    }
    return uow, table, fields


def _owner() -> Actor:
    return Actor(actor_type="user", actor_id="owner-1", role="owner")
