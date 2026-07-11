from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.agent import AgentRun
from app.models.audit import OpsAuditEvent
from app.models.stage06_platform import (
    BitableBase,
    PlatformField,
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
from app.models.stage06_hardening import Stage06IdempotencyRecord
from app.services.audit import record_audit_event
from app.services.permissions import Actor
from app.services.stage06_audit import sanitize_stage06_audit_state
from app.services.stage06_pagination import paginate_items


STAGE06_FIELD_TYPES = frozenset(
    {
        "text",
        "number",
        "date",
        "status",
        "single_select",
        "multi_select",
        "user",
        "checkbox",
        "url",
        "email",
        "phone",
        "json",
        "linked_record",
        "lookup",
    }
)
F1_FIELD_TYPES = frozenset(
    {
        "text",
        "number",
        "date",
        "status",
        "single_select",
        "multi_select",
        "user",
        "checkbox",
        "url",
        "email",
        "phone",
    }
)
F1_CHOICE_FIELD_TYPES = frozenset({"status", "single_select", "multi_select"})
STAGE06_DEFAULT_WRITE_ROLES = frozenset(
    {"admin", "owner", "manager", "operator", "builder"}
)
CREATE_FORM_SCALAR_FIELD_TYPES = frozenset(
    {
        "text",
        "number",
        "date",
        "status",
        "single_select",
        "multi_select",
        "user",
        "checkbox",
        "url",
        "email",
        "phone",
    }
)
_MISSING = object()


class PlatformValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class BaseInitializationResult:
    base: BitableBase
    table: PlatformTable
    default_view: PlatformView


@dataclass(frozen=True)
class TableInitializationResult:
    table: PlatformTable
    default_view: PlatformView


@dataclass(frozen=True)
class FieldInitializationResult:
    field: PlatformField
    affected_view_ids: list[UUID]


class Stage06PlatformUnitOfWork(Protocol):
    def add_workspace(self, workspace: Workspace) -> None:
        pass

    def add_workspace_member(self, member: WorkspaceMember) -> None:
        pass

    def get_workspace(self, workspace_id: UUID) -> Workspace | None:
        pass

    def list_workspace_members(self, workspace_id: UUID) -> list[WorkspaceMember]:
        pass

    def list_workspace_members_for_user(self, user_id: str) -> list[WorkspaceMember]:
        pass

    def get_workspace_member(self, member_id: UUID) -> WorkspaceMember | None:
        pass

    def add_base(self, base: BitableBase) -> None:
        pass

    def get_base(self, base_id: UUID) -> BitableBase | None:
        pass

    def list_bases(self, workspace_id: UUID) -> list[BitableBase]:
        pass

    def add_table(self, table: PlatformTable) -> None:
        pass

    def get_table(self, table_id: UUID) -> PlatformTable | None:
        pass

    def lock_table_for_schema_mutation(self, table_id: UUID) -> PlatformTable | None:
        pass

    def list_tables(self, base_id: UUID) -> list[PlatformTable]:
        pass

    def add_field(self, field: PlatformField) -> None:
        pass

    def list_fields(self, table_id: UUID) -> list[PlatformField]:
        pass

    def add_record(self, record: PlatformRecord) -> None:
        pass

    def get_record(self, record_id: UUID) -> PlatformRecord | None:
        pass

    def list_records(self, table_id: UUID) -> list[PlatformRecord]:
        pass

    def add_record_link(self, record_link: RecordLink) -> None:
        pass

    def delete_record_links_for_record(self, record_id: UUID) -> None:
        pass

    def add_view(self, view: PlatformView) -> None:
        pass

    def get_view(self, view_id: UUID) -> PlatformView | None:
        pass

    def list_views(self, table_id: UUID) -> list[PlatformView]:
        pass

    def add_template(self, template: PlatformTemplate) -> None:
        pass

    def get_template(self, template_id: UUID) -> PlatformTemplate | None:
        pass

    def list_templates(self) -> list[PlatformTemplate]:
        pass

    def add_template_installation(
        self,
        installation: TemplateInstallation,
    ) -> None:
        pass

    def add_import_job(self, import_job: ImportJob) -> None:
        pass

    def get_import_job(self, import_job_id: UUID) -> ImportJob | None:
        pass

    def add_digital_employee(self, employee: DigitalEmployee) -> None:
        pass

    def get_digital_employee(self, employee_id: UUID) -> DigitalEmployee | None:
        pass

    def list_digital_employees(self, base_id: UUID) -> list[DigitalEmployee]:
        pass

    def add_record_change_draft(self, draft: RecordChangeDraft) -> None:
        pass

    def get_record_change_draft(self, draft_id: UUID) -> RecordChangeDraft | None:
        pass

    def list_record_change_drafts(self, base_id: UUID) -> list[RecordChangeDraft]:
        pass

    def add_notification_request(self, request: NotificationRequest) -> None:
        pass

    def get_notification_request(
        self,
        request_id: UUID,
    ) -> NotificationRequest | None:
        pass

    def list_notification_requests(self, base_id: UUID) -> list[NotificationRequest]:
        pass

    def add_agent_run(self, run: AgentRun) -> None:
        pass

    def list_audit_events(self) -> list[OpsAuditEvent]:
        pass

    def add_telegram_binding(self, binding: Stage06TelegramBinding) -> None:
        pass

    def list_telegram_bindings(self) -> list[Stage06TelegramBinding]:
        pass

    def get_idempotency_record(
        self,
        workspace_id: UUID,
        operation: str,
        idempotency_key: str,
    ) -> Stage06IdempotencyRecord | None:
        pass

    def add_idempotency_record(self, record: Stage06IdempotencyRecord) -> None:
        pass


@dataclass
class InMemoryStage06PlatformUnitOfWork:
    workspaces: list[Workspace] = field(default_factory=list)
    workspace_members: list[WorkspaceMember] = field(default_factory=list)
    bases: list[BitableBase] = field(default_factory=list)
    tables: list[PlatformTable] = field(default_factory=list)
    fields: list[PlatformField] = field(default_factory=list)
    records: list[PlatformRecord] = field(default_factory=list)
    record_links: list[RecordLink] = field(default_factory=list)
    views: list[PlatformView] = field(default_factory=list)
    templates: list[PlatformTemplate] = field(default_factory=list)
    template_installations: list[TemplateInstallation] = field(default_factory=list)
    import_jobs: list[ImportJob] = field(default_factory=list)
    digital_employees: list[DigitalEmployee] = field(default_factory=list)
    record_change_drafts: list[RecordChangeDraft] = field(default_factory=list)
    notification_requests: list[NotificationRequest] = field(default_factory=list)
    agent_runs: list[AgentRun] = field(default_factory=list)
    telegram_bindings: list[Stage06TelegramBinding] = field(default_factory=list)
    audit_events: list[OpsAuditEvent] = field(default_factory=list)
    idempotency_records: list[Stage06IdempotencyRecord] = field(default_factory=list)

    def add(self, value: object) -> None:
        if isinstance(value, OpsAuditEvent):
            self.audit_events.append(value)

    def add_workspace(self, workspace: Workspace) -> None:
        self.workspaces.append(workspace)

    def add_workspace_member(self, member: WorkspaceMember) -> None:
        self.workspace_members.append(member)

    def get_workspace(self, workspace_id: UUID) -> Workspace | None:
        return _find_by_id(self.workspaces, workspace_id)

    def list_workspace_members(self, workspace_id: UUID) -> list[WorkspaceMember]:
        return [
            member for member in self.workspace_members if member.workspace_id == workspace_id
        ]

    def list_workspace_members_for_user(self, user_id: str) -> list[WorkspaceMember]:
        return [
            member for member in self.workspace_members if member.user_id == user_id
        ]

    def get_workspace_member(self, member_id: UUID) -> WorkspaceMember | None:
        return _find_by_id(self.workspace_members, member_id)

    def add_base(self, base: BitableBase) -> None:
        self.bases.append(base)

    def get_base(self, base_id: UUID) -> BitableBase | None:
        return _find_by_id(self.bases, base_id)

    def list_bases(self, workspace_id: UUID) -> list[BitableBase]:
        return [base for base in self.bases if base.workspace_id == workspace_id]

    def add_table(self, table: PlatformTable) -> None:
        self.tables.append(table)

    def get_table(self, table_id: UUID) -> PlatformTable | None:
        return _find_by_id(self.tables, table_id)

    def lock_table_for_schema_mutation(self, table_id: UUID) -> PlatformTable | None:
        return self.get_table(table_id)

    def list_tables(self, base_id: UUID) -> list[PlatformTable]:
        return [table for table in self.tables if table.base_id == base_id]

    def add_field(self, field: PlatformField) -> None:
        self.fields.append(field)

    def list_fields(self, table_id: UUID) -> list[PlatformField]:
        return sorted(
            [field for field in self.fields if field.table_id == table_id],
            key=lambda value: value.order_index,
        )

    def add_record(self, record: PlatformRecord) -> None:
        self.records.append(record)

    def get_record(self, record_id: UUID) -> PlatformRecord | None:
        return _find_by_id(self.records, record_id)

    def list_records(self, table_id: UUID) -> list[PlatformRecord]:
        return [record for record in self.records if record.table_id == table_id]

    def add_record_link(self, record_link: RecordLink) -> None:
        self.record_links.append(record_link)

    def delete_record_links_for_record(self, record_id: UUID) -> None:
        self.record_links = [
            link for link in self.record_links if link.source_record_id != record_id
        ]

    def add_view(self, view: PlatformView) -> None:
        self.views.append(view)

    def get_view(self, view_id: UUID) -> PlatformView | None:
        return _find_by_id(self.views, view_id)

    def list_views(self, table_id: UUID) -> list[PlatformView]:
        return [view for view in self.views if view.table_id == table_id]

    def add_template(self, template: PlatformTemplate) -> None:
        if self.get_template(template.id) is None:
            self.templates.append(template)

    def get_template(self, template_id: UUID) -> PlatformTemplate | None:
        return _find_by_id(self.templates, template_id)

    def list_templates(self) -> list[PlatformTemplate]:
        return list(self.templates)

    def add_template_installation(
        self,
        installation: TemplateInstallation,
    ) -> None:
        self.template_installations.append(installation)

    def add_import_job(self, import_job: ImportJob) -> None:
        self.import_jobs.append(import_job)

    def get_import_job(self, import_job_id: UUID) -> ImportJob | None:
        return _find_by_id(self.import_jobs, import_job_id)

    def add_digital_employee(self, employee: DigitalEmployee) -> None:
        self.digital_employees.append(employee)

    def get_digital_employee(self, employee_id: UUID) -> DigitalEmployee | None:
        return _find_by_id(self.digital_employees, employee_id)

    def list_digital_employees(self, base_id: UUID) -> list[DigitalEmployee]:
        return [employee for employee in self.digital_employees if employee.base_id == base_id]

    def add_record_change_draft(self, draft: RecordChangeDraft) -> None:
        self.record_change_drafts.append(draft)

    def get_record_change_draft(self, draft_id: UUID) -> RecordChangeDraft | None:
        return _find_by_id(self.record_change_drafts, draft_id)

    def list_record_change_drafts(self, base_id: UUID) -> list[RecordChangeDraft]:
        return [draft for draft in self.record_change_drafts if draft.base_id == base_id]

    def add_notification_request(self, request: NotificationRequest) -> None:
        self.notification_requests.append(request)

    def get_notification_request(
        self,
        request_id: UUID,
    ) -> NotificationRequest | None:
        return _find_by_id(self.notification_requests, request_id)

    def list_notification_requests(self, base_id: UUID) -> list[NotificationRequest]:
        return [
            request for request in self.notification_requests if request.base_id == base_id
        ]

    def add_agent_run(self, run: AgentRun) -> None:
        self.agent_runs.append(run)

    def list_audit_events(self) -> list[OpsAuditEvent]:
        return list(self.audit_events)

    def add_telegram_binding(self, binding: Stage06TelegramBinding) -> None:
        self.telegram_bindings.append(binding)

    def list_telegram_bindings(self) -> list[Stage06TelegramBinding]:
        return list(self.telegram_bindings)

    def get_idempotency_record(
        self,
        workspace_id: UUID,
        operation: str,
        idempotency_key: str,
    ) -> Stage06IdempotencyRecord | None:
        return next(
            (
                record
                for record in self.idempotency_records
                if record.workspace_id == workspace_id
                and record.operation == operation
                and record.idempotency_key == idempotency_key
            ),
            None,
        )

    def add_idempotency_record(self, record: Stage06IdempotencyRecord) -> None:
        self.idempotency_records.append(record)


class SqlAlchemyStage06PlatformUnitOfWork:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_workspace(self, workspace: Workspace) -> None:
        self.session.add(workspace)

    def add_workspace_member(self, member: WorkspaceMember) -> None:
        self.session.add(member)

    def get_workspace(self, workspace_id: UUID) -> Workspace | None:
        return self.session.get(Workspace, workspace_id)

    def list_workspace_members(self, workspace_id: UUID) -> list[WorkspaceMember]:
        return list(
            self.session.scalars(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == workspace_id
                )
            )
        )

    def list_workspace_members_for_user(self, user_id: str) -> list[WorkspaceMember]:
        return list(
            self.session.scalars(
                select(WorkspaceMember).where(WorkspaceMember.user_id == user_id)
            )
        )

    def get_workspace_member(self, member_id: UUID) -> WorkspaceMember | None:
        return self.session.get(WorkspaceMember, member_id)

    def add_base(self, base: BitableBase) -> None:
        self.session.add(base)
        self.session.flush()

    def get_base(self, base_id: UUID) -> BitableBase | None:
        return self.session.get(BitableBase, base_id)

    def list_bases(self, workspace_id: UUID) -> list[BitableBase]:
        return list(
            self.session.scalars(
                select(BitableBase).where(BitableBase.workspace_id == workspace_id)
            )
        )

    def add_table(self, table: PlatformTable) -> None:
        self.session.add(table)
        self.session.flush()

    def get_table(self, table_id: UUID) -> PlatformTable | None:
        return self.session.get(PlatformTable, table_id)

    def lock_table_for_schema_mutation(self, table_id: UUID) -> PlatformTable | None:
        return self.session.scalar(
            select(PlatformTable)
            .where(PlatformTable.id == table_id)
            .with_for_update()
        )

    def list_tables(self, base_id: UUID) -> list[PlatformTable]:
        return list(
            self.session.scalars(
                select(PlatformTable).where(PlatformTable.base_id == base_id)
            )
        )

    def add_field(self, field: PlatformField) -> None:
        self.session.add(field)

    def list_fields(self, table_id: UUID) -> list[PlatformField]:
        return list(
            self.session.scalars(
                select(PlatformField)
                .where(PlatformField.table_id == table_id)
                .order_by(PlatformField.order_index)
            )
        )

    def add_record(self, record: PlatformRecord) -> None:
        self.session.add(record)

    def get_record(self, record_id: UUID) -> PlatformRecord | None:
        return self.session.get(PlatformRecord, record_id)

    def list_records(self, table_id: UUID) -> list[PlatformRecord]:
        return list(
            self.session.scalars(
                select(PlatformRecord).where(PlatformRecord.table_id == table_id)
            )
        )

    def add_record_link(self, record_link: RecordLink) -> None:
        self.session.add(record_link)

    def delete_record_links_for_record(self, record_id: UUID) -> None:
        self.session.execute(
            delete(RecordLink).where(RecordLink.source_record_id == record_id)
        )

    def add_view(self, view: PlatformView) -> None:
        self.session.add(view)

    def get_view(self, view_id: UUID) -> PlatformView | None:
        return self.session.get(PlatformView, view_id)

    def list_views(self, table_id: UUID) -> list[PlatformView]:
        return list(
            self.session.scalars(
                select(PlatformView).where(PlatformView.table_id == table_id)
            )
        )

    def add_template(self, template: PlatformTemplate) -> None:
        self.session.add(template)

    def get_template(self, template_id: UUID) -> PlatformTemplate | None:
        return self.session.get(PlatformTemplate, template_id)

    def list_templates(self) -> list[PlatformTemplate]:
        return list(self.session.scalars(select(PlatformTemplate)))

    def add_template_installation(
        self,
        installation: TemplateInstallation,
    ) -> None:
        self.session.add(installation)

    def add_import_job(self, import_job: ImportJob) -> None:
        self.session.add(import_job)

    def get_import_job(self, import_job_id: UUID) -> ImportJob | None:
        return self.session.get(ImportJob, import_job_id)

    def add_digital_employee(self, employee: DigitalEmployee) -> None:
        self.session.add(employee)

    def get_digital_employee(self, employee_id: UUID) -> DigitalEmployee | None:
        return self.session.get(DigitalEmployee, employee_id)

    def list_digital_employees(self, base_id: UUID) -> list[DigitalEmployee]:
        return list(
            self.session.scalars(
                select(DigitalEmployee).where(DigitalEmployee.base_id == base_id)
            )
        )

    def add_record_change_draft(self, draft: RecordChangeDraft) -> None:
        self.session.add(draft)

    def get_record_change_draft(self, draft_id: UUID) -> RecordChangeDraft | None:
        return self.session.get(RecordChangeDraft, draft_id)

    def list_record_change_drafts(self, base_id: UUID) -> list[RecordChangeDraft]:
        return list(
            self.session.scalars(
                select(RecordChangeDraft).where(RecordChangeDraft.base_id == base_id)
            )
        )

    def add_notification_request(self, request: NotificationRequest) -> None:
        self.session.add(request)

    def get_notification_request(
        self,
        request_id: UUID,
    ) -> NotificationRequest | None:
        return self.session.get(NotificationRequest, request_id)

    def list_notification_requests(self, base_id: UUID) -> list[NotificationRequest]:
        return list(
            self.session.scalars(
                select(NotificationRequest).where(NotificationRequest.base_id == base_id)
            )
        )

    def add_agent_run(self, run: AgentRun) -> None:
        self.session.add(run)

    def list_audit_events(self) -> list[OpsAuditEvent]:
        return list(
            self.session.scalars(
                select(OpsAuditEvent).order_by(OpsAuditEvent.created_at)
            )
        )

    def add_telegram_binding(self, binding: Stage06TelegramBinding) -> None:
        self.session.add(binding)

    def list_telegram_bindings(self) -> list[Stage06TelegramBinding]:
        return list(self.session.scalars(select(Stage06TelegramBinding)))

    def get_idempotency_record(
        self,
        workspace_id: UUID,
        operation: str,
        idempotency_key: str,
    ) -> Stage06IdempotencyRecord | None:
        return self.session.scalar(
            select(Stage06IdempotencyRecord)
            .where(
                Stage06IdempotencyRecord.workspace_id == workspace_id,
                Stage06IdempotencyRecord.operation == operation,
                Stage06IdempotencyRecord.idempotency_key == idempotency_key,
            )
            .with_for_update()
        )

    def add_idempotency_record(self, record: Stage06IdempotencyRecord) -> None:
        self.session.add(record)


def create_workspace(
    uow: Stage06PlatformUnitOfWork,
    *,
    name: str,
    owner_user_id: str,
    actor: Actor | None = None,
) -> Workspace:
    workspace = Workspace(
        id=uuid4(),
        name=name,
        slug=_slugify(name),
        owner_user_id=owner_user_id,
        status="active",
        settings={},
    )
    uow.add_workspace(workspace)
    uow.add_workspace_member(
        WorkspaceMember(
            id=uuid4(),
            workspace_id=workspace.id,
            user_id=owner_user_id,
            role="owner",
            status="active",
        )
    )
    _record_stage06_audit(
        uow,
        actor=actor,
        event_type="stage06.workspace_created",
        entity_type="workspace",
        entity_id=workspace.id,
        after_state={"name": workspace.name, "slug": workspace.slug},
    )
    return workspace


def create_base(
    uow: Stage06PlatformUnitOfWork,
    workspace_id: UUID,
    *,
    name: str,
    description: str | None = None,
    actor: Actor | None = None,
) -> BitableBase:
    _require_exists(uow.get_workspace(workspace_id), "workspace_not_found")
    base = BitableBase(
        id=uuid4(),
        workspace_id=workspace_id,
        name=name,
        description=description,
        source_type="blank",
        status="active",
        settings={},
    )
    uow.add_base(base)
    _record_stage06_audit(
        uow,
        actor=actor,
        event_type="stage06.base_created",
        entity_type="base",
        entity_id=base.id,
        after_state={"workspace_id": str(workspace_id), "name": base.name},
    )
    return base


def create_table(
    uow: Stage06PlatformUnitOfWork,
    base_id: UUID,
    *,
    name: str,
    key: str,
    actor: Actor | None = None,
) -> PlatformTable:
    _require_exists(uow.get_base(base_id), "base_not_found")
    table = PlatformTable(
        id=uuid4(),
        base_id=base_id,
        name=name,
        key=key,
        status="active",
        settings={},
    )
    uow.add_table(table)
    _record_stage06_audit(
        uow,
        actor=actor,
        event_type="stage06.table_created",
        entity_type="table",
        entity_id=table.id,
        after_state={"base_id": str(base_id), "name": table.name, "key": table.key},
    )
    return table


def create_field(
    uow: Stage06PlatformUnitOfWork,
    table_id: UUID,
    *,
    name: str,
    key: str,
    field_type: str,
    required: bool = False,
    options: dict[str, Any] | None = None,
    permission_policy: dict[str, Any] | None = None,
    actor: Actor | None = None,
) -> PlatformField:
    _require_exists(uow.get_table(table_id), "table_not_found")
    if field_type not in STAGE06_FIELD_TYPES:
        raise PlatformValidationError(
            "unsupported_field_type",
            f"Unsupported Stage06 field type: {field_type}",
        )
    field = PlatformField(
        id=uuid4(),
        table_id=table_id,
        name=name,
        key=key,
        field_type=field_type,
        required=required,
        unique=False,
        options=options or {},
        permission_policy=permission_policy or {},
        order_index=len(uow.list_fields(table_id)),
        status="active",
    )
    uow.add_field(field)
    _record_stage06_audit(
        uow,
        actor=actor,
        event_type="stage06.field_created",
        entity_type="field",
        entity_id=field.id,
        after_state=_field_to_schema(field),
    )
    return field


def initialize_field(
    uow: Stage06PlatformUnitOfWork,
    table_id: UUID,
    *,
    name: str,
    field_type: str,
    required: bool,
    choices: list[str] | None,
    actor: Actor,
) -> FieldInitializationResult:
    normalized_name = _normalized_f1_field_name(name)
    normalized_choices = _validated_f1_choices(field_type, choices)
    table = _require_exists(
        uow.lock_table_for_schema_mutation(table_id),
        "table_not_found",
    )
    existing_fields = uow.list_fields(table.id)
    normalized_existing_names = {
        field.name.strip().casefold()
        for field in existing_fields
    }
    if normalized_name.casefold() in normalized_existing_names:
        raise PlatformValidationError("duplicate_field_name", "field_name")

    field_key = _generated_f1_field_key({field.key for field in existing_fields})
    next_order_index = max(
        (field.order_index for field in existing_fields),
        default=-1,
    ) + 1
    field = PlatformField(
        id=uuid4(),
        table_id=table.id,
        name=normalized_name,
        key=field_key,
        field_type=field_type,
        required=required,
        unique=False,
        options=(
            {"choices": normalized_choices}
            if normalized_choices is not None
            else {}
        ),
        permission_policy={},
        order_index=next_order_index,
        status="active",
    )
    uow.add_field(field)

    affected_view_ids: list[UUID] = []
    for view in uow.list_views(table.id):
        configured_fields = view.config.get("fields")
        if view.status != "active" or not isinstance(configured_fields, list):
            continue
        if field.key in configured_fields:
            continue
        next_config = dict(view.config)
        next_config["fields"] = [*configured_fields, field.key]
        view.config = next_config
        affected_view_ids.append(view.id)

    _record_stage06_audit(
        uow,
        actor=actor,
        event_type="stage07.field_initialized",
        entity_type="field",
        entity_id=field.id,
        after_state={
            "table_id": str(table.id),
            "field_key": field.key,
            "field_type": field.field_type,
            "required": field.required,
            "order_index": field.order_index,
            "affected_view_ids": [str(view_id) for view_id in affected_view_ids],
        },
    )
    return FieldInitializationResult(field=field, affected_view_ids=affected_view_ids)


def create_record(
    uow: Stage06PlatformUnitOfWork,
    table_id: UUID,
    *,
    values: dict[str, Any],
    actor: Actor | None = None,
) -> PlatformRecord:
    _require_exists(uow.get_table(table_id), "table_not_found")
    fields = uow.list_fields(table_id)
    _validate_record_values(fields, values, uow=uow)
    normalized_values = _normalize_record_values(fields, values)
    record = PlatformRecord(
        id=uuid4(),
        table_id=table_id,
        record_values=normalized_values,
        record_status="active",
        created_by_user_id=None if actor is None else actor.actor_id,
        updated_by_user_id=None if actor is None else actor.actor_id,
        version=1,
    )
    uow.add_record(record)
    _sync_record_links(uow, record, fields)
    _record_stage06_audit(
        uow,
        actor=actor,
        event_type="stage06.record_created",
        entity_type="record",
        entity_id=record.id,
        after_state={"table_id": str(table_id), "values": normalized_values, "version": 1},
    )
    return record


def get_create_form(uow: Stage06PlatformUnitOfWork, table_id: UUID, *, actor: Actor) -> dict[str, Any]:
    _require_exists(uow.get_table(table_id), "table_not_found")
    all_fields = uow.list_fields(table_id)
    writable_fields = [field for field in all_fields if _can_actor_write_field(actor, field)]
    fields = [field for field in writable_fields if field.field_type in CREATE_FORM_SCALAR_FIELD_TYPES]
    can_create = not any(
        field.required and (field not in writable_fields or field.field_type not in CREATE_FORM_SCALAR_FIELD_TYPES)
        for field in all_fields
    )
    return {
        "table_id": str(table_id),
        "can_create": can_create,
        "fields": [
            {
                "id": str(field.id),
                "key": field.key,
                "name": field.name,
                "field_type": field.field_type,
                "required": field.required,
                "options": _create_form_options(field),
                "order_index": field.order_index,
            }
            for field in fields
        ],
    }


def _create_form_options(field: PlatformField) -> dict[str, Any]:
    return _safe_field_options(field)


def update_record(
    uow: Stage06PlatformUnitOfWork,
    record_id: UUID,
    *,
    values: dict[str, Any],
    expected_version: int,
    actor: Actor,
) -> PlatformRecord:
    record = _require_exists(uow.get_record(record_id), "record_not_found")
    if record.version != expected_version:
        raise PlatformValidationError("record_version_conflict", str(record_id))

    fields = uow.list_fields(record.table_id)
    field_by_key = {field.key: field for field in fields}
    _validate_record_values(fields, values, uow=uow, partial=True)
    for key in values:
        if not _can_actor_write_field(actor, field_by_key.get(key)):
            _deny_permission(
                uow,
                actor=actor,
                action="update_record_field",
                entity_type="record",
                entity_id=record.id,
                field_key=key,
            )

    normalized_values = _normalize_record_values(fields, values)
    before_values = {key: record.values.get(key) for key in normalized_values}
    updated_values = dict(record.values)
    updated_values.update(normalized_values)
    record.record_values = updated_values
    record.updated_by_user_id = actor.actor_id
    record.version += 1
    _sync_record_links(uow, record, fields)
    _record_stage06_audit(
        uow,
        actor=actor,
        event_type="stage06.record_updated",
        entity_type="record",
        entity_id=record.id,
        before_state={"values": before_values},
        after_state={
            "values": {key: updated_values.get(key) for key in normalized_values},
            "version": record.version,
        },
    )
    return record


def create_form_view(
    uow: Stage06PlatformUnitOfWork,
    base_id: UUID,
    table_id: UUID,
    *,
    name: str,
    view_type: str,
    config: dict[str, Any],
    permission_policy: dict[str, Any] | None = None,
    is_default: bool = False,
    actor: Actor | None = None,
) -> PlatformView:
    _require_exists(uow.get_base(base_id), "base_not_found")
    table = _require_exists(uow.get_table(table_id), "table_not_found")
    if table.base_id != base_id:
        raise PlatformValidationError("resource_scope_mismatch", "view_table_base")
    if view_type not in {"grid", "kanban", "calendar", "form", "dashboard_lite"}:
        raise PlatformValidationError("unsupported_view_type", view_type)
    view = PlatformView(
        id=uuid4(),
        base_id=base_id,
        table_id=table_id,
        name=name,
        view_type=view_type,
        config=config,
        permission_policy=permission_policy or {},
        is_default=is_default,
        status="active",
    )
    uow.add_view(view)
    _record_stage06_audit(
        uow,
        actor=actor,
        event_type="stage06.view_created",
        entity_type="view",
        entity_id=view.id,
        after_state={"table_id": str(table_id), "name": view.name, "view_type": view_type},
    )
    return view


def initialize_base(
    uow: Stage06PlatformUnitOfWork,
    workspace_id: UUID,
    *,
    base_name: str,
    table_name: str,
    actor: Actor,
) -> BaseInitializationResult:
    normalized_base_name = _normalized_builder_name(base_name, label="base_name")
    normalized_table_name = _normalized_builder_name(table_name, label="table_name")
    base = create_base(
        uow,
        workspace_id,
        name=normalized_base_name,
        actor=actor,
    )
    initialized_table = initialize_table(
        uow,
        base.id,
        table_name=normalized_table_name,
        actor=actor,
    )
    _record_stage06_audit(
        uow,
        actor=actor,
        event_type="stage06.base_initialized",
        entity_type="base",
        entity_id=base.id,
        after_state={
            "resource_map": {
                "base_id": str(base.id),
                "table_id": str(initialized_table.table.id),
                "view_id": str(initialized_table.default_view.id),
            }
        },
    )
    return BaseInitializationResult(
        base=base,
        table=initialized_table.table,
        default_view=initialized_table.default_view,
    )


def initialize_table(
    uow: Stage06PlatformUnitOfWork,
    base_id: UUID,
    *,
    table_name: str,
    actor: Actor,
) -> TableInitializationResult:
    base = _require_exists(uow.get_base(base_id), "base_not_found")
    normalized_table_name = _normalized_builder_name(table_name, label="table_name")
    table = create_table(
        uow,
        base.id,
        name=normalized_table_name,
        key=_generated_builder_table_key(),
        actor=actor,
    )
    default_view = create_form_view(
        uow,
        base.id,
        table.id,
        name="所有记录",
        view_type="grid",
        config={"fields": []},
        permission_policy={},
        is_default=True,
        actor=actor,
    )
    _record_stage06_audit(
        uow,
        actor=actor,
        event_type="stage06.table_initialized",
        entity_type="table",
        entity_id=table.id,
        after_state={
            "resource_map": {
                "base_id": str(base.id),
                "table_id": str(table.id),
                "view_id": str(default_view.id),
            }
        },
    )
    return TableInitializationResult(table=table, default_view=default_view)


def read_workspace(
    uow: Stage06PlatformUnitOfWork,
    workspace_id: UUID,
) -> Workspace:
    return _require_exists(uow.get_workspace(workspace_id), "workspace_not_found")


def list_workspace_members(
    uow: Stage06PlatformUnitOfWork,
    workspace_id: UUID,
) -> list[WorkspaceMember]:
    _require_exists(uow.get_workspace(workspace_id), "workspace_not_found")
    return uow.list_workspace_members(workspace_id)


def read_base(
    uow: Stage06PlatformUnitOfWork,
    base_id: UUID,
) -> BitableBase:
    return _require_exists(uow.get_base(base_id), "base_not_found")


def list_bases_for_workspace(
    uow: Stage06PlatformUnitOfWork,
    workspace_id: UUID,
) -> list[BitableBase]:
    _require_exists(uow.get_workspace(workspace_id), "workspace_not_found")
    return [base for base in uow.list_bases(workspace_id) if base.status == "active"]


def list_tables_for_base(
    uow: Stage06PlatformUnitOfWork,
    base_id: UUID,
) -> list[PlatformTable]:
    _require_exists(uow.get_base(base_id), "base_not_found")
    return [table for table in uow.list_tables(base_id) if table.status == "active"]


def list_views_for_base(
    uow: Stage06PlatformUnitOfWork,
    base_id: UUID,
) -> list[PlatformView]:
    tables = list_tables_for_base(uow, base_id)
    return [
        view
        for table in tables
        for view in uow.list_views(table.id)
        if view.status == "active"
    ]


def get_table_schema(
    uow: Stage06PlatformUnitOfWork,
    table_id: UUID,
    *,
    actor: Actor | None = None,
) -> dict[str, Any]:
    table = _require_exists(uow.get_table(table_id), "table_not_found")
    fields = uow.list_fields(table_id)
    if actor is not None:
        fields = [field for field in fields if _can_actor_read_field(actor, field)]
    return {
        "table": {
            "id": str(table.id),
            "base_id": str(table.base_id),
            "name": table.name,
            "key": table.key,
            "status": table.status,
        },
        "fields": [safe_table_schema_field(field) for field in fields],
    }


def get_view_presentation(
    uow: Stage06PlatformUnitOfWork,
    view_id: UUID,
    *,
    actor: Actor,
) -> dict[str, Any]:
    view = _require_exists(uow.get_view(view_id), "view_not_found")
    if not _can_actor_read_resource(actor, view.permission_policy):
        _deny_permission(
            uow,
            actor=actor,
            action="read_view_presentation",
            entity_type="view",
            entity_id=view.id,
        )
    if view.table_id is None:
        raise PlatformValidationError("view_has_no_table", str(view_id))
    fields = uow.list_fields(view.table_id)
    field_by_key = {field.key: field for field in fields}
    configured_fields = view.config.get("fields")
    candidate_keys = configured_fields if isinstance(configured_fields, list) else list(field_by_key)
    visible_field_keys = [
        key
        for key in candidate_keys
        if isinstance(key, str) and _can_actor_read_field(actor, field_by_key.get(key))
    ]
    group_by_field_key = _visible_configured_field_key(
        view.config.get("group_by_field_key"),
        field_by_key,
        actor,
    )
    date_field_key = _visible_configured_field_key(
        view.config.get("date_field_key"),
        field_by_key,
        actor,
        field_type="date",
    )
    return {
        "view_id": str(view.id),
        "table_id": str(view.table_id),
        "view_type": view.view_type,
        "visible_field_keys": visible_field_keys,
        "group_by_field_key": group_by_field_key,
        "date_field_key": date_field_key,
        "form_field_keys": visible_field_keys,
    }


def read_record_for_actor(
    uow: Stage06PlatformUnitOfWork,
    record_id: UUID,
    *,
    actor: Actor,
) -> dict[str, Any]:
    record = _require_exists(uow.get_record(record_id), "record_not_found")
    fields = uow.list_fields(record.table_id)
    values: dict[str, Any] = {}
    for field in fields:
        if not _can_actor_read_field(actor, field):
            continue
        value = _view_field_value(uow, record, fields, field, actor)
        if value is not _MISSING:
            values[field.key] = value
    return {
        "id": str(record.id),
        "table_id": str(record.table_id),
        "values": values,
        "record_status": record.record_status,
        "version": record.version,
    }


def list_view_records(
    uow: Stage06PlatformUnitOfWork,
    view_id: UUID,
    *,
    actor: Actor,
    limit: int | None = None,
    cursor: str | None = None,
) -> dict[str, Any]:
    view = _require_exists(uow.get_view(view_id), "view_not_found")
    if not _can_actor_read_resource(actor, view.permission_policy):
        _deny_permission(
            uow,
            actor=actor,
            action="read_view_records",
            entity_type="view",
            entity_id=view.id,
        )
    if view.table_id is None:
        raise PlatformValidationError("view_has_no_table", str(view_id))
    fields = uow.list_fields(view.table_id)
    field_by_key = {field.key: field for field in fields}
    view_fields = view.config.get("fields") or [field.key for field in fields]
    records = []
    page = paginate_items(
        uow.list_records(view.table_id),
        limit=limit,
        cursor=cursor,
    )
    for record in page.items:
        visible_fields: dict[str, Any] = {}
        for key in view_fields:
            field = field_by_key.get(key)
            if not _can_actor_read_field(actor, field):
                continue
            value = _view_field_value(uow, record, fields, field, actor)
            if value is not _MISSING:
                visible_fields[key] = value
        records.append({"id": str(record.id), "fields": visible_fields})
    return {
        "view_id": str(view.id),
        "records": records,
        "trace_id": f"stage06:view:{view.id}",
        "next_cursor": page.next_cursor,
        "has_more": page.has_more,
    }


def _validate_record_values(
    fields: list[PlatformField],
    values: dict[str, Any],
    *,
    uow: Stage06PlatformUnitOfWork | None = None,
    partial: bool = False,
) -> None:
    field_by_key = {field.key: field for field in fields}
    for field in fields:
        if field.required and field.key not in values:
            if partial:
                continue
            raise PlatformValidationError("missing_required_field", field.key)
    for key, value in values.items():
        field = field_by_key.get(key)
        if field is None:
            raise PlatformValidationError("unknown_field", key)
        if not _value_matches_field_type(value, field.field_type):
            raise PlatformValidationError("invalid_field_value", key)
        _validate_configured_choice_value(field, value)
        if field.field_type == "linked_record":
            _validate_linked_record_value(uow, field, value)


def _value_matches_field_type(value: Any, field_type: str) -> bool:
    if value is None:
        return True
    if field_type in {"text", "status", "single_select", "user", "url", "email", "phone"}:
        return isinstance(value, str)
    if field_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if field_type == "checkbox":
        return isinstance(value, bool)
    if field_type in {"multi_select", "linked_record"}:
        return isinstance(value, list)
    if field_type in {"json", "lookup"}:
        return isinstance(value, (dict, list, str, int, float, bool))
    if field_type == "date":
        return isinstance(value, str)
    return False


def _validate_configured_choice_value(field: PlatformField, value: Any) -> None:
    choices = _safe_field_options(field).get("choices")
    if choices is None or value is None:
        return
    if field.field_type == "multi_select":
        if (
            not isinstance(value, list)
            or not all(isinstance(item, str) for item in value)
            or len(value) != len(set(value))
            or any(item not in choices for item in value)
        ):
            raise PlatformValidationError("invalid_field_choice", field.key)
        return
    if not isinstance(value, str) or value not in choices:
        raise PlatformValidationError("invalid_field_choice", field.key)


def _validate_linked_record_value(
    uow: Stage06PlatformUnitOfWork | None,
    field: PlatformField,
    value: Any,
) -> None:
    if uow is None or value is None:
        return
    target_table_id = _optional_uuid(field.options.get("target_table_id"))
    source_table = uow.get_table(field.table_id)
    if source_table is None:
        raise PlatformValidationError("table_not_found", str(field.table_id))
    for item in value:
        target_record_id = _optional_uuid(item)
        if target_record_id is None:
            raise PlatformValidationError("invalid_link_target", field.key)
        target_record = uow.get_record(target_record_id)
        if target_record is None:
            raise PlatformValidationError("invalid_link_target", field.key)
        target_table = uow.get_table(target_record.table_id)
        if target_table is None:
            raise PlatformValidationError("invalid_link_target", field.key)
        if target_table.base_id != source_table.base_id:
            raise PlatformValidationError("resource_scope_mismatch", field.key)
        if target_table_id is not None and target_record.table_id != target_table_id:
            raise PlatformValidationError("invalid_link_target", field.key)


def _normalize_record_values(
    fields: list[PlatformField],
    values: dict[str, Any],
) -> dict[str, Any]:
    field_by_key = {field.key: field for field in fields}
    normalized: dict[str, Any] = {}
    for key, value in values.items():
        field = field_by_key[key]
        if field.field_type == "linked_record" and value is not None:
            normalized[key] = [str(item) for item in value]
        else:
            normalized[key] = value
    return normalized


def _sync_record_links(
    uow: Stage06PlatformUnitOfWork,
    record: PlatformRecord,
    fields: list[PlatformField],
) -> None:
    uow.delete_record_links_for_record(record.id)
    for field in fields:
        if field.field_type != "linked_record":
            continue
        linked_ids = record.values.get(field.key) or []
        for linked_id in linked_ids:
            target_record_id = _optional_uuid(linked_id)
            if target_record_id is None:
                continue
            target_record = uow.get_record(target_record_id)
            if target_record is None:
                continue
            uow.add_record_link(
                RecordLink(
                    id=uuid4(),
                    source_table_id=record.table_id,
                    source_record_id=record.id,
                    source_field_id=field.id,
                    target_table_id=target_record.table_id,
                    target_record_id=target_record.id,
                )
            )


def _view_field_value(
    uow: Stage06PlatformUnitOfWork,
    record: PlatformRecord,
    fields: list[PlatformField],
    field: PlatformField | None,
    actor: Actor,
) -> Any:
    if field is None:
        return _MISSING
    if field.field_type == "lookup":
        return _lookup_field_value(uow, record, field, actor)
    if field.key in record.values:
        return record.values[field.key]
    return _MISSING


def _lookup_field_value(
    uow: Stage06PlatformUnitOfWork,
    record: PlatformRecord,
    field: PlatformField,
    actor: Actor,
) -> list[Any] | object:
    source_field_key = field.options.get("source_field_key")
    target_field_key = field.options.get("target_field_key")
    if not source_field_key or not target_field_key:
        return []
    linked_ids = record.values.get(source_field_key) or []
    if not isinstance(linked_ids, list):
        return []
    values: list[Any] = []
    for linked_id in linked_ids:
        target_record_id = _optional_uuid(linked_id)
        if target_record_id is None:
            continue
        target_record = uow.get_record(target_record_id)
        if target_record is None:
            continue
        target_field = next(
            (
                candidate
                for candidate in uow.list_fields(target_record.table_id)
                if candidate.key == target_field_key
            ),
            None,
        )
        if not _can_actor_read_field(actor, target_field):
            return _MISSING
        if target_field_key in target_record.values:
            values.append(target_record.values[target_field_key])
    return values


def _safe_field_options(field: PlatformField) -> dict[str, Any]:
    if field.field_type not in {"status", "single_select", "multi_select"}:
        return {}
    choices = field.options.get("choices")
    if not isinstance(choices, list) or not all(isinstance(choice, str) for choice in choices):
        return {}
    return {"choices": list(choices)}


def _field_to_schema(field: PlatformField) -> dict[str, Any]:
    return {
        "id": str(field.id),
        "table_id": str(field.table_id),
        "name": field.name,
        "key": field.key,
        "field_type": field.field_type,
        "required": field.required,
        "options": field.options,
        "permission_policy": field.permission_policy,
        "order_index": field.order_index,
    }


def safe_table_schema_field(field: PlatformField) -> dict[str, Any]:
    return {
        "id": str(field.id),
        "table_id": str(field.table_id),
        "name": field.name,
        "key": field.key,
        "field_type": field.field_type,
        "required": field.required,
        "options": _safe_field_options(field),
        "order_index": field.order_index,
    }


def _can_actor_read_field(actor: Actor, field: PlatformField | None) -> bool:
    if field is None:
        return False
    policy = field.permission_policy or {}
    mode = policy.get(actor.role, policy.get("default", "read"))
    return mode not in {"hidden", "none"}


def _visible_configured_field_key(
    key: object,
    field_by_key: dict[str, PlatformField],
    actor: Actor,
    *,
    field_type: str | None = None,
) -> str | None:
    if not isinstance(key, str):
        return None
    field = field_by_key.get(key)
    if field is None or not _can_actor_read_field(actor, field):
        return None
    if field_type is not None and field.field_type != field_type:
        return None
    return key


def _can_actor_write_field(actor: Actor, field: PlatformField | None) -> bool:
    if field is None:
        return False
    policy = field.permission_policy or {}
    mode = policy.get(actor.role, policy.get("default"))
    if mode is None:
        return actor.role in STAGE06_DEFAULT_WRITE_ROLES
    return mode in {"write", "admin", "owner", "*"} or mode is True


def _can_actor_read_resource(actor: Actor, policy: dict[str, Any] | None) -> bool:
    mode = (policy or {}).get(actor.role, (policy or {}).get("default", "read"))
    return mode not in {"hidden", "none"}


def _deny_permission(
    uow: Stage06PlatformUnitOfWork,
    *,
    actor: Actor,
    action: str,
    entity_type: str,
    entity_id: UUID | None = None,
    field_key: str | None = None,
) -> None:
    _record_stage06_audit(
        uow,
        actor=actor,
        event_type="permission_denied",
        entity_type=entity_type,
        entity_id=entity_id,
        permission_snapshot={
            "action": action,
            "role": actor.role,
            "actor_type": actor.actor_type,
            "field_key": field_key,
        },
    )
    raise PlatformValidationError("permission_denied", action)


def _record_stage06_audit(
    uow: Stage06PlatformUnitOfWork,
    *,
    actor: Actor | None,
    event_type: str,
    entity_type: str,
    entity_id: UUID | None = None,
    before_state: dict[str, Any] | None = None,
    after_state: dict[str, Any] | None = None,
    permission_snapshot: dict[str, Any] | None = None,
) -> OpsAuditEvent | None:
    if actor is None:
        return None
    return record_audit_event(
        _audit_target(uow),
        trace_id=f"stage06:{entity_type}:{entity_id or uuid4()}",
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        before_state=sanitize_stage06_audit_state(before_state),
        after_state=sanitize_stage06_audit_state(after_state),
        permission_snapshot=sanitize_stage06_audit_state(
            permission_snapshot
            or {"role": actor.role, "actor_type": actor.actor_type}
        ),
    )


def _audit_target(uow: Stage06PlatformUnitOfWork) -> Any:
    return getattr(uow, "session", uow)


def _require_exists(value: Any | None, code: str) -> Any:
    if value is None:
        raise PlatformValidationError(code, code)
    return value


def _find_by_id(items: list[Any], item_id: UUID) -> Any | None:
    return next((item for item in items if item.id == item_id), None)


def _slugify(value: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in value)
    return "-".join(part for part in slug.split("-") if part) or "workspace"


def _normalized_builder_name(value: str, *, label: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > 160:
        raise PlatformValidationError("invalid_builder_name", label)
    return normalized


def _normalized_f1_field_name(value: str) -> str:
    if not isinstance(value, str):
        raise PlatformValidationError("invalid_field_name", "field_name")
    normalized = value.strip()
    if not normalized or len(normalized) > 160:
        raise PlatformValidationError("invalid_field_name", "field_name")
    return normalized


def _validated_f1_choices(
    field_type: str,
    choices: list[str] | None,
) -> list[str] | None:
    if field_type not in F1_FIELD_TYPES:
        raise PlatformValidationError("unsupported_field_type", field_type)
    if field_type not in F1_CHOICE_FIELD_TYPES:
        if choices is not None:
            raise PlatformValidationError("unexpected_field_choices", field_type)
        return None
    if not isinstance(choices, list) or not 1 <= len(choices) <= 100:
        raise PlatformValidationError("invalid_field_choices", field_type)

    normalized_choices: list[str] = []
    normalized_choice_keys: set[str] = set()
    for choice in choices:
        if not isinstance(choice, str):
            raise PlatformValidationError("invalid_field_choices", field_type)
        normalized_choice = choice.strip()
        normalized_choice_key = normalized_choice.casefold()
        if (
            not normalized_choice
            or len(normalized_choice) > 64
            or normalized_choice_key in normalized_choice_keys
        ):
            raise PlatformValidationError("invalid_field_choices", field_type)
        normalized_choices.append(normalized_choice)
        normalized_choice_keys.add(normalized_choice_key)
    return normalized_choices


def _generated_f1_field_key(existing_keys: set[str]) -> str:
    while True:
        key = f"fld_{uuid4().hex}"
        if key not in existing_keys:
            return key


def _generated_builder_table_key() -> str:
    return f"tbl_{uuid4().hex}"


def _optional_uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None
