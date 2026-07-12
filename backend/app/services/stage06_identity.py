from dataclasses import dataclass
from typing import Literal

from app.core.config import Settings


Stage06IdentitySource = Literal[
    "development_header",
    "verified_adapter",
    "telegram_binding",
]


class Stage06IdentityError(RuntimeError):
    def __init__(self, code: str, *, status_code: int = 401) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class Stage06RequestIdentity:
    user_id: str
    source: Stage06IdentitySource
    telegram_user_id: str | None = None


def resolve_stage06_request_identity(
    settings: Settings,
    development_user_id: str | None,
    verified_user_id: str | None = None,
) -> Stage06RequestIdentity:
    verified = _normalized_user_id(verified_user_id)
    if verified is not None:
        return Stage06RequestIdentity(
            user_id=verified,
            source="verified_adapter",
        )

    if settings.environment in {"staging", "production"}:
        raise Stage06IdentityError("stage06_verified_identity_required")

    development = _normalized_user_id(development_user_id)
    if development is None:
        raise Stage06IdentityError("stage06_identity_required")
    return Stage06RequestIdentity(
        user_id=development,
        source="development_header",
    )


def _normalized_user_id(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
