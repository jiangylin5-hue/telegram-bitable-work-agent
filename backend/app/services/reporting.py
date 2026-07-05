from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.cards import AccountCardBinding
from app.models.recharge import RechargeRecord
from app.models.reporting import (
    AccountDailyMetric,
    CompanyDailyReport,
    CustomerDailyReport,
    RiskEvent,
)
from app.services.audit import record_audit_event
from app.services.permissions import (
    Actor,
    PermissionDenied,
    assert_action_allowed,
    can_view_customer_record,
)


class ReportingStateError(RuntimeError):
    pass


class ReportingUnitOfWork(Protocol):
    def add_metric(self, metric: AccountDailyMetric) -> None:
        pass

    def add_risk_event(self, event: RiskEvent) -> None:
        pass

    def add_customer_report(self, report: CustomerDailyReport) -> None:
        pass

    def add_company_report(self, report: CompanyDailyReport) -> None:
        pass

    def list_metrics_for_customer_on_date(
        self,
        customer_id: UUID,
        metric_date: date,
    ) -> list[AccountDailyMetric]:
        pass

    def list_metrics_on_date(self, metric_date: date) -> list[AccountDailyMetric]:
        pass

    def list_recharge_records_for_customer_on_date(
        self,
        customer_id: UUID,
        report_date: date,
    ) -> list[RechargeRecord]:
        pass

    def list_recharge_records_on_date(
        self,
        report_date: date,
    ) -> list[RechargeRecord]:
        pass

    def list_card_bindings_for_customer_on_date(
        self,
        customer_id: UUID,
        report_date: date,
    ) -> list[AccountCardBinding]:
        pass

    def list_card_bindings_on_date(
        self,
        report_date: date,
    ) -> list[AccountCardBinding]:
        pass

    def add(self, value: object) -> None:
        pass

    def commit(self) -> None:
        pass


class InMemoryReportingUnitOfWork:
    def __init__(
        self,
        *,
        metrics: list[AccountDailyMetric] | None = None,
        risk_events: list[RiskEvent] | None = None,
        customer_reports: list[CustomerDailyReport] | None = None,
        company_reports: list[CompanyDailyReport] | None = None,
        recharge_records: list[RechargeRecord] | None = None,
        card_bindings: list[AccountCardBinding] | None = None,
    ) -> None:
        self.metrics = list(metrics or [])
        self.risk_events = list(risk_events or [])
        self.customer_reports = list(customer_reports or [])
        self.company_reports = list(company_reports or [])
        self.recharge_records = list(recharge_records or [])
        self.card_bindings = list(card_bindings or [])
        self.audit_events: list[object] = []
        self.committed = False

    def add_metric(self, metric: AccountDailyMetric) -> None:
        self.metrics.append(metric)

    def add_risk_event(self, event: RiskEvent) -> None:
        self.risk_events.append(event)

    def add_customer_report(self, report: CustomerDailyReport) -> None:
        self.customer_reports.append(report)

    def add_company_report(self, report: CompanyDailyReport) -> None:
        self.company_reports.append(report)

    def list_metrics_for_customer_on_date(
        self,
        customer_id: UUID,
        metric_date: date,
    ) -> list[AccountDailyMetric]:
        return [
            metric
            for metric in self.metrics
            if metric.customer_id == customer_id and metric.metric_date == metric_date
        ]

    def list_metrics_on_date(self, metric_date: date) -> list[AccountDailyMetric]:
        return [
            metric
            for metric in self.metrics
            if metric.metric_date == metric_date
        ]

    def list_recharge_records_for_customer_on_date(
        self,
        customer_id: UUID,
        report_date: date,
    ) -> list[RechargeRecord]:
        return [
            recharge
            for recharge in self.recharge_records
            if recharge.customer_id == customer_id
            and _recharge_report_date(recharge) == report_date
        ]

    def list_recharge_records_on_date(
        self,
        report_date: date,
    ) -> list[RechargeRecord]:
        return [
            recharge
            for recharge in self.recharge_records
            if _recharge_report_date(recharge) == report_date
        ]

    def list_card_bindings_for_customer_on_date(
        self,
        customer_id: UUID,
        report_date: date,
    ) -> list[AccountCardBinding]:
        return [
            binding
            for binding in self.card_bindings
            if binding.customer_id == customer_id
            and _card_binding_report_date(binding) == report_date
        ]

    def list_card_bindings_on_date(
        self,
        report_date: date,
    ) -> list[AccountCardBinding]:
        return [
            binding
            for binding in self.card_bindings
            if _card_binding_report_date(binding) == report_date
        ]

    def add(self, value: object) -> None:
        self.audit_events.append(value)

    def commit(self) -> None:
        self.committed = True


class SqlAlchemyReportingUnitOfWork:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_metric(self, metric: AccountDailyMetric) -> None:
        self.session.add(metric)

    def add_risk_event(self, event: RiskEvent) -> None:
        self.session.add(event)

    def add_customer_report(self, report: CustomerDailyReport) -> None:
        self.session.add(report)

    def add_company_report(self, report: CompanyDailyReport) -> None:
        self.session.add(report)

    def list_metrics_for_customer_on_date(
        self,
        customer_id: UUID,
        metric_date: date,
    ) -> list[AccountDailyMetric]:
        return list(
            self.session.scalars(
                select(AccountDailyMetric).where(
                    AccountDailyMetric.customer_id == customer_id,
                    AccountDailyMetric.metric_date == metric_date,
                )
            )
        )

    def list_metrics_on_date(self, metric_date: date) -> list[AccountDailyMetric]:
        return list(
            self.session.scalars(
                select(AccountDailyMetric).where(
                    AccountDailyMetric.metric_date == metric_date,
                )
            )
        )

    def list_recharge_records_for_customer_on_date(
        self,
        customer_id: UUID,
        report_date: date,
    ) -> list[RechargeRecord]:
        return list(
            self.session.scalars(
                select(RechargeRecord).where(
                    RechargeRecord.customer_id == customer_id,
                    _sql_report_date(
                        RechargeRecord.readback_at,
                        RechargeRecord.created_at,
                    )
                    == report_date,
                )
            )
        )

    def list_recharge_records_on_date(
        self,
        report_date: date,
    ) -> list[RechargeRecord]:
        return list(
            self.session.scalars(
                select(RechargeRecord).where(
                    _sql_report_date(
                        RechargeRecord.readback_at,
                        RechargeRecord.created_at,
                    )
                    == report_date,
                )
            )
        )

    def list_card_bindings_for_customer_on_date(
        self,
        customer_id: UUID,
        report_date: date,
    ) -> list[AccountCardBinding]:
        return list(
            self.session.scalars(
                select(AccountCardBinding).where(
                    AccountCardBinding.customer_id == customer_id,
                    _sql_report_date(
                        AccountCardBinding.bound_at,
                        AccountCardBinding.unbound_at,
                        AccountCardBinding.created_at,
                    )
                    == report_date,
                )
            )
        )

    def list_card_bindings_on_date(
        self,
        report_date: date,
    ) -> list[AccountCardBinding]:
        return list(
            self.session.scalars(
                select(AccountCardBinding).where(
                    _sql_report_date(
                        AccountCardBinding.bound_at,
                        AccountCardBinding.unbound_at,
                        AccountCardBinding.created_at,
                    )
                    == report_date,
                )
            )
        )

    def add(self, value: object) -> None:
        self.session.add(value)

    def commit(self) -> None:
        self.session.commit()


def generate_customer_daily_report(
    uow: ReportingUnitOfWork,
    *,
    actor: Actor,
    customer_id: UUID,
    report_date: date,
) -> CustomerDailyReport:
    if not can_view_customer_record(actor, customer_id):
        raise PermissionDenied(f"{actor.role} cannot view customer {customer_id}")

    metrics = uow.list_metrics_for_customer_on_date(customer_id, report_date)
    risk_events = [_risk_event_from_metric(metric) for metric in metrics if _is_risky(metric)]
    for event in risk_events:
        uow.add_risk_event(event)
        record_audit_event(
            uow,
            trace_id=f"risk:{event.id}",
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            event_type="risk_event_created",
            entity_type="risk_event",
            entity_id=event.id,
            after_state={
                "customer_id": str(event.customer_id) if event.customer_id else None,
                "account_asset_id": (
                    str(event.account_asset_id) if event.account_asset_id else None
                ),
                "risk_type": event.risk_type,
                "severity": event.severity,
                "status": event.status,
            },
        )

    recharge_records = uow.list_recharge_records_for_customer_on_date(
        customer_id,
        report_date,
    )
    card_bindings = uow.list_card_bindings_for_customer_on_date(
        customer_id,
        report_date,
    )
    payload = {
        "report_date": report_date.isoformat(),
        "customer_id": str(customer_id),
        "metrics": [_metric_payload(metric) for metric in metrics],
        "risk_events": [_risk_payload(event) for event in risk_events],
        "recharge_records": [
            _recharge_payload(recharge) for recharge in recharge_records
        ],
        "card_binding_state": _card_binding_state_payload(card_bindings),
        "card_bindings": [_card_binding_payload(binding) for binding in card_bindings],
    }
    report = CustomerDailyReport(
        id=uuid4(),
        customer_id=customer_id,
        report_date=report_date,
        report_payload=payload,
        visibility_scope={"customer_ids": [str(customer_id)]},
        delivery_status="draft",
        trace_id=f"report:customer:{customer_id}:{report_date.isoformat()}",
    )
    uow.add_customer_report(report)
    record_audit_event(
        uow,
        trace_id=report.trace_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type="customer_daily_report_generated",
        entity_type="customer_daily_report",
        entity_id=report.id,
        after_state={
            "customer_id": str(customer_id),
            "report_date": report_date.isoformat(),
            "delivery_status": report.delivery_status,
            "metric_count": len(metrics),
            "risk_event_count": len(risk_events),
            "recharge_record_count": len(recharge_records),
            "card_binding_count": len(card_bindings),
        },
    )
    return report


def generate_company_daily_report(
    uow: ReportingUnitOfWork,
    *,
    actor: Actor,
    report_date: date,
) -> CompanyDailyReport:
    assert_action_allowed(
        actor,
        "view_company_report",
        session=uow,
        trace_id=f"report:company:{report_date.isoformat()}",
        entity_type="company_daily_report",
    )
    metrics = uow.list_metrics_on_date(report_date)
    recharge_records = uow.list_recharge_records_on_date(report_date)
    card_bindings = uow.list_card_bindings_on_date(report_date)
    totals = _total_fresh_spend_by_currency(metrics)
    payload = {
        "report_date": report_date.isoformat(),
        "customers": _company_customer_payloads(metrics),
        "total_spend_by_currency": totals,
        "metric_sources": [_metric_source_payload(metric) for metric in metrics],
        "recharge_summary": _recharge_summary_payload(recharge_records),
        "card_binding_summary": _card_binding_summary_payload(card_bindings),
    }
    report = CompanyDailyReport(
        id=uuid4(),
        report_date=report_date,
        report_payload=payload,
        delivery_status="draft",
        trace_id=f"report:company:{report_date.isoformat()}",
    )
    uow.add_company_report(report)
    record_audit_event(
        uow,
        trace_id=report.trace_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type="company_daily_report_generated",
        entity_type="company_daily_report",
        entity_id=report.id,
        after_state={
            "report_date": report_date.isoformat(),
            "delivery_status": report.delivery_status,
            "metric_count": len(metrics),
            "customer_count": len({metric.customer_id for metric in metrics}),
            "recharge_record_count": len(recharge_records),
            "card_binding_count": len(card_bindings),
        },
    )
    return report


def get_company_report_for_actor(
    uow: ReportingUnitOfWork,
    *,
    actor: Actor,
    report: CompanyDailyReport,
) -> CompanyDailyReport:
    assert_action_allowed(
        actor,
        "view_company_report",
        session=uow,
        trace_id=report.trace_id,
        entity_type="company_daily_report",
        entity_id=report.id,
    )
    return report


def _metric_payload(metric: AccountDailyMetric) -> dict[str, object]:
    return {
        "metric_id": str(metric.id),
        "customer_id": str(metric.customer_id),
        "account_asset_id": str(metric.account_asset_id),
        "metric_date": metric.metric_date.isoformat(),
        "balance": {
            "amount": _decimal_or_none(metric.balance_amount),
            "currency": metric.balance_currency,
        },
        "spend": {
            "amount": _decimal_or_none(metric.spend_amount),
            "currency": metric.spend_currency,
        },
        "source": metric.source,
        "freshness_at": metric.freshness_at.isoformat(),
        "read_status": metric.read_status,
    }


def _metric_source_payload(metric: AccountDailyMetric) -> dict[str, object]:
    return {
        "metric_id": str(metric.id),
        "customer_id": str(metric.customer_id),
        "account_asset_id": str(metric.account_asset_id),
        "source": metric.source,
        "freshness_at": metric.freshness_at.isoformat(),
        "read_status": metric.read_status,
    }


def _risk_payload(event: RiskEvent) -> dict[str, object]:
    return {
        "risk_event_id": str(event.id),
        "customer_id": str(event.customer_id) if event.customer_id else None,
        "account_asset_id": str(event.account_asset_id) if event.account_asset_id else None,
        "risk_type": event.risk_type,
        "severity": event.severity,
        "source_metric_id": (
            str(event.source_metric_id) if event.source_metric_id else None
        ),
        "freshness_at": event.freshness_at.isoformat() if event.freshness_at else None,
        "status": event.status,
    }


def _recharge_payload(recharge: RechargeRecord) -> dict[str, object]:
    return {
        "recharge_record_id": str(recharge.id),
        "customer_id": str(recharge.customer_id),
        "amount": _decimal_or_none(recharge.amount),
        "currency": recharge.currency,
        "collection_status": recharge.collection_status,
        "execution_status": recharge.execution_status,
        "readback_status": recharge.readback_status,
        "freshness_at": (
            recharge.readback_at.isoformat()
            if recharge.readback_at is not None
            else None
        ),
        "source": "recharge_records",
    }


def _card_binding_state_payload(
    card_bindings: list[AccountCardBinding],
) -> dict[str, object]:
    if not card_bindings:
        return {
            "status": "not_available_in_stage_02",
            "source": "account_card_bindings",
            "reason": "no account_card_bindings facts for this customer/date",
        }
    return {
        "status": "available",
        "source": "account_card_bindings",
        "record_count": len(card_bindings),
        "status_counts": _status_counts(
            [binding.binding_status for binding in card_bindings]
        ),
    }


def _card_binding_payload(binding: AccountCardBinding) -> dict[str, object]:
    return {
        "card_binding_id": str(binding.id),
        "customer_id": str(binding.customer_id),
        "account_asset_id": str(binding.account_asset_id),
        "binding_status": binding.binding_status,
        "one_card_one_account_policy": binding.one_card_one_account_policy,
        "freshness_at": (
            _card_binding_freshness_at(binding).isoformat()
            if _card_binding_freshness_at(binding) is not None
            else None
        ),
        "failure_reason": "[masked]" if binding.failure_reason else None,
        "source": "account_card_bindings",
    }


def _card_binding_summary_payload(
    card_bindings: list[AccountCardBinding],
) -> dict[str, object]:
    return {
        "record_count": len(card_bindings),
        "status_counts": _status_counts(
            [binding.binding_status for binding in card_bindings]
        ),
        "source": "account_card_bindings",
    }


def _recharge_summary_payload(
    recharge_records: list[RechargeRecord],
) -> dict[str, object]:
    amount_by_currency: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    execution_status_counts: dict[str, int] = defaultdict(int)
    readback_status_counts: dict[str, int] = defaultdict(int)
    for recharge in recharge_records:
        amount_by_currency[recharge.currency] += recharge.amount
        execution_status_counts[recharge.execution_status] += 1
        readback_status_counts[recharge.readback_status] += 1
    return {
        "record_count": len(recharge_records),
        "amount_by_currency": {
            currency: _decimal_or_none(amount) or "0.00"
            for currency, amount in sorted(amount_by_currency.items())
        },
        "execution_status_counts": dict(sorted(execution_status_counts.items())),
        "readback_status_counts": dict(sorted(readback_status_counts.items())),
        "source": "recharge_records",
    }


def _status_counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for value in values:
        counts[value] += 1
    return dict(sorted(counts.items()))


def _company_customer_payloads(
    metrics: list[AccountDailyMetric],
) -> list[dict[str, object]]:
    grouped: dict[UUID, list[AccountDailyMetric]] = defaultdict(list)
    for metric in metrics:
        grouped[metric.customer_id].append(metric)

    payloads = []
    for customer_id, customer_metrics in sorted(grouped.items(), key=lambda item: str(item[0])):
        payloads.append(
            {
                "customer_id": str(customer_id),
                "metric_count": len(customer_metrics),
                "spend_by_currency": _total_fresh_spend_by_currency(customer_metrics),
                "metric_sources": [
                    _metric_source_payload(metric) for metric in customer_metrics
                ],
            }
        )
    return payloads


def _total_fresh_spend_by_currency(
    metrics: list[AccountDailyMetric],
) -> dict[str, str]:
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for metric in metrics:
        if metric.read_status != "fresh" or metric.spend_amount is None:
            continue
        currency = metric.spend_currency or "unknown"
        totals[currency] += metric.spend_amount
    return {currency: _decimal_or_none(amount) or "0.00" for currency, amount in totals.items()}


def _is_risky(metric: AccountDailyMetric) -> bool:
    return metric.read_status != "fresh"


def _risk_event_from_metric(metric: AccountDailyMetric) -> RiskEvent:
    return RiskEvent(
        id=uuid4(),
        customer_id=metric.customer_id,
        account_asset_id=metric.account_asset_id,
        risk_type=metric.read_status,
        severity="medium",
        source_metric_id=metric.id,
        source_metric=_metric_source_payload(metric),
        freshness_at=metric.freshness_at,
        status="open",
    )


def _recharge_report_date(recharge: RechargeRecord) -> date | None:
    if recharge.readback_at is not None:
        return recharge.readback_at.date()
    created_at = getattr(recharge, "created_at", None)
    if created_at is None:
        return None
    return created_at.date()


def _card_binding_report_date(binding: AccountCardBinding) -> date | None:
    freshness_at = _card_binding_freshness_at(binding)
    if freshness_at is not None:
        return freshness_at.date()
    created_at = getattr(binding, "created_at", None)
    if created_at is None:
        return None
    return created_at.date()


def _card_binding_freshness_at(binding: AccountCardBinding):
    return binding.bound_at or binding.unbound_at


def _sql_report_date(*columns):
    return func.date(func.coalesce(*columns))


def _decimal_or_none(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")
