from datetime import date
from uuid import UUID

from app.models.reporting import CompanyDailyReport, CustomerDailyReport
from app.services.permissions import Actor
from app.services.reporting import (
    ReportingUnitOfWork,
    generate_company_daily_report,
    generate_customer_daily_report,
)


class MockReportingAgent:
    def generate_customer_report(
        self,
        uow: ReportingUnitOfWork,
        *,
        actor: Actor,
        customer_id: UUID,
        report_date: date,
    ) -> CustomerDailyReport:
        return generate_customer_daily_report(
            uow,
            actor=actor,
            customer_id=customer_id,
            report_date=report_date,
        )

    def generate_company_report(
        self,
        uow: ReportingUnitOfWork,
        *,
        actor: Actor,
        report_date: date,
    ) -> CompanyDailyReport:
        return generate_company_daily_report(
            uow,
            actor=actor,
            report_date=report_date,
        )
