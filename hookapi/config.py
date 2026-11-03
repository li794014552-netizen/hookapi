"""Load HookAPI settings from YAML with ${ENV} expansion."""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml
from pydantic import BaseModel

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _resolve_env(value: str) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in os.environ:
            raise KeyError(f"environment variable {key!r} is not set")
        return os.environ[key]

    return _ENV_PATTERN.sub(repl, value)


class AppConfig(BaseModel):
    hmac_secret: str
    database_path: Path
    forward_url: str | None = None


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    with config_path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    if not isinstance(raw, dict):
        raise ValueError(f"config root must be a mapping: {config_path}")

    hmac_secret = raw.get("hmac_secret")
    if not isinstance(hmac_secret, str):
        raise ValueError("hmac_secret must be a string")
    hmac_secret = _resolve_env(hmac_secret)

    database_path = raw.get("database_path")
    if database_path is None:
        raise ValueError("database_path is required")
    database_path = Path(database_path)

    forward_url = raw.get("forward_url", None)
    if isinstance(forward_url, str):
        forward_url = _resolve_env(forward_url)
    elif forward_url is not None:
        raise ValueError("forward_url must be a string or null")

    return AppConfig(
        hmac_secret=hmac_secret,
        database_path=database_path,
        forward_url=forward_url,
    )
