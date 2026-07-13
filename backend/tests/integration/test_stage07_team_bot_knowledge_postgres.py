import os
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.database import get_session
from app.main import create_app
from app.models.audit import OpsAuditEvent
from app.models.stage06_hardening import Stage06IdempotencyRecord
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import SqlAlchemyStage06PlatformUnitOfWork
from tests.integration.test_stage07_governance_postgres import (
    DATABASE_URL_ENV,
    Stage06Postgres,
    _session_override,
    stage06_postgres,
)

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not os.getenv(DATABASE_URL_ENV),
        reason=f'{DATABASE_URL_ENV} is required for disposable Team Bot PostgreSQL tests',
    ),
]


def test_team_bot_empty_context_is_idempotent_and_audited_in_postgres(
    stage06_postgres: Stage06Postgres,
) -> None:
    app = create_app()
    app.dependency_overrides[get_session] = _session_override(stage06_postgres.session_factory)
    suffix = uuid4().hex[:8]
    with TestClient(app) as owner:
        owner.headers['X-Stage06-User-Id'] = 'team-bot-owner'
        workspace_id = owner.post(
            '/workspaces',
            json={'name': f'Team bot {suffix}', 'owner_user_id': 'team-bot-owner'},
        ).json()['id']
        base_id = owner.post(f'/workspaces/{workspace_id}/bases', json={'name': 'Operations'}).json()['id']
        table_id = owner.post(
            f'/bases/{base_id}/tables',
            json={'name': 'Tasks', 'key': f'tasks_{suffix}'},
        ).json()['id']
        owner.post(f'/tables/{table_id}/fields', json={'name': 'Title', 'key': 'title', 'field_type': 'text'})
        view_id = owner.post(
            f'/bases/{base_id}/views',
            json={'table_id': table_id, 'name': 'Current tasks', 'view_type': 'grid', 'config': {'fields': ['title']}},
        ).json()['id']

    with stage06_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        employee = create_digital_employee(
            uow,
            UUID(base_id),
            name='Team summary',
            description='Safe view summary only.',
            telegram_alias='team-private',
            accessible_tables=[table_id],
            accessible_views=[view_id],
            allowed_actions=['summarize'],
            actor=Actor(actor_type='user', actor_id='team-bot-owner', role='owner'),
        )
        session.commit()
        employee_id = str(employee.id)

    with TestClient(app) as owner:
        owner.headers['X-Stage06-User-Id'] = 'team-bot-owner'
        contacts = owner.get(f'/mini-app/workspaces/{workspace_id}/team-bot-contacts')
        first = owner.post(
            f'/mini-app/team-bots/{employee_id}/summaries',
            headers={'Idempotency-Key': 'team-bot-empty-1'},
            json={'base_id': base_id, 'view_id': view_id},
        )
        replay = owner.post(
            f'/mini-app/team-bots/{employee_id}/summaries',
            headers={'Idempotency-Key': 'team-bot-empty-1'},
            json={'base_id': base_id, 'view_id': view_id},
        )

    assert contacts.status_code == 200
    assert contacts.json()['contacts'] == [{
        'id': employee_id,
        'base_id': base_id,
        'name': 'Team summary',
        'description': 'Safe view summary only.',
        'available_intents': ['summarize'],
    }]
    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()
    assert first.json()['kind'] == 'empty_context'
    assert first.json()['citations'] == []
    assert 'team-private' not in (contacts.text + first.text)

    with stage06_postgres.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(OpsAuditEvent).where(
            OpsAuditEvent.event_type == 'stage07.team_bot_summary',
        )) == 1
        assert session.scalar(select(func.count()).select_from(Stage06IdempotencyRecord).where(
            Stage06IdempotencyRecord.operation == 'stage07.team_bot.summary',
        )) == 1
