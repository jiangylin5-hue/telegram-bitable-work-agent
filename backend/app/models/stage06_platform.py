from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class Workspace(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workspaces"
    __table_args__ = (UniqueConstraint("slug", name="uq_workspaces_slug"),)

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), nullable=False)
    owner_user_id: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class WorkspaceMember(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "user_id",
            name="uq_workspace_members_workspace_user",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class Stage06TelegramBinding(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stage06_telegram_bindings"

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id"),
        nullable=False,
    )
    workspace_member_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspace_members.id", name="fk_stage06_binding_member"),
        nullable=True,
    )
    telegram_chat_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    telegram_user_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    binding_type: Mapped[str] = mapped_column(String(40), nullable=False)
    default_base_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("bases.id"),
        nullable=True,
    )
    default_digital_employee_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("digital_employees.id", name="fk_stage06_binding_employee"),
        nullable=True,
    )
    scope_policy: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")


class BitableBase(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bases"

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, default="blank")
    template_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class PlatformTable(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tables"
    __table_args__ = (
        UniqueConstraint("base_id", "key", name="uq_tables_base_key"),
    )

    base_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("bases.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    primary_field_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class PlatformField(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fields"
    __table_args__ = (
        UniqueConstraint("table_id", "key", name="uq_fields_table_key"),
    )

    table_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tables.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    field_type: Mapped[str] = mapped_column(String(40), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    unique: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    options: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    default_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    permission_policy: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    permission_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")


class PlatformRecord(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "records"

    table_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tables.id"),
        nullable=False,
    )
    record_values: Mapped[dict] = mapped_column("values", JSONB, nullable=False)
    record_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="active",
    )
    created_by_user_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    updated_by_user_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    @property
    def values(self) -> dict:
        return self.record_values


class RecordLink(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "record_links"

    source_table_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tables.id"),
        nullable=False,
    )
    source_record_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("records.id"),
        nullable=False,
    )
    source_field_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("fields.id"),
        nullable=False,
    )
    target_table_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tables.id"),
        nullable=False,
    )
    target_record_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("records.id"),
        nullable=False,
    )


class PlatformView(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "views"
    __table_args__ = (
        Index(
            "uq_views_one_default_per_table",
            "table_id",
            unique=True,
            postgresql_where=text("is_default IS TRUE"),
        ),
    )

    base_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("bases.id"),
        nullable=False,
    )
    table_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tables.id"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    view_type: Mapped[str] = mapped_column(String(40), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    permission_policy: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    owner_user_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    scope: Mapped[str] = mapped_column(
        String(40), nullable=False, default="system_default"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ViewMemberGrant(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "view_member_grants"
    __table_args__ = (
        UniqueConstraint(
            "view_id",
            "user_id",
            name="uq_view_member_grants_view_user",
        ),
    )

    view_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("views.id"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(String(120), nullable=False)
    access_level: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")


class PlatformForm(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "forms"

    view_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("views.id"),
        nullable=False,
    )
    table_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tables.id"),
        nullable=False,
    )
    form_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    submit_policy: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
