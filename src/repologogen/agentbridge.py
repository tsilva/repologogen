"""Canonical AgentBridge endpoint and model routing."""

import os
from urllib.parse import urlparse

DEFAULT_BASE_URL = "http://127.0.0.1:8082/api/v1"


def base_url(value: str | None = None) -> str:
    value = (value or os.getenv("AGENTBRIDGE_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    parsed = urlparse(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.hostname == "openrouter.ai"
    ):
        raise ValueError("Configure an AgentBridge HTTP endpoint")
    return value


def model_id(model: str) -> str:
    model = model.strip()
    if (
        model.startswith(("codex/", "claudecode/"))
        or (model.startswith("openrouter/") and model.count("/") >= 2)
        or model == "openrouter/default"
    ):
        return model
    return f"openrouter/{model}"
