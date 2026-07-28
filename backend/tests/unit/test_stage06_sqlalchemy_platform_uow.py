from uuid import uuid4

from app.models.stage06_platform import PlatformField
from app.services.stage06_platform import SqlAlchemyStage06PlatformUnitOfWork


class _FieldSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.flush_count = 0

    def add(self, value: object) -> None:
        self.added.append(value)

    def flush(self) -> None:
        self.flush_count += 1


def test_sqlalchemy_uow_flushes_field_before_following_record_validation() -> None:
    session = _FieldSession()
    uow = SqlAlchemyStage06PlatformUnitOfWork(session)  # type: ignore[arg-type]
    field = PlatformField(
        id=uuid4(),
        table_id=uuid4(),
        name="Ticket",
        key="ticket",
        field_type="text",
        required=False,
        unique=False,
        options={},
        default_value=None,
        permission_policy={},
        permission_version=1,
        order_index=0,
        status="active",
    )

    uow.add_field(field)

    assert session.added == [field]
    assert session.flush_count == 1
