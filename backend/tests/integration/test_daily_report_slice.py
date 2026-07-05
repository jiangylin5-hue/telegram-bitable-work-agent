from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from app.models.reporting import AccountDailyMetric
from app.services.permissions import Actor, PermissionDenied
from app.services.reporting import (
    InMemoryReportingUnitOfWork,
    generate_company_daily_report,
    get_company_report_for_actor,
)


def test_company_report_is_visible_to_manager_and_denied_to_sales() -> None:
    day = date(2026, 7, 4)
    customer_a_id = uuid4()
    customer_b_id = uuid4()
    uow = InMemoryReportingUnitOfWork(
        metrics=[
            _metric(
                customer_id=customer_a_id,
                account_asset_id=uuid4(),
                metric_date=day,
                spend_amount=Decimal("20.00"),
            ),
            _metric(
                customer_id=customer_b_id,
                account_asset_id=uuid4(),
                metric_date=day,
                spend_amount=Decimal("30.00"),
            ),
        ],
    )
    manager = Actor(actor_type="user", actor_id=str(uuid4()), role="manager")
    sales = Actor(
        actor_type="user",
        actor_id=str(uuid4()),
        role="sales",
        customer_ids=frozenset({str(customer_a_id)}),
    )

    report = generate_company_daily_report(uow, actor=manager, report_date=day)
    visible_report = get_company_report_for_actor(uow, actor=manager, report=report)

    assert len(visible_report.report_payload["customers"]) == 2
    assert visible_report.report_payload["total_spend_by_currency"]["USD"] == "50.00"

    try:
        get_company_report_for_actor(uow, actor=sales, report=report)
    except PermissionDenied:
        pass
    else:
        raise AssertionError("sales should not view company daily report")

    assert uow.audit_events[-1].event_type == "permission_denied"


def _metric(
    *,
    customer_id: UUID,
    account_asset_id: UUID,
    metric_date: date,
    spend_amount: Decimal,
) -> AccountDailyMetric:
    return AccountDailyMetric(
        id=uuid4(),
        account_asset_id=account_asset_id,
        customer_id=customer_id,
        metric_date=metric_date,
        balance_amount=Decimal("100.00"),
        balance_currency="USD",
        spend_amount=spend_amount,
        spend_currency="USD",
        freshness_at=datetime(2026, 7, 4, 9, 30, tzinfo=timezone.utc),
        source="mock_readback",
        read_status="fresh",
    )
