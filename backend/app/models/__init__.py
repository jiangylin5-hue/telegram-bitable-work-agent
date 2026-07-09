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
from app.models.stage06_hardening import Stage06IdempotencyRecord
from app.models.stage06_platform import (
    BitableBase,
    PlatformField,
    PlatformForm,
    PlatformRecord,
    PlatformTable,
    PlatformView,
    RecordLink,
    Stage06TelegramBinding,
    Workspace,
    WorkspaceMember,
)
from app.models.stage06_runtime import (
    DigitalEmployee,
    NotificationRequest,
    RecordChangeDraft,
)
from app.models.stage06_templates import (
    ImportJob,
    PlatformTemplate,
    TemplateInstallation,
)
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
    "DigitalEmployee",
    "FieldPermission",
    "ImportJob",
    "Message",
    "NotificationRequest",
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
    "BitableBase",
    "PlatformField",
    "PlatformForm",
    "PlatformRecord",
    "PlatformTable",
    "PlatformView",
    "PlatformTemplate",
    "RecordChangeDraft",
    "RecordLink",
    "Stage06TelegramBinding",
    "Stage06IdempotencyRecord",
    "TableView",
    "TelegramCustomerBinding",
    "TelegramIdentity",
    "TelegramSendRequest",
    "TemplateInstallation",
    "User",
    "ViewColumn",
    "ViewFilter",
    "Workspace",
    "WorkspaceMember",
    "metadata",
]
