from datetime import date

from pydantic import BaseModel


class ReportRecord(BaseModel):
    id: str
    report_date: date
    delivery_status: str
    report_payload: dict[str, object]
    trace_id: str


class CustomerDailyReportResponse(ReportRecord):
    customer_id: str


class CompanyDailyReportResponse(ReportRecord):
    pass
