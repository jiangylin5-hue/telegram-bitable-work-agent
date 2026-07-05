from uuid import uuid4

from app.services.account_inventory import (
    InMemoryAccountInventoryUnitOfWork,
    activate_inventory_account,
    confirm_account_assignment,
    create_inventory_account,
    propose_account_assignment,
)
from app.services.permissions import Actor, PermissionDenied


def test_assignment_requires_human_confirmation() -> None:
    uow = InMemoryAccountInventoryUnitOfWork()
    production_actor = Actor(
        actor_type="user",
        actor_id=str(uuid4()),
        role="production",
    )
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

    assert assignment.assignment_status == "proposed"
    assert account.inventory_status == "unused"

    confirmed = confirm_account_assignment(
        uow,
        actor=production_actor,
        assignment_id=assignment.id,
    )

    assert confirmed.assignment_status == "confirmed"
    assert str(confirmed.confirmed_by_user_id) == production_actor.actor_id
    assert account.inventory_status == "allocated"
    assert account.assigned_customer_id == customer_id
    assert uow.status_events[-1].event_type == "assigned"
    assert uow.audit_events[-1].event_type == "inventory_account_assigned"
    assert uow.audit_events[-1].entity_id == account.id


def test_agent_cannot_confirm_assignment() -> None:
    uow = InMemoryAccountInventoryUnitOfWork()
    production_actor = Actor(
        actor_type="user",
        actor_id=str(uuid4()),
        role="production",
    )
    agent_actor = Actor(actor_type="agent", actor_id="account-inventory-agent", role="agent")
    account = create_inventory_account(
        uow,
        actor=production_actor,
        platform="meta",
        external_account_id="act_2001",
        production_batch_id="batch-1",
    )
    assignment = propose_account_assignment(
        uow,
        actor=agent_actor,
        account_inventory_id=account.id,
        customer_id=uuid4(),
    )

    try:
        confirm_account_assignment(
            uow,
            actor=agent_actor,
            assignment_id=assignment.id,
        )
    except PermissionDenied:
        pass
    else:
        raise AssertionError("agent confirmation should be denied")

    assert assignment.assignment_status == "proposed"
    assert account.inventory_status == "unused"
    assert uow.audit_events[-1].event_type == "permission_denied"


def test_agent_cannot_activate_allocated_inventory_account() -> None:
    uow = InMemoryAccountInventoryUnitOfWork()
    production_actor = Actor(
        actor_type="user",
        actor_id=str(uuid4()),
        role="production",
    )
    agent_actor = Actor(actor_type="agent", actor_id="account-inventory-agent", role="agent")
    account = create_inventory_account(
        uow,
        actor=production_actor,
        platform="meta",
        external_account_id="act_2001",
        production_batch_id="batch-1",
    )
    assignment = propose_account_assignment(
        uow,
        actor=agent_actor,
        account_inventory_id=account.id,
        customer_id=uuid4(),
    )
    confirm_account_assignment(
        uow,
        actor=production_actor,
        assignment_id=assignment.id,
    )

    try:
        activate_inventory_account(
            uow,
            actor=agent_actor,
            account_inventory_id=account.id,
            reason="agent attempted activation",
        )
    except PermissionDenied:
        pass
    else:
        raise AssertionError("agent activation should be denied")

    assert account.inventory_status == "allocated"
    assert uow.status_events[-1].event_type == "assigned"
    assert uow.audit_events[-1].event_type == "permission_denied"
