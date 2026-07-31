from app.models.audit import OpsAuditEvent
from app.models.base import Base
from app.models.accounts import (
    AccountAsset,
    AccountAssignment,
    AccountInventory,
    AccountStatusEvent,
)
from app.models.agent import AgentRun
from app.models.agent_event_runtime import (
    AgentActionSlot,
    AgentArtifact,
    AgentCommand,
    AgentEvent,
    AgentOutboxEvent,
    AgentObjectiveRun,
    AgentPrivateInput,
    AgentRunCheckpoint,
    AgentWorkflowRun,
)
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
    DigitalEmployeeMemberGrant,
    NotificationRequest,
    RecordChangeDraft,
)
from app.models.stage08_runtime import Stage08ExecutionTicket
from app.models.stage08_memory import (
    Stage08MemoryExtractionCandidate,
    Stage08MemoryItem,
)
from app.models.stage08_group_context import (
    Stage08GroupBusinessContextBinding,
    Stage08GroupMessageProjection,
)
from app.models.stage08_knowledge import (
    Stage08KnowledgeChunk,
    Stage08KnowledgeSource,
)
from app.models.stage12_retrieval import (
    Stage12RelationEdge,
    Stage12RetrievalChunk,
    Stage12RetrievalProfile,
    Stage12RetrievalScopeRegistration,
    Stage12RetrievalSource,
)
from app.models.stage06_templates import (
    ImportJob,
    PlatformTemplate,
    TemplateInstallation,
)
from app.models.stage07_telegram import (
    Stage07TelegramDeepLink,
    Stage07TelegramDeepLinkDelivery,
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
    "AgentArtifact",
    "AgentActionSlot",
    "AgentCommand",
    "AgentEvent",
    "AgentOutboxEvent",
    "AgentObjectiveRun",
    "AgentPrivateInput",
    "AgentRunCheckpoint",
    "AgentWorkflowRun",
    "AutomationRule",
    "CompanyDailyReport",
    "Customer",
    "CustomerGroup",
    "CustomerDailyReport",
    "DigitalEmployee",
    "DigitalEmployeeMemberGrant",
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
    "Stage08MemoryExtractionCandidate",
    "Stage08MemoryItem",
    "Stage08GroupBusinessContextBinding",
    "Stage08GroupMessageProjection",
    "Stage08KnowledgeChunk",
    "Stage08KnowledgeSource",
    "Stage08ExecutionTicket",
    "Stage12RelationEdge",
    "Stage12RetrievalChunk",
    "Stage12RetrievalProfile",
    "Stage12RetrievalScopeRegistration",
    "Stage12RetrievalSource",
    "Stage07TelegramDeepLink",
    "Stage07TelegramDeepLinkDelivery",
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
