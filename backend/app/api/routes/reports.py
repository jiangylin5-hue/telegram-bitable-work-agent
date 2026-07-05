from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_system_actor
from app.core.database import get_session
from app.models.reporting import CompanyDailyReport, CustomerDailyReport
from app.schemas.reports import CompanyDailyReportResponse, CustomerDailyReportResponse
from app.services.permissions import Actor, PermissionDenied
from app.services.reporting import (
    ReportingUnitOfWork,
    SqlAlchemyReportingUnitOfWork,
    generate_company_daily_report,
    generate_customer_daily_report,
)

router = APIRouter(prefix="/reports", tags=["reports"])


def get_reporting_uow(
    session: Session = Depends(get_session),
) -> ReportingUnitOfWork:
    return SqlAlchemyReportingUnitOfWork(session)


@router.post(
    "/customer-daily/{customer_id}",
    response_model=CustomerDailyReportResponse,
)
def create_customer_daily_report(
    customer_id: UUID,
    report_date: date,
    actor: Actor = Depends(get_system_actor),
    uow: ReportingUnitOfWork = Depends(get_reporting_uow),
) -> CustomerDailyReportResponse:
    try:
        report = generate_customer_daily_report(
            uow,
            actor=actor,
            customer_id=customer_id,
            report_date=report_date,
        )
    except PermissionDenied as exc:
        uow.commit()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    uow.commit()
    return _customer_report_response(report)


@router.post("/company-daily", response_model=CompanyDailyReportResponse)
def create_company_daily_report(
    report_date: date,
    actor: Actor = Depends(get_system_actor),
    uow: ReportingUnitOfWork = Depends(get_reporting_uow),
) -> CompanyDailyReportResponse:
    try:
        report = generate_company_daily_report(
            uow,
            actor=actor,
            report_date=report_date,
        )
    except PermissionDenied as exc:
        uow.commit()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    uow.commit()
    return _company_report_response(report)


def _customer_report_response(
    report: CustomerDailyReport,
) -> CustomerDailyReportResponse:
    return CustomerDailyReportResponse(
        id=str(report.id),
        customer_id=str(report.customer_id),
        report_date=report.report_date,
        delivery_status=report.delivery_status,
        report_payload=report.report_payload,
        trace_id=report.trace_id,
    )


def _company_report_response(report: CompanyDailyReport) -> CompanyDailyReportResponse:
    return CompanyDailyReportResponse(
        id=str(report.id),
        report_date=report.report_date,
        delivery_status=report.delivery_status,
        report_payload=report.report_payload,
        trace_id=report.trace_id,
    )
