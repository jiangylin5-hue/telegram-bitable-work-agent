from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api.routes.reports import get_reporting_uow
from app.agents.mock_reporting import MockReportingAgent
from app.main import create_app
from app.models.cards import AccountCardBinding
from app.models.recharge import RechargeRecord
from app.models.reporting import AccountDailyMetric, CompanyDailyReport, CustomerDailyReport
from app.services.permissions import Actor
from app.services.reporting import (
    InMemoryReportingUnitOfWork,
    SqlAlchemyReportingUnitOfWork,
    generate_company_daily_report,
    generate_customer_daily_report,
)


class FakeScalarResult:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def __iter__(self):
        return iter(self.rows)


class FakeSqlAlchemySession:
    def __init__(self, rows_by_entity: dict[type, list[object]] | None = None) -> None:
        self.rows_by_entity = rows_by_entity or {}
        self.added: list[object] = []
        self.statements: list[object] = []

    def add(self, value: object) -> None:
        self.added.append(value)

    def scalars(self, statement: object) -> FakeScalarResult:
        self.statements.append(statement)
        entity = statement.column_descriptions[0]["entity"]
        return FakeScalarResult(self.rows_by_entity.get(entity, []))


def test_default_reporting_dependency_uses_sqlalchemy_uow() -> None:
    session = FakeSqlAlchemySession()

    uow = get_reporting_uow(session=session)

    assert isinstance(uow, SqlAlchemyReportingUnitOfWork)
    assert uow.session is session


def test_sqlalchemy_reporting_uow_uses_session_for_fact_reads_and_writes() -> None:
    day = date(2026, 7, 4)
    customer_id = uuid4()
    metric = _metric(
        customer_id=customer_id,
        account_asset_id=uuid4(),
        metric_date=day,
        spend_amount=Decimal("12.00"),
    )
    recharge = _recharge(
        customer_id=customer_id,
        amount=Decimal("1000.00"),
        readback_at=datetime(2026, 7, 4, 10, 30, tzinfo=timezone.utc),
    )
    binding = _card_binding(
        customer_id=customer_id,
        account_asset_id=uuid4(),
        binding_status="bound",
        bound_at=datetime(2026, 7, 4, 12, 30, tzinfo=timezone.utc),
    )
    session = FakeSqlAlchemySession(
        rows_by_entity={
            AccountDailyMetric: [metric],
            RechargeRecord: [recharge],
            AccountCardBinding: [binding],
        }
    )
    uow = SqlAlchemyReportingUnitOfWork(session)
    customer_report = CustomerDailyReport(
        id=uuid4(),
        customer_id=customer_id,
        report_date=day,
        report_payload={},
        visibility_scope={"customer_ids": [str(customer_id)]},
        delivery_status="draft",
        trace_id="report:customer",
    )
    company_report = CompanyDailyReport(
        id=uuid4(),
        report_date=day,
        report_payload={},
        delivery_status="draft",
        trace_id="report:company",
    )

    uow.add_metric(metric)
    uow.add_customer_report(customer_report)
    uow.add_company_report(company_report)

    assert uow.list_metrics_for_customer_on_date(customer_id, day) == [metric]
    assert uow.list_metrics_on_date(day) == [metric]
    assert uow.list_recharge_records_for_customer_on_date(customer_id, day) == [recharge]
    assert uow.list_recharge_records_on_date(day) == [recharge]
    assert uow.list_card_bindings_for_customer_on_date(customer_id, day) == [binding]
    assert uow.list_card_bindings_on_date(day) == [binding]
    assert session.added == [metric, customer_report, company_report]
    assert len(session.statements) == 6
    assert all(statement._where_criteria for statement in session.statements)


def test_customer_report_contains_only_requested_customer_metrics() -> None:
    day = date(2026, 7, 4)
    customer_a_id = uuid4()
    customer_b_id = uuid4()
    account_a_id = uuid4()
    account_b_id = uuid4()
    uow = InMemoryReportingUnitOfWork(
        metrics=[
            _metric(
                customer_id=customer_a_id,
                account_asset_id=account_a_id,
                metric_date=day,
                spend_amount=Decimal("25.30"),
            ),
            _metric(
                customer_id=customer_b_id,
                account_asset_id=account_b_id,
                metric_date=day,
                spend_amount=Decimal("80.00"),
            ),
        ],
    )
    actor = Actor(actor_type="user", actor_id=str(uuid4()), role="manager")

    report = generate_customer_daily_report(
        uow,
        actor=actor,
        customer_id=customer_a_id,
        report_date=day,
    )

    metrics = report.report_payload["metrics"]
    assert report.customer_id == customer_a_id
    assert len(metrics) == 1
    assert metrics[0]["customer_id"] == str(customer_a_id)
    assert metrics[0]["account_asset_id"] == str(account_a_id)
    assert metrics[0]["source"] == "mock_readback"
    assert metrics[0]["freshness_at"] == "2026-07-04T09:30:00+00:00"
    assert str(account_b_id) not in str(report.report_payload)
    assert uow.audit_events[-1].event_type == "customer_daily_report_generated"
    assert uow.audit_events[-1].entity_id == report.id


def test_customer_report_keeps_stale_spend_unknown_and_creates_risk_event() -> None:
    day = date(2026, 7, 4)
    customer_id = uuid4()
    metric = _metric(
        customer_id=customer_id,
        account_asset_id=uuid4(),
        metric_date=day,
        spend_amount=None,
        read_status="stale_data",
    )
    uow = InMemoryReportingUnitOfWork(metrics=[metric])
    actor = Actor(actor_type="user", actor_id=str(uuid4()), role="manager")

    report = generate_customer_daily_report(
        uow,
        actor=actor,
        customer_id=customer_id,
        report_date=day,
    )

    report_metric = report.report_payload["metrics"][0]
    assert report_metric["spend"]["amount"] is None
    assert report_metric["read_status"] == "stale_data"
    assert uow.risk_events[-1].risk_type == "stale_data"
    assert uow.risk_events[-1].source_metric_id == metric.id
    assert [event.event_type for event in uow.audit_events] == [
        "risk_event_created",
        "customer_daily_report_generated",
    ]


def test_mock_reporting_agent_lands_customer_report_on_report_table() -> None:
    day = date(2026, 7, 4)
    customer_id = uuid4()
    uow = InMemoryReportingUnitOfWork(
        metrics=[
            _metric(
                customer_id=customer_id,
                account_asset_id=uuid4(),
                metric_date=day,
                spend_amount=Decimal("12.00"),
            )
        ],
    )
    actor = Actor(
        actor_type="agent",
        actor_id="customer-reporting-agent",
        role="agent",
        customer_ids=frozenset({str(customer_id)}),
    )

    report = MockReportingAgent().generate_customer_report(
        uow,
        actor=actor,
        customer_id=customer_id,
        report_date=day,
    )

    assert uow.customer_reports == [report]
    assert report.report_payload["metrics"][0]["source"] == "mock_readback"


def test_customer_report_includes_same_day_recharge_records_and_binding_gap() -> None:
    day = date(2026, 7, 4)
    customer_id = uuid4()
    other_customer_id = uuid4()
    same_day_recharge = _recharge(
        customer_id=customer_id,
        amount=Decimal("1000.00"),
        readback_at=datetime(2026, 7, 4, 10, 30, tzinfo=timezone.utc),
    )
    other_customer_recharge = _recharge(
        customer_id=other_customer_id,
        amount=Decimal("999.00"),
        readback_at=datetime(2026, 7, 4, 10, 30, tzinfo=timezone.utc),
    )
    other_day_recharge = _recharge(
        customer_id=customer_id,
        amount=Decimal("500.00"),
        readback_at=datetime(2026, 7, 3, 10, 30, tzinfo=timezone.utc),
    )
    uow = InMemoryReportingUnitOfWork(
        metrics=[
            _metric(
                customer_id=customer_id,
                account_asset_id=uuid4(),
                metric_date=day,
                spend_amount=Decimal("12.00"),
            )
        ],
        recharge_records=[
            same_day_recharge,
            other_customer_recharge,
            other_day_recharge,
        ],
    )
    actor = Actor(actor_type="user", actor_id=str(uuid4()), role="manager")

    report = generate_customer_daily_report(
        uow,
        actor=actor,
        customer_id=customer_id,
        report_date=day,
    )

    assert report.report_payload["recharge_records"] == [
        {
            "recharge_record_id": str(same_day_recharge.id),
            "customer_id": str(customer_id),
            "amount": "1000.00",
            "currency": "USD",
            "collection_status": "confirmed",
            "execution_status": "succeeded",
            "readback_status": "failed",
            "freshness_at": "2026-07-04T10:30:00+00:00",
            "source": "recharge_records",
        }
    ]
    assert report.report_payload["card_binding_state"] == {
        "status": "not_available_in_stage_02",
        "source": "account_card_bindings",
        "reason": "no account_card_bindings facts for this customer/date",
    }


def test_customer_report_includes_same_day_card_binding_facts() -> None:
    day = date(2026, 7, 4)
    customer_id = uuid4()
    account_asset_id = uuid4()
    same_day_binding = _card_binding(
        customer_id=customer_id,
        account_asset_id=account_asset_id,
        binding_status="bound",
        bound_at=datetime(2026, 7, 4, 12, 30, tzinfo=timezone.utc),
    )
    failed_binding = _card_binding(
        customer_id=customer_id,
        account_asset_id=account_asset_id,
        binding_status="failed",
        bound_at=datetime(2026, 7, 4, 13, 30, tzinfo=timezone.utc),
        failure_reason="provider timeout",
    )
    other_day_binding = _card_binding(
        customer_id=customer_id,
        account_asset_id=account_asset_id,
        binding_status="bound",
        bound_at=datetime(2026, 7, 3, 12, 30, tzinfo=timezone.utc),
    )
    uow = InMemoryReportingUnitOfWork(
        metrics=[
            _metric(
                customer_id=customer_id,
                account_asset_id=account_asset_id,
                metric_date=day,
                spend_amount=Decimal("12.00"),
            )
        ],
        card_bindings=[
            same_day_binding,
            failed_binding,
            other_day_binding,
        ],
    )
    actor = Actor(actor_type="user", actor_id=str(uuid4()), role="manager")

    report = generate_customer_daily_report(
        uow,
        actor=actor,
        customer_id=customer_id,
        report_date=day,
    )

    assert report.report_payload["card_binding_state"] == {
        "status": "available",
        "source": "account_card_bindings",
        "record_count": 2,
        "status_counts": {"bound": 1, "failed": 1},
    }
    assert report.report_payload["card_bindings"] == [
        {
            "card_binding_id": str(same_day_binding.id),
            "customer_id": str(customer_id),
            "account_asset_id": str(account_asset_id),
            "binding_status": "bound",
            "one_card_one_account_policy": "strict",
            "freshness_at": "2026-07-04T12:30:00+00:00",
            "failure_reason": None,
            "source": "account_card_bindings",
        },
        {
            "card_binding_id": str(failed_binding.id),
            "customer_id": str(customer_id),
            "account_asset_id": str(account_asset_id),
            "binding_status": "failed",
            "one_card_one_account_policy": "strict",
            "freshness_at": "2026-07-04T13:30:00+00:00",
            "failure_reason": "[masked]",
            "source": "account_card_bindings",
        },
    ]


def test_company_report_generation_writes_audit_event() -> None:
    day = date(2026, 7, 4)
    customer_id = uuid4()
    uow = InMemoryReportingUnitOfWork(
        metrics=[
            _metric(
                customer_id=customer_id,
                account_asset_id=uuid4(),
                metric_date=day,
                spend_amount=Decimal("20.00"),
            )
        ],
    )
    actor = Actor(actor_type="user", actor_id=str(uuid4()), role="manager")

    report = generate_company_daily_report(
        uow,
        actor=actor,
        report_date=day,
    )

    assert uow.company_reports == [report]
    assert uow.audit_events[-1].event_type == "company_daily_report_generated"
    assert uow.audit_events[-1].entity_id == report.id


def test_company_report_includes_recharge_summary_for_report_date() -> None:
    day = date(2026, 7, 4)
    customer_a_id = uuid4()
    customer_b_id = uuid4()
    same_day_success = _recharge(
        customer_id=customer_a_id,
        amount=Decimal("1000.00"),
        readback_at=datetime(2026, 7, 4, 10, 30, tzinfo=timezone.utc),
        execution_status="succeeded",
        readback_status="failed",
    )
    same_day_queued = _recharge(
        customer_id=customer_b_id,
        amount=Decimal("500.00"),
        readback_at=datetime(2026, 7, 4, 11, 30, tzinfo=timezone.utc),
        execution_status="queued",
        readback_status="not_started",
    )
    other_day = _recharge(
        customer_id=customer_a_id,
        amount=Decimal("700.00"),
        readback_at=datetime(2026, 7, 3, 10, 30, tzinfo=timezone.utc),
    )
    uow = InMemoryReportingUnitOfWork(
        metrics=[],
        recharge_records=[same_day_success, same_day_queued, other_day],
    )
    actor = Actor(actor_type="user", actor_id=str(uuid4()), role="manager")

    report = generate_company_daily_report(
        uow,
        actor=actor,
        report_date=day,
    )

    assert report.report_payload["recharge_summary"] == {
        "record_count": 2,
        "amount_by_currency": {"USD": "1500.00"},
        "execution_status_counts": {"queued": 1, "succeeded": 1},
        "readback_status_counts": {"failed": 1, "not_started": 1},
        "source": "recharge_records",
    }


def test_company_report_includes_card_binding_summary_for_report_date() -> None:
    day = date(2026, 7, 4)
    customer_id = uuid4()
    same_day_bound = _card_binding(
        customer_id=customer_id,
        account_asset_id=uuid4(),
        binding_status="bound",
        bound_at=datetime(2026, 7, 4, 12, 30, tzinfo=timezone.utc),
    )
    same_day_failed = _card_binding(
        customer_id=customer_id,
        account_asset_id=uuid4(),
        binding_status="failed",
        bound_at=datetime(2026, 7, 4, 13, 30, tzinfo=timezone.utc),
    )
    other_day = _card_binding(
        customer_id=customer_id,
        account_asset_id=uuid4(),
        binding_status="bound",
        bound_at=datetime(2026, 7, 3, 12, 30, tzinfo=timezone.utc),
    )
    uow = InMemoryReportingUnitOfWork(
        metrics=[],
        card_bindings=[same_day_bound, same_day_failed, other_day],
    )
    actor = Actor(actor_type="user", actor_id=str(uuid4()), role="manager")

    report = generate_company_daily_report(
        uow,
        actor=actor,
        report_date=day,
    )

    assert report.report_payload["card_binding_summary"] == {
        "record_count": 2,
        "status_counts": {"bound": 1, "failed": 1},
        "source": "account_card_bindings",
    }


def test_customer_report_api_commits_generated_report() -> None:
    app = create_app()
    day = date(2026, 7, 4)
    customer_id = uuid4()
    uow = InMemoryReportingUnitOfWork(
        metrics=[
            _metric(
                customer_id=customer_id,
                account_asset_id=uuid4(),
                metric_date=day,
                spend_amount=Decimal("33.00"),
            )
        ],
    )
    app.dependency_overrides[get_reporting_uow] = lambda: uow

    with TestClient(app) as client:
        response = client.post(
            f"/reports/customer-daily/{customer_id}",
            params={"report_date": day.isoformat()},
        )

    assert response.status_code == 200
    assert response.json()["customer_id"] == str(customer_id)
    assert uow.committed is True


def _metric(
    *,
    customer_id: UUID,
    account_asset_id: UUID,
    metric_date: date,
    spend_amount: Decimal | None,
    read_status: str = "fresh",
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
        read_status=read_status,
    )


def _recharge(
    *,
    customer_id: UUID,
    amount: Decimal,
    readback_at: datetime,
    execution_status: str = "succeeded",
    readback_status: str = "failed",
) -> RechargeRecord:
    return RechargeRecord(
        id=uuid4(),
        service_record_id=uuid4(),
        customer_id=customer_id,
        account_asset_id=uuid4(),
        amount=amount,
        currency="USD",
        collection_status="confirmed",
        execution_status=execution_status,
        readback_status=readback_status,
        readback_at=readback_at,
        execution_ticket_id=uuid4(),
    )


def _card_binding(
    *,
    customer_id: UUID,
    account_asset_id: UUID,
    binding_status: str,
    bound_at: datetime,
    failure_reason: str | None = None,
) -> AccountCardBinding:
    return AccountCardBinding(
        id=uuid4(),
        customer_id=customer_id,
        account_asset_id=account_asset_id,
        payment_profile_id=uuid4(),
        binding_status=binding_status,
        one_card_one_account_policy="strict",
        service_record_id=uuid4(),
        execution_log_id=uuid4(),
        bound_at=bound_at,
        unbound_at=None,
        failure_reason=failure_reason,
        trace_id=f"binding:{account_asset_id}",
    )
