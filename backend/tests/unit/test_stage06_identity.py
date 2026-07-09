import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api import deps
from app.core.config import Settings
from app.services.stage06_identity import (
    Stage06IdentityError,
    resolve_stage06_request_identity,
)


def test_stage06_identity_requires_header_in_local() -> None:
    with pytest.raises(Stage06IdentityError) as denied:
        resolve_stage06_request_identity(
            Settings(environment="local"),
            development_user_id=None,
        )

    assert denied.value.code == "stage06_identity_required"


def test_stage06_identity_accepts_trimmed_development_user_in_local() -> None:
    identity = resolve_stage06_request_identity(
        Settings(environment="local"),
        development_user_id="  owner-1  ",
    )

    assert identity.user_id == "owner-1"
    assert identity.source == "development_header"
    assert identity.telegram_user_id is None


def test_stage06_identity_rejects_development_header_in_production() -> None:
    with pytest.raises(Stage06IdentityError) as denied:
        resolve_stage06_request_identity(
            Settings(environment="production"),
            development_user_id="owner-1",
        )

    assert denied.value.code == "stage06_verified_identity_required"


def test_stage06_identity_accepts_verified_adapter_in_production() -> None:
    identity = resolve_stage06_request_identity(
        Settings(environment="production"),
        development_user_id="spoofed-owner",
        verified_user_id="owner-1",
    )

    assert identity.user_id == "owner-1"
    assert identity.source == "verified_adapter"


def test_stage06_identity_rejects_empty_verified_identity() -> None:
    with pytest.raises(Stage06IdentityError) as denied:
        resolve_stage06_request_identity(
            Settings(environment="production"),
            development_user_id=None,
            verified_user_id="   ",
        )

    assert denied.value.code == "stage06_verified_identity_required"


def _identity_test_client() -> TestClient:
    app = FastAPI()

    @app.get("/identity")
    def read_identity(
        identity=Depends(deps.get_stage06_request_identity),
    ) -> dict[str, str]:
        return {"user_id": identity.user_id, "source": identity.source}

    return TestClient(app)


def test_stage06_identity_dependency_returns_401_without_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "local")

    response = _identity_test_client().get("/identity")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "stage06_identity_required"


def test_stage06_identity_dependency_reads_development_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "local")

    response = _identity_test_client().get(
        "/identity",
        headers={"X-Stage06-User-Id": "owner-1"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "owner-1",
        "source": "development_header",
    }


def test_stage06_identity_dependency_fails_closed_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")

    response = _identity_test_client().get(
        "/identity",
        headers={"X-Stage06-User-Id": "owner-1"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "stage06_verified_identity_required"
