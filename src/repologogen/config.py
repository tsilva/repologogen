"""Configuration management for repologogen using YAML."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from jsonschema import ValidationError, validate

ASSET_NAMES = ("logo", "icon", "favicon", "social_card")
TARGET_NAMES = ("web-seo", "google-play", "apple-store")
ASSET_OVERRIDE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "enabled": {"type": "boolean"},
        "style": {"type": "string"},
        "visual_metaphor": {"type": ["string", "null"]},
        "include_repo_name": {"type": "boolean"},
        "icon_colors": {
            "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "string"}]
        },
        "additional_instructions": {"type": "string"},
        "model": {"type": "string"},
        "size": {"type": "string"},
        "prompt_template": {"type": ["string", "null"]},
    },
}


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""

    def __init__(self, message: str, file_path: Path | None = None):
        self.file_path = file_path
        super().__init__(message)


@dataclass
class MetadataConfig:
    """Configuration for generated metadata outputs."""

    enabled: bool = True


@dataclass
class Config:
    """Configuration for logo and asset generation."""

    model: str = "google/gemini-3-pro-image-preview"
    text_model: str = "google/gemini-3-flash-preview"
    size: str = "1K"
    prompt_template: str | None = None
    style: str = "minimalist"
    visual_metaphor: str | None = None
    include_repo_name: bool = False
    icon_colors: list[str] | str = field(
        default_factory=lambda: ["#58a6ff", "#d29922", "#a371f7", "#7aa2f7", "#f97583"]
    )
    additional_instructions: str = ""
    key_color: str = "#00FF00"
    tolerance: int = 70
    output_path: str = "logo.png"
    compress: bool = True
    compress_quality: int = 80
    trim: bool = True
    trim_margin: int = 5
    refine_prompt: bool = True
    bundle: str = "logo"
    targets: list[str] = field(default_factory=list)
    assets_dir: str = "repologogen-assets"
    manifest_path: str = "repologogen-assets/manifest.json"
    metadata: MetadataConfig = field(default_factory=MetadataConfig)
    assets: dict[str, dict[str, Any]] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Config:
        """Create config from dictionary."""
        raw = dict(data)
        meta = raw.pop("meta", {})
        metadata_data = raw.pop("metadata", {}) or {}
        assets_data = raw.pop("assets", {}) or {}
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in raw.items() if k in known_fields}
        return cls(
            metadata=MetadataConfig(**metadata_data),
            assets={name: dict(values or {}) for name, values in assets_data.items()},
            meta=meta,
            **filtered_data,
        )


CONFIG_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "model": {"type": "string"},
        "text_model": {"type": "string"},
        "size": {"type": "string"},
        "prompt_template": {"type": ["string", "null"]},
        "style": {"type": "string"},
        "visual_metaphor": {"type": ["string", "null"]},
        "include_repo_name": {"type": "boolean"},
        "icon_colors": {
            "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "string"}]
        },
        "additional_instructions": {"type": "string"},
        "key_color": {"type": "string", "pattern": "^#[0-9A-Fa-f]{6}$"},
        "tolerance": {"type": "integer", "minimum": 0, "maximum": 255},
        "output_path": {"type": "string"},
        "compress": {"type": "boolean"},
        "compress_quality": {"type": "integer", "minimum": 0, "maximum": 100},
        "trim": {"type": "boolean"},
        "trim_margin": {"type": "integer", "minimum": 0, "maximum": 25},
        "refine_prompt": {"type": "boolean"},
        "bundle": {"type": "string", "enum": ["logo", "core-brand"]},
        "targets": {
            "type": "array",
            "items": {"type": "string", "enum": list(TARGET_NAMES)},
            "uniqueItems": True,
        },
        "assets_dir": {"type": "string"},
        "manifest_path": {"type": "string"},
        "metadata": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "enabled": {"type": "boolean"},
            },
        },
        "assets": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "logo": ASSET_OVERRIDE_SCHEMA,
                "icon": ASSET_OVERRIDE_SCHEMA,
                "favicon": ASSET_OVERRIDE_SCHEMA,
                "social_card": ASSET_OVERRIDE_SCHEMA,
            },
        },
        "openrouter_api_key": {"type": "string"},
    },
}

COMPLETE_CONFIG_REQUIRED_FIELDS = [
    "model",
    "text_model",
    "size",
    "prompt_template",
    "style",
    "visual_metaphor",
    "include_repo_name",
    "icon_colors",
    "additional_instructions",
    "key_color",
    "tolerance",
    "output_path",
    "compress",
    "compress_quality",
    "trim",
    "trim_margin",
    "refine_prompt",
    "bundle",
    "targets",
    "assets_dir",
    "manifest_path",
    "metadata",
    "assets",
]

COMPLETE_CONFIG_SCHEMA: dict[str, Any] = {
    **CONFIG_SCHEMA,
    "required": COMPLETE_CONFIG_REQUIRED_FIELDS,
}


def has_unresolved_vars(value: str) -> bool:
    """Check if a string has unresolved environment variables."""
    if not isinstance(value, str):
        return False

    pattern = r"(?<!\$)\$\{?\w+\}?"
    return bool(re.search(pattern, value))


def find_unresolved_vars(data: dict[str, Any], prefix: str = "") -> list[tuple[str, str]]:
    """Find all unresolved environment variables in config data."""
    unresolved: list[tuple[str, str]] = []

    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key

        if isinstance(value, str):
            if has_unresolved_vars(value):
                unresolved.append((full_key, value))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, str) and has_unresolved_vars(item):
                    unresolved.append((f"{full_key}[{i}]", item))
        elif isinstance(value, dict):
            unresolved.extend(find_unresolved_vars(value, full_key))

    return unresolved


def validate_no_unresolved_vars(data: dict[str, Any]) -> None:
    """Validate that config data has no unresolved environment variables."""
    unresolved = find_unresolved_vars(data)
    if unresolved:
        items = [f"  {key}={repr(value)}" for key, value in unresolved]
        message = "Configuration contains unresolved environment variables:\n" + "\n".join(items)
        raise ConfigValidationError(message)


def validate_config(
    data: dict[str, Any],
    file_path: Path | None = None,
    *,
    require_complete: bool = False,
) -> None:
    """Validate configuration data against schema."""
    schema = COMPLETE_CONFIG_SCHEMA if require_complete else CONFIG_SCHEMA

    try:
        validate(instance=data, schema=schema)
    except ValidationError as e:
        path = " -> ".join(str(p) for p in e.path) if e.path else "root"
        message = f"Config validation error at '{path}': {e.message}"
        raise ConfigValidationError(message, file_path) from None


def load_yaml_file(path: Path, validate_schema: bool = True) -> dict[str, Any]:
    """Load and validate configuration from a YAML file."""
    if not path.exists():
        raise ConfigValidationError(f"Configuration file not found: {path}", path)

    try:
        with open(path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as e:
        raise ConfigValidationError(f"Invalid YAML in config file: {e}", path) from None
    except OSError as e:
        raise ConfigValidationError(f"Cannot read config file: {e}", path) from None

    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ConfigValidationError("Configuration root must be a mapping", path)

    if validate_schema:
        validate_config(data, path)

    return data


def expand_path(path: str) -> Path:
    """Expand environment variables and user home in path."""
    return Path(os.path.expandvars(os.path.expanduser(path)))


def merge_configs(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge override into base (modifies base in-place)."""
    for key, value in override.items():
        if key.startswith("_"):
            continue
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            merge_configs(base[key], value)
        else:
            base[key] = value
    return base


def get_bundled_defaults() -> dict[str, Any]:
    """Load bundled default configuration."""
    return {
        "model": "google/gemini-3-pro-image-preview",
        "text_model": "google/gemini-3-flash-preview",
        "size": "1K",
        "prompt_template": None,
        "style": "minimalist",
        "visual_metaphor": None,
        "include_repo_name": False,
        "icon_colors": ["#58a6ff", "#d29922", "#a371f7", "#7aa2f7", "#f97583"],
        "additional_instructions": "",
        "key_color": "#00FF00",
        "tolerance": 70,
        "output_path": "logo.png",
        "compress": True,
        "compress_quality": 80,
        "trim": True,
        "trim_margin": 5,
        "refine_prompt": True,
        "bundle": "logo",
        "targets": [],
        "assets_dir": "repologogen-assets",
        "manifest_path": "repologogen-assets/manifest.json",
        "metadata": {"enabled": True},
        "assets": {name: {} for name in ASSET_NAMES},
    }


def load_merged_config(
    bundled_config_path: Path | None = None,
    user_config_path: Path | None = None,
    project_config_path: Path | None = None,
    *,
    project_root: Path | None = None,
    require_user_config: bool = False,
    require_project_config: bool = False,
) -> Config:
    """Load and merge configuration (priority: CLI > project > user > defaults)."""
    del bundled_config_path  # Kept for backward-compatible signature.

    merged = get_bundled_defaults()
    sources = ["bundled_defaults"]

    resolved_user_config = user_config_path or expand_path("~/.repologogen/config.yaml")
    if resolved_user_config.exists():
        merge_configs(merged, load_yaml_file(resolved_user_config))
        sources.append(str(resolved_user_config))
    elif require_user_config:
        raise ConfigValidationError(
            f"Configuration file not found: {resolved_user_config}", resolved_user_config
        )

    resolved_project_config = project_config_path
    if resolved_project_config is None:
        base_path = project_root or Path.cwd()
        resolved_project_config = base_path / ".config.yaml"

    if resolved_project_config.exists():
        merge_configs(merged, load_yaml_file(resolved_project_config))
        sources.append(str(resolved_project_config))
    elif require_project_config:
        raise ConfigValidationError(
            f"Configuration file not found: {resolved_project_config}", resolved_project_config
        )

    validate_no_unresolved_vars(merged)
    validate_config(merged, require_complete=True)

    merged["meta"] = {"sources": sources}
    return Config.from_dict(merged)


def get_api_key(project_path: Path | None = None) -> str | None:
    """Get OpenRouter API key from environment or user config."""
    del project_path

    api_key = os.getenv("OPENROUTER_API_KEY")
    if api_key:
        return api_key

    user_config_path = expand_path("~/.repologogen/config.yaml")
    if user_config_path.exists():
        try:
            with open(user_config_path, encoding="utf-8") as handle:
                config = yaml.safe_load(handle) or {}
        except (yaml.YAMLError, OSError):
            return None

        api_key = config.get("openrouter_api_key")
        return api_key if isinstance(api_key, str) else None

    return None
