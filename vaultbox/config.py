from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass


class ConfigurationError(ValueError):
    pass


def _required(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise ConfigurationError(f"{name} is not configured")
    return value


@dataclass(frozen=True)
class Settings:
    age_key: str
    age_recipient: str
    api_keys: tuple[str, ...]
    web_username: str
    web_password: str
    session_secret: str
    max_payload_bytes: int = 1024 * 1024
    sops_timeout_seconds: float = 30.0
    max_concurrency: int = 4
    cookie_secure: bool = True
    enable_docs: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        try:
            configured = json.loads(_required("VAULTBOX_API_KEYS"))
        except json.JSONDecodeError as exc:
            raise ConfigurationError("VAULTBOX_API_KEYS must be a JSON array") from exc
        if not isinstance(configured, list) or not configured or not all(isinstance(k, str) and k for k in configured):
            raise ConfigurationError("VAULTBOX_API_KEYS must be a non-empty JSON array of strings")
        return cls(
            age_key=_required("VAULTBOX_AGE_KEY"),
            age_recipient=_required("VAULTBOX_AGE_RECIPIENT"),
            api_keys=tuple(configured),
            web_username=_required("VAULTBOX_WEB_USERNAME"),
            web_password=_required("VAULTBOX_WEB_PASSWORD"),
            session_secret=_required("VAULTBOX_SESSION_SECRET"),
            max_payload_bytes=int(os.environ.get("VAULTBOX_MAX_PAYLOAD_BYTES", 1024 * 1024)),
            sops_timeout_seconds=float(os.environ.get("VAULTBOX_SOPS_TIMEOUT", 30)),
            max_concurrency=int(os.environ.get("VAULTBOX_MAX_CONCURRENCY", 4)),
            cookie_secure=os.environ.get("VAULTBOX_COOKIE_SECURE", "true").lower() in {"1", "true", "yes"},
            enable_docs=os.environ.get("VAULTBOX_ENABLE_DOCS", "false").lower() in {"1", "true", "yes"},
        )

    def api_key_matches(self, supplied: str) -> bool:
        supplied_digest = hashlib.sha256(supplied.encode()).hexdigest()
        matched = False
        for configured in self.api_keys:
            if configured.startswith("sha256:"):
                expected = configured[7:]
                import hmac
                matched |= hmac.compare_digest(supplied_digest, expected)
            else:
                import hmac
                matched |= hmac.compare_digest(supplied, configured)
        return matched
