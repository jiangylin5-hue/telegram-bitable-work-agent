from __future__ import annotations

import os
from pathlib import Path


def load_env_file(path: Path) -> list[str]:
    if not path.exists():
        return []
    loaded: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        if not os.environ.get(key):
            os.environ[key] = _unquote(value.strip())
        loaded.append(key)
    return loaded


def load_default_stage06_env(backend_root: Path) -> list[str]:
    env_path = Path(os.getenv("STAGE06_ENV_FILE", str(backend_root / ".env")))
    return load_env_file(env_path)


def safe_loaded_key_names(keys: list[str]) -> list[str]:
    secret_fragments = ("KEY", "TOKEN", "SECRET", "PASSWORD")
    return sorted(
        key
        for key in keys
        if not any(fragment in key.upper() for fragment in secret_fragments)
    )


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
