from collections.abc import Iterable
from uuid import UUID

from app.services.permissions import Actor
from app.services.stage06_identity import Stage06RequestIdentity
from app.services.stage06_platform import Stage06PlatformUnitOfWork


ROLE_ACTIONS: dict[str, frozenset[str]] = {
    "owner": frozenset({"*"}),
    "admin": frozenset(
        {
            "workspace.read",
            "member.read",
            "base.create",
            "base.read",
            "table.create",
            "table.read",
            "field.manage",
            "view.manage",
            "record.read",
            "record.create",
            "record.update",
            "import.create",
            "import.read",
            "import.commit",
            "template.install",
            "template.save",
            "digital_employee.create",
            "digital_employee.read",
            "digital_employee.update",
            "digital_employee.invoke",
            "record_change_draft.read",
            "record_change_draft.confirm",
            "record_change_draft.reject",
            "telegram_binding.manage",
            "notification_request.create",
            "notification_request.read",
            "notification_request.confirm",
            "audit.read",
        }
    ),
    "builder": frozenset(
        {
            "workspace.read",
            "base.create",
            "base.read",
            "table.create",
            "table.read",
            "field.manage",
            "view.manage",
            "record.read",
            "record.create",
            "record.update",
            "import.create",
            "import.read",
            "import.commit",
            "template.install",
            "template.save",
            "digital_employee.create",
            "digital_employee.read",
            "digital_employee.update",
            "digital_employee.invoke",
            "record_change_draft.read",
            "telegram_binding.manage",
            "notification_request.create",
            "notification_request.read",
        }
    ),
    "operator": frozenset(
        {
            "workspace.read",
            "base.read",
            "table.read",
            "record.read",
            "record.create",
            "record.update",
            "digital_employee.read",
            "digital_employee.invoke",
            "record_change_draft.read",
            "record_change_draft.confirm",
            "record_change_draft.reject",
            "notification_request.create",
            "notification_request.read",
            "notification_request.confirm",
        }
    ),
    "viewer": frozenset(
        {
            "workspace.read",
            "base.read",
            "table.read",
            "record.read",
            "digital_employee.read",
            "digital_employee.invoke",
            "record_change_draft.read",
            "notification_request.read",
        }
    ),
}


class Stage06AuthorizationError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        resource_type: str,
        action: str,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.resource_type = resource_type
        self.action = action


def authorize_workspace_action(
    uow: Stage06PlatformUnitOfWork,
    identity: Stage06RequestIdentity,
    workspace_id: UUID,
    action: str,
) -> Actor:
    if uow.get_workspace(workspace_id) is None:
        raise Stage06AuthorizationError(
            "workspace_not_found",
            resource_type="workspace",
            action=action,
        )
    member = next(
        (
            item
            for item in uow.list_workspace_members(workspace_id)
            if item.user_id == identity.user_id and item.status == "active"
        ),
        None,
    )
    if member is None:
        raise Stage06AuthorizationError(
            "stage06_membership_required",
            resource_type="workspace",
            action=action,
        )
    allowed = ROLE_ACTIONS.get(member.role, frozenset())
    if "*" not in allowed and action not in allowed:
        raise Stage06AuthorizationError(
            "stage06_action_denied",
            resource_type="workspace",
            action=action,
        )
    return Actor(
        actor_type="user",
        actor_id=identity.user_id,
        role=member.role,
    )


def actor_for_workspace_bootstrap(identity: Stage06RequestIdentity) -> Actor:
    return Actor(actor_type="user", actor_id=identity.user_id, role="owner")


def workspace_id_for_base(
    uow: Stage06PlatformUnitOfWork,
    base_id: UUID,
) -> UUID:
    base = uow.get_base(base_id)
    if base is None:
        _not_found("base", "base.read")
    return base.workspace_id


def workspace_id_for_table(
    uow: Stage06PlatformUnitOfWork,
    table_id: UUID,
) -> UUID:
    table = uow.get_table(table_id)
    if table is None:
        _not_found("table", "table.read")
    return workspace_id_for_base(uow, table.base_id)


def workspace_id_for_view(
    uow: Stage06PlatformUnitOfWork,
    view_id: UUID,
) -> UUID:
    view = uow.get_view(view_id)
    if view is None:
        _not_found("view", "record.read")
    return workspace_id_for_base(uow, view.base_id)


def workspace_id_for_record(
    uow: Stage06PlatformUnitOfWork,
    record_id: UUID,
) -> UUID:
    record = uow.get_record(record_id)
    if record is None:
        _not_found("record", "record.read")
    return workspace_id_for_table(uow, record.table_id)


def workspace_id_for_import_job(
    uow: Stage06PlatformUnitOfWork,
    import_job_id: UUID,
) -> UUID:
    job = uow.get_import_job(import_job_id)
    if job is None:
        _not_found("import_job", "import.read")
    return job.workspace_id


def workspace_id_for_employee(
    uow: Stage06PlatformUnitOfWork,
    employee_id: UUID,
) -> UUID:
    employee = uow.get_digital_employee(employee_id)
    if employee is None:
        _not_found("digital_employee", "digital_employee.read")
    return employee.workspace_id


def workspace_id_for_draft(
    uow: Stage06PlatformUnitOfWork,
    draft_id: UUID,
) -> UUID:
    draft = uow.get_record_change_draft(draft_id)
    if draft is None:
        _not_found("record_change_draft", "record_change_draft.read")
    return draft.workspace_id


def workspace_id_for_notification(
    uow: Stage06PlatformUnitOfWork,
    request_id: UUID,
) -> UUID:
    request = uow.get_notification_request(request_id)
    if request is None:
        _not_found("notification_request", "notification_request.read")
    return request.workspace_id


def action_allowed_for_role(role: str, action: str) -> bool:
    allowed: Iterable[str] = ROLE_ACTIONS.get(role, frozenset())
    return "*" in allowed or action in allowed


def _not_found(resource_type: str, action: str) -> None:
    raise Stage06AuthorizationError(
        f"{resource_type}_not_found",
        resource_type=resource_type,
        action=action,
    )
