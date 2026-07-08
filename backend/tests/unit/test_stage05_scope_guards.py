from __future__ import annotations

import inspect
from pathlib import Path

from app.services import agent_workflows, confirmation


BACKEND_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = BACKEND_ROOT / "app"


STAGE05_RUNTIME_FILES = [
    APP_ROOT / "agents" / "account_inventory_agent.py",
    APP_ROOT / "agents" / "bm_invite_draft_agent.py",
    APP_ROOT / "agents" / "card_binding_draft_agent.py",
    APP_ROOT / "agents" / "customer_reply_draft_agent.py",
    APP_ROOT / "agents" / "message_intake_router.py",
    APP_ROOT / "agents" / "recharge_draft_agent.py",
    APP_ROOT / "agents" / "schemas.py",
    APP_ROOT / "agents" / "stage05_state.py",
    APP_ROOT / "agents" / "stage05_supervisor.py",
    APP_ROOT / "services" / "agent_workflows.py",
]


FORBIDDEN_STAGE05_EXECUTION_TOKENS = (
    "execute_recharge_with_mock_provider",
    "MockRechargeProvider",
    "create_inventory_account",
    "confirm_account_assignment",
    "activate_inventory_account",
    "use_execution_ticket",
    "add_execution_ticket",
    "_create_execution_ticket",
    "PROVIDER_MODE=enabled",
)


FORBIDDEN_STAGE05_RUNTIME_PATH_PARTS = (
    "frontend",
    "mini_app",
    "miniapp",
    "rag",
    "pgvector",
    "capability_registry",
)


def test_stage05_runtime_does_not_call_provider_ticket_or_account_production_paths() -> None:
    offenders: list[str] = []

    for path in STAGE05_RUNTIME_FILES:
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_STAGE05_EXECUTION_TOKENS:
            if token in text:
                offenders.append(f"{path.relative_to(BACKEND_ROOT)} contains {token}")

    assert offenders == []


def test_stage05_confirmation_branches_stay_on_reply_or_noop_paths() -> None:
    source = "\n".join(
        [
            inspect.getsource(confirmation._confirm_stage05_business_draft),
            inspect.getsource(confirmation._confirm_stage05_customer_reply),
            inspect.getsource(confirmation._create_noop_execution_log),
        ]
    )

    assert "_create_execution_ticket" not in source
    assert "add_execution_ticket" not in source
    assert "execute_recharge_with_mock_provider" not in source
    assert 'provider="noop"' in source
    assert '"external_call_performed": False' in source
    assert "TelegramSendRequest(" in source
    assert "uow.add_send_request" in source
    assert '"target_allowed": target_allowed' in source


def test_stage05_workflow_can_only_persist_drafts_or_account_exception_actions() -> None:
    source = inspect.getsource(agent_workflows)

    assert "create_service_draft_from_stage05_candidate" in source
    assert "mark_account_exception_from_agent" in source
    assert "create_inventory_account" not in source
    assert "confirm_account_assignment" not in source
    assert "activate_inventory_account" not in source
    assert "execute_recharge_with_mock_provider" not in source


def test_stage05_did_not_add_runtime_surfaces_for_deferred_features() -> None:
    offenders = [
        path.relative_to(BACKEND_ROOT).as_posix()
        for path in APP_ROOT.rglob("*")
        if path.is_file()
        and path.suffix == ".py"
        and _is_stage05_related(path)
        and any(part in path.as_posix().lower() for part in FORBIDDEN_STAGE05_RUNTIME_PATH_PARTS)
    ]

    assert offenders == []


def test_stage05_skills_extension_does_not_add_dynamic_marketplace_or_provider_paths() -> None:
    skill_files = [
        APP_ROOT / "agents" / "stage05_skills.py",
        APP_ROOT / "agents" / "stage05_skill_matching.py",
    ]
    forbidden_tokens = (
        "importlib",
        "entry_points",
        "pkg_resources",
        "execute_recharge_with_mock_provider",
        "MockRechargeProvider",
        "execute_meta",
        "provider_readback(",
        "TelegramSendRequest(",
    )
    offenders: list[str] = []

    for path in skill_files:
        text = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            if token in text:
                offenders.append(f"{path.relative_to(BACKEND_ROOT)} contains {token}")

    assert offenders == []


def _is_stage05_related(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    return "stage05" in path.as_posix().lower() or "Stage05" in text
