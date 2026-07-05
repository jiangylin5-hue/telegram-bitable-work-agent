from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid
from uuid import UUID

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class TableView(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "table_views"
    __table_args__ = (UniqueConstraint("view_key", name="uq_table_views_view_key"),)

    view_key: Mapped[str] = mapped_column(String(120), nullable=False)
    table_name: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)


class ViewColumn(UuidPrimaryKeyMixin, Base):
    __tablename__ = "view_columns"
    __table_args__ = (
        UniqueConstraint(
            "table_view_id",
            "field_name",
            name="uq_view_columns_view_field",
        ),
    )

    table_view_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("table_views.id"),
        nullable=False,
    )
    field_name: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    field_type: Mapped[str] = mapped_column(String(60), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ViewFilter(UuidPrimaryKeyMixin, Base):
    __tablename__ = "view_filters"

    table_view_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("table_views.id"),
        nullable=False,
    )
    field_name: Mapped[str] = mapped_column(String(120), nullable=False)
    operator: Mapped[str] = mapped_column(String(40), nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class FieldPermission(UuidPrimaryKeyMixin, Base):
    __tablename__ = "field_permissions"
    __table_args__ = (
        UniqueConstraint(
            "table_name",
            "field_name",
            "role",
            name="uq_field_permissions_table_field_role",
        ),
    )

    table_name: Mapped[str] = mapped_column(String(120), nullable=False)
    field_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    can_view: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AutomationRule(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "automation_rules"

    view_key: Mapped[str] = mapped_column(String(120), nullable=False)
    trigger_event: Mapped[str] = mapped_column(String(120), nullable=False)
    target_event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    rule_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
