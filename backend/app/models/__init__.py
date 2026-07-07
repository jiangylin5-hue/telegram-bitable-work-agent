from app.models.audit import OpsAuditEvent
from app.models.base import Base
from app.models.accounts import (
    AccountAsset,
    AccountAssignment,
    AccountInventory,
    AccountStatusEvent,
)
from app.models.agent import AgentRun
from app.models.bitable import (
    AutomationRule,
    FieldPermission,
    TableView,
    ViewColumn,
    ViewFilter,
)
from app.models.cards import AccountCardBinding, PaymentProfile
from app.models.customers import Customer, CustomerGroup
from app.models.outbox import OutboxEvent
from app.models.recharge import CollectionRecord, RechargeRecord
from app.models.reporting import (
    AccountDailyMetric,
    CompanyDailyReport,
    CustomerDailyReport,
    RiskEvent,
)
from app.models.service import ExecutionLog, ExecutionTicket, ServiceRecord
from app.models.service_drafts import ServiceDraft
from app.models.telegram import (
    Message,
    TelegramCustomerBinding,
    TelegramIdentity,
    TelegramSendRequest,
)
from app.models.users import User

metadata = Base.metadata

__all__ = [
    "Base",
    "AccountAsset",
    "AccountAssignment",
    "AccountInventory",
    "AccountStatusEvent",
    "AccountDailyMetric",
    "AccountCardBinding",
    "AgentRun",
    "AutomationRule",
    "CompanyDailyReport",
    "Customer",
    "CustomerGroup",
    "CustomerDailyReport",
    "FieldPermission",
    "Message",
    "OpsAuditEvent",
    "OutboxEvent",
    "PaymentProfile",
    "CollectionRecord",
    "ExecutionLog",
    "ExecutionTicket",
    "RechargeRecord",
    "RiskEvent",
    "ServiceRecord",
    "ServiceDraft",
    "TableView",
    "TelegramCustomerBinding",
    "TelegramIdentity",
    "TelegramSendRequest",
    "User",
    "ViewColumn",
    "ViewFilter",
    "metadata",
]
