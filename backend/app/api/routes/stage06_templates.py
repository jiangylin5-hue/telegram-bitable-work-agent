import base64
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_stage06_request_identity
from app.core.database import get_session
from app.core.errors import error_detail
from app.schemas.stage06_templates import (
    CommitImportRequest,
    CreateImportRequest,
    ImportCommitResponse,
    ImportJobResponse,
    InstallTemplateRequest,
    SaveBaseAsTemplateRequest,
    TemplateInstallationResponse,
    TemplateListResponse,
    TemplateResponse,
)
from app.services.stage06_authorization import (
    Stage06AuthorizationError,
    authorize_workspace_action,
    workspace_id_for_base,
    workspace_id_for_import_job,
)
from app.services.stage06_identity import Stage06RequestIdentity
from app.services.stage06_idempotency import (
    begin_idempotent_operation,
    complete_idempotent_operation,
    fingerprint_request,
)
from app.services.stage06_platform import PlatformValidationError
from app.services.stage06_templates import (
    Stage06TemplateImportUnitOfWork,
    commit_import_job,
    create_import_job_from_csv,
    create_import_job_from_excel,
    install_template,
    list_templates,
    read_import_job,
    save_base_as_template,
)
from app.services.stage06_platform import SqlAlchemyStage06PlatformUnitOfWork

router = APIRouter(tags=["stage06-template-import"])


class SqlAlchemyStage06TemplateImportUnitOfWork(SqlAlchemyStage06PlatformUnitOfWork):
    pass


def get_stage06_template_import_uow(
    session: Session = Depends(get_session),
) -> Stage06TemplateImportUnitOfWork:
    return SqlAlchemyStage06TemplateImportUnitOfWork(session)


@router.get("/templates", response_model=TemplateListResponse)
def list_templates_endpoint(
    _identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06TemplateImportUnitOfWork = Depends(get_stage06_template_import_uow),
) -> TemplateListResponse:
    return TemplateListResponse(
        templates=[_template_response(template) for template in list_templates(uow)]
    )


@router.post(
    "/workspaces/{workspace_id}/template-installations",
    response_model=TemplateInstallationResponse,
)
def install_template_endpoint(
    workspace_id: UUID,
    request: InstallTemplateRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=160),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06TemplateImportUnitOfWork = Depends(get_stage06_template_import_uow),
) -> TemplateInstallationResponse:
    try:
        actor = authorize_workspace_action(
            uow,
            identity,
            workspace_id,
            "template.install",
        )
        fingerprint = fingerprint_request(
            {
                "workspace_id": workspace_id,
                "template_id": request.template_id,
                "user_id": identity.user_id,
            }
        )
        decision = _begin_and_reserve(
            uow,
            workspace_id=workspace_id,
            operation="template.install",
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
        )
        if decision.status == "replay":
            return TemplateInstallationResponse(**(decision.response_ref or {}))
        installation = install_template(
            uow,
            workspace_id,
            UUID(request.template_id),
            installed_by_user_id=identity.user_id,
            actor=actor,
        )
        response = TemplateInstallationResponse(
            id=str(installation.id),
            workspace_id=str(installation.workspace_id),
            base_id=str(installation.base_id),
            template_id=str(installation.template_id),
            template_version=installation.template_version,
            resource_map=installation.resource_map,
        )
        complete_idempotent_operation(
            decision.record,
            response_ref=response.model_dump(),
        )
    except (PlatformValidationError, Stage06AuthorizationError, ValueError) as exc:
        raise _http_error(exc) from exc
    _commit_if_sqlalchemy(uow)
    return response


@router.post("/workspaces/{workspace_id}/imports", response_model=ImportJobResponse)
def create_import_endpoint(
    workspace_id: UUID,
    request: CreateImportRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=160),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06TemplateImportUnitOfWork = Depends(get_stage06_template_import_uow),
) -> ImportJobResponse:
    try:
        authorize_workspace_action(uow, identity, workspace_id, "import.create")
        fingerprint = fingerprint_request(
            {
                "workspace_id": workspace_id,
                "request": request.model_dump(),
                "user_id": identity.user_id,
            }
        )
        decision = _begin_and_reserve(
            uow,
            workspace_id=workspace_id,
            operation="import.create",
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
        )
        if decision.status == "replay":
            response_ref = decision.response_ref or {}
            job = read_import_job(uow, UUID(str(response_ref["import_job_id"])))
            return _import_job_response(job)
        base_id = None if request.base_id is None else UUID(request.base_id)
        if request.source_type == "csv":
            job = create_import_job_from_csv(
                uow,
                workspace_id,
                file_name=request.file_name,
                content=request.content,
                created_by_user_id=identity.user_id,
                base_id=base_id,
            )
        elif request.source_type == "excel":
            job = create_import_job_from_excel(
                uow,
                workspace_id,
                file_name=request.file_name,
                content=base64.b64decode(request.content),
                created_by_user_id=identity.user_id,
                base_id=base_id,
            )
        else:
            raise PlatformValidationError("unsupported_import_source", request.source_type)
        complete_idempotent_operation(
            decision.record,
            response_ref={"import_job_id": str(job.id)},
        )
    except (PlatformValidationError, Stage06AuthorizationError, ValueError) as exc:
        raise _http_error(exc) from exc
    _commit_if_sqlalchemy(uow)
    return _import_job_response(job)


@router.get("/imports/{import_job_id}", response_model=ImportJobResponse)
def read_import_endpoint(
    import_job_id: UUID,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06TemplateImportUnitOfWork = Depends(get_stage06_template_import_uow),
) -> ImportJobResponse:
    try:
        workspace_id = workspace_id_for_import_job(uow, import_job_id)
        authorize_workspace_action(uow, identity, workspace_id, "import.read")
        job = read_import_job(uow, import_job_id)
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        raise _http_error(exc) from exc
    return _import_job_response(job)


@router.post("/imports/{import_job_id}/commit", response_model=ImportCommitResponse)
def commit_import_endpoint(
    import_job_id: UUID,
    request: CommitImportRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=160),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06TemplateImportUnitOfWork = Depends(get_stage06_template_import_uow),
) -> ImportCommitResponse:
    try:
        workspace_id = workspace_id_for_import_job(uow, import_job_id)
        actor = authorize_workspace_action(uow, identity, workspace_id, "import.commit")
        fingerprint = fingerprint_request(
            {
                "import_job_id": import_job_id,
                "request": request.model_dump(),
                "user_id": identity.user_id,
            }
        )
        decision = _begin_and_reserve(
            uow,
            workspace_id=workspace_id,
            operation="import.commit",
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
        )
        if decision.status == "replay":
            return ImportCommitResponse(**(decision.response_ref or {}))
        result = commit_import_job(
            uow,
            import_job_id,
            base_name=request.base_name,
            table_name=request.table_name,
            table_key=request.table_key,
            field_mapping=request.field_mapping,
            actor=actor,
        )
        response = ImportCommitResponse(
            import_job_id=str(result.import_job_id),
            status=result.status,
            resource_map=result.resource_map,
        )
        complete_idempotent_operation(
            decision.record,
            response_ref=response.model_dump(),
        )
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        _commit_if_sqlalchemy(uow)
        raise _http_error(exc) from exc
    _commit_if_sqlalchemy(uow)
    return response


@router.post("/bases/{base_id}/templates", response_model=TemplateResponse)
def save_base_as_template_endpoint(
    base_id: UUID,
    request: SaveBaseAsTemplateRequest,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06TemplateImportUnitOfWork = Depends(get_stage06_template_import_uow),
) -> TemplateResponse:
    try:
        workspace_id = workspace_id_for_base(uow, base_id)
        authorize_workspace_action(uow, identity, workspace_id, "template.save")
        template = save_base_as_template(
            uow,
            base_id,
            name=request.name,
            category=request.category,
            description=request.description,
            created_by_user_id=identity.user_id,
        )
    except (PlatformValidationError, Stage06AuthorizationError) as exc:
        raise _http_error(exc) from exc
    _commit_if_sqlalchemy(uow)
    return _template_response(template)


def _template_response(template: object) -> TemplateResponse:
    return TemplateResponse(
        id=str(template.id),
        name=template.name,
        category=template.category,
        description=template.description,
        version=template.version,
        status=template.status,
    )


def _import_job_response(job: object) -> ImportJobResponse:
    return ImportJobResponse(
        id=str(job.id),
        workspace_id=str(job.workspace_id),
        base_id=None if job.base_id is None else str(job.base_id),
        source_type=job.source_type,
        detected_schema=job.detected_schema,
        preview_rows=job.preview_rows,
        mapping=job.mapping,
        status=job.status,
        error_summary=job.error_summary,
    )


def _commit_if_sqlalchemy(uow: Stage06TemplateImportUnitOfWork) -> None:
    session = getattr(uow, "session", None)
    if session is not None:
        session.commit()


def _begin_and_reserve(
    uow: Stage06TemplateImportUnitOfWork,
    *,
    workspace_id: UUID,
    operation: str,
    idempotency_key: str,
    request_fingerprint: str,
):
    trace_id = f"idempotency:{operation}:{request_fingerprint[:24]}"
    try:
        decision = begin_idempotent_operation(
            uow,
            workspace_id=workspace_id,
            operation=operation,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            trace_id=trace_id,
        )
        if decision.status == "started":
            _commit_if_sqlalchemy(uow)
        return decision
    except IntegrityError:
        session = getattr(uow, "session", None)
        if session is None:
            raise
        session.rollback()
        return begin_idempotent_operation(
            uow,
            workspace_id=workspace_id,
            operation=operation,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            trace_id=trace_id,
        )


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, Stage06AuthorizationError):
        status_code = 404 if exc.code.endswith("_not_found") else 403
        return HTTPException(
            status_code=status_code,
            detail=error_detail(exc.code, str(exc)),
        )
    code = exc.code if isinstance(exc, PlatformValidationError) else "invalid_request"
    if code.endswith("_not_found"):
        status_code = 404
    elif code in {"idempotency_conflict", "idempotency_in_progress"}:
        status_code = 409
    else:
        status_code = 422
    return HTTPException(status_code=status_code, detail=error_detail(code, str(exc)))
