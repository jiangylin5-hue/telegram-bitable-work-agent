from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.routes.inventory import get_account_inventory_uow
from app.main import create_app
from app.models.accounts import AccountAssignment, AccountInventory, AccountStatusEvent
from app.services.account_inventory import (
    InMemoryAccountInventoryUnitOfWork,
    SqlAlchemyAccountInventoryUnitOfWork,
    activate_inventory_account,
    confirm_account_assignment,
    create_inventory_account,
    list_inventory_accounts_by_status,
    list_unused_inventory_accounts,
    propose_account_assignment,
)
from app.services.permissions import Actor


class FakeScalarResult:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def __iter__(self):
        return iter(self.rows)


class FakeSqlAlchemySession:
    def __init__(self, *, rows: list[object] | None = None) -> None:
        self.rows = list(rows or [])
        self.added: list[object] = []
        self.statements: list[object] = []
        self.objects_by_key: dict[tuple[type, object], object] = {}

    def add(self, value: object) -> None:
        self.added.append(value)

    def get(self, model: type, object_id: object) -> object | None:
        return self.objects_by_key.get((model, object_id))

    def scalars(self, statement: object) -> FakeScalarResult:
        self.statements.append(statement)
        return FakeScalarResult(self.rows)


def test_default_inventory_dependency_uses_sqlalchemy_uow() -> None:
    session = FakeSqlAlchemySession()

    uow = get_account_inventory_uow(session=session)

    assert isinstance(uow, SqlAlchemyAccountInventoryUnitOfWork)
    assert uow.session is session


def test_sqlalchemy_inventory_uow_uses_session_for_reads_and_writes() -> None:
    account = make_inventory_account()
    assignment_id = uuid4()
    session = FakeSqlAlchemySession(rows=[account])
    session.objects_by_key[(type(account), account.id)] = account
    uow = SqlAlchemyAccountInventoryUnitOfWork(session)

    uow.add_inventory_account(account)
    uow.add_status_event(make_status_event(account))
    uow.add_assignment(make_assignment(account, assignment_id))

    assert uow.get_inventory_account(account.id) is account
    assert uow.list_inventory_accounts() == [account]
    assert len(session.added) == 3
    assert len(session.statements) == 1


def test_production_creates_unused_inventory_account_with_status_event() -> None:
    uow = InMemoryAccountInventoryUnitOfWork()
    actor = Actor(actor_type="user", actor_id=str(uuid4()), role="production")

    account = create_inventory_account(
        uow,
        actor=actor,
        platform="meta",
        external_account_id="act_2001",
        production_batch_id="batch-1",
    )

    assert account.inventory_status == "unused"
    assert account.external_account_id == "act_2001"
    assert len(uow.status_events) == 1
    assert uow.status_events[0].event_type == "produced"
    assert list_unused_inventory_accounts(uow) == [account]
    assert uow.audit_events[-1].event_type == "inventory_account_created"
    assert uow.audit_events[-1].entity_id == account.id


def test_inventory_api_returns_unused_accounts() -> None:
    app = create_app()
    uow = InMemoryAccountInventoryUnitOfWork()
    actor = Actor(actor_type="user", actor_id=str(uuid4()), role="production")
    create_inventory_account(
        uow,
        actor=actor,
        platform="meta",
        external_account_id="act_2001",
        production_batch_id="batch-1",
    )
    app.dependency_overrides[get_account_inventory_uow] = lambda: uow

    with TestClient(app) as client:
        response = client.get("/inventory/accounts?status=unused")

    assert response.status_code == 200
    assert response.json()["records"][0]["external_account_id"] == "act_2001"
    assert response.json()["records"][0]["inventory_status"] == "unused"


def test_inventory_status_query_can_answer_assigned_customer_and_current_status() -> None:
    uow = InMemoryAccountInventoryUnitOfWork()
    production_actor = Actor(actor_type="user", actor_id=str(uuid4()), role="production")
    agent_actor = Actor(actor_type="agent", actor_id="account-inventory-agent", role="agent")
    account = create_inventory_account(
        uow,
        actor=production_actor,
        platform="meta",
        external_account_id="act_2001",
        production_batch_id="batch-1",
    )
    other_account = create_inventory_account(
        uow,
        actor=production_actor,
        platform="meta",
        external_account_id="act_2002",
        production_batch_id="batch-1",
    )
    customer_id = uuid4()
    assignment = propose_account_assignment(
        uow,
        actor=agent_actor,
        account_inventory_id=account.id,
        customer_id=customer_id,
    )
    confirm_account_assignment(
        uow,
        actor=production_actor,
        assignment_id=assignment.id,
    )

    allocated_accounts = list_inventory_accounts_by_status(
        uow,
        status="allocated",
        customer_id=customer_id,
    )

    assert allocated_accounts == [account]
    assert allocated_accounts[0].assigned_customer_id == customer_id
    assert other_account not in allocated_accounts


def test_production_can_activate_allocated_inventory_account_with_status_event() -> None:
    uow = InMemoryAccountInventoryUnitOfWork()
    production_actor = Actor(actor_type="user", actor_id=str(uuid4()), role="production")
    agent_actor = Actor(actor_type="agent", actor_id="account-inventory-agent", role="agent")
    account = create_inventory_account(
        uow,
        actor=production_actor,
        platform="meta",
        external_account_id="act_2001",
        production_batch_id="batch-1",
    )
    customer_id = uuid4()
    assignment = propose_account_assignment(
        uow,
        actor=agent_actor,
        account_inventory_id=account.id,
        customer_id=customer_id,
    )
    confirm_account_assignment(
        uow,
        actor=production_actor,
        assignment_id=assignment.id,
    )

    activated = activate_inventory_account(
        uow,
        actor=production_actor,
        account_inventory_id=account.id,
        reason="meta readback confirmed account can run",
    )

    assert activated.inventory_status == "activated"
    assert activated.assigned_customer_id == customer_id
    assert activated.status_reason == "meta readback confirmed account can run"
    assert uow.status_events[-1].event_type == "activated"
    assert uow.status_events[-1].before_status == "allocated"
    assert uow.status_events[-1].after_status == "activated"
    assert uow.status_events[-1].customer_id == customer_id
    assert uow.audit_events[-1].event_type == "inventory_account_activated"
    assert uow.audit_events[-1].entity_id == account.id


def test_inventory_api_can_filter_by_status_and_customer() -> None:
    app = create_app()
    uow = InMemoryAccountInventoryUnitOfWork()
    production_actor = Actor(actor_type="user", actor_id=str(uuid4()), role="production")
    agent_actor = Actor(actor_type="agent", actor_id="account-inventory-agent", role="agent")
    account = create_inventory_account(
        uow,
        actor=production_actor,
        platform="meta",
        external_account_id="act_2001",
        production_batch_id="batch-1",
    )
    customer_id = uuid4()
    assignment = propose_account_assignment(
        uow,
        actor=agent_actor,
        account_inventory_id=account.id,
        customer_id=customer_id,
    )
    confirm_account_assignment(
        uow,
        actor=production_actor,
        assignment_id=assignment.id,
    )
    app.dependency_overrides[get_account_inventory_uow] = lambda: uow

    with TestClient(app) as client:
        response = client.get(
            f"/inventory/accounts?status=allocated&customer_id={customer_id}"
        )

    assert response.status_code == 200
    assert response.json()["records"] == [
        {
            "id": str(account.id),
            "platform": "meta",
            "external_account_id": "act_2001",
            "inventory_status": "allocated",
            "assigned_customer_id": str(customer_id),
            "assigned_at": account.assigned_at.isoformat(),
            "status_reason": None,
        }
    ]


def make_inventory_account() -> AccountInventory:
    return AccountInventory(
        id=uuid4(),
        platform="meta",
        external_account_id="act_2001",
        inventory_status="unused",
        production_batch_id="batch-1",
    )


def make_status_event(account: AccountInventory) -> AccountStatusEvent:
    return AccountStatusEvent(
        id=uuid4(),
        account_inventory_id=account.id,
        event_type="produced",
        before_status=None,
        after_status="unused",
        actor_type="user",
        actor_id=str(uuid4()),
        created_at=account.created_at,
    )


def make_assignment(
    account: AccountInventory,
    assignment_id,
) -> AccountAssignment:
    return AccountAssignment(
        id=assignment_id,
        account_inventory_id=account.id,
        customer_id=uuid4(),
        assignment_status="proposed",
        assigned_at=account.created_at,
        trace_id=f"assignment:{account.id}",
    )
