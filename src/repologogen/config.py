"""Configuration management for repologogen using YAML."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from jsonschema import ValidationError, validate


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""

    def __init__(self, message: str, file_path: Path | None = None):
        self.file_path = file_path
        super().__init__(message)


def has_unresolved_vars(value: str) -> bool:
    """Check if string has unresolved environment variables.

    Detects patterns like $VAR or ${VAR}.
    Ignores escaped variables like $$VAR.
    """
    if not isinstance(value, str):
        return False

    # Pattern to match $VAR or ${VAR}, but not $$VAR
    # (?<!\$) ensures not preceded by another $
    pattern = r"(?<!\$)\$\{?\w+\}?"
    return bool(re.search(pattern, value))


def find_unresolved_vars(data: dict[str, Any], prefix: str = "") -> list[tuple[str, str]]:
    """Find all unresolved environment variables in config data.

    Args:
        data: Configuration dictionary
        prefix: Key prefix for nested dicts

    Returns:
        List of tuples (key, value) where unresolved vars were found
    """
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
    """Validate that config data has no unresolved environment variables.

    Args:
        data: Configuration dictionary

    Raises:
        ConfigValidationError: If unresolved variables are found
    """
    unresolved = find_unresolved_vars(data)
    if unresolved:
        items = [f"  {key}={repr(value)}" for key, value in unresolved]
        message = "Configuration contains unresolved environment variables:\n" + "\n".join(items)
        raise ConfigValidationError(message)


@dataclass
class Config:
    """Configuration for logo generation."""

    model: str = "google/gemini-3-pro-image-preview"
    size: str = "1K"
    prompt_template: str | None = None
    style: str = "minimalist"
    visual_metaphor: str | None = None
    include_repo_name: bool = False
    icon_colors: list[str] = field(
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
    meta: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        """Create config from dictionary."""
        meta = data.pop("meta", {})
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in known_fields}
        return cls(meta=meta, **filtered_data)


# Strict JSON Schema for configuration validation
CONFIG_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "model": {"type": "string"},
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
    },
    "required": [
        "model",
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
    ],
}


def validate_config(data: dict[str, Any], file_path: Path | None = None) -> None:
    """Validate configuration data against schema."""
    try:
        validate(instance=data, schema=CONFIG_SCHEMA)
    except ValidationError as e:
        path = " -> ".join(str(p) for p in e.path) if e.path else "root"
        message = f"Config validation error at '{path}': {e.message}"
        raise ConfigValidationError(message, file_path) from None


def load_yaml_file(path: Path, validate_schema: bool = True) -> dict[str, Any]:
    """Load and validate configuration from a YAML file.

    Args:
        path: Path to the config file
        validate_schema: Whether to validate against schema (default: True)

    Returns:
        Configuration dictionary

    Raises:
        ConfigValidationError: If file is missing, invalid YAML, or fails schema validation
    """
    if not path.exists():
        raise ConfigValidationError(f"Configuration file not found: {path}", path)

    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigValidationError(f"Invalid YAML in config file: {e}", path) from None
    except OSError as e:
        raise ConfigValidationError(f"Cannot read config file: {e}", path) from None

    if data is None:
        data = {}

    if validate_schema:
        validate_config(data, path)

    return data


def expand_path(path: str) -> Path:
    """Expand environment variables and user home in path."""
    return Path(os.path.expandvars(os.path.expanduser(path)))


def merge_configs(base: dict, override: dict) -> dict:
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
    }


def load_merged_config(
    bundled_config_path: Path | None = None,
    user_config_path: Path | None = None,
    project_config_path: Path | None = None,
) -> Config:
    """Load and merge configuration (priority: project > user).

    Args:
        bundled_config_path: Override path to bundled defaults file (for testing)
        user_config_path: Override path to user config (~/.repologogen/config.yaml)
        project_config_path: Override path to project config (.config.yaml)

    Returns:
        Merged Config object

    Raises:
        ConfigValidationError: If no config file is found or any config file fails validation
    """
    sources: list[str] = []
    merged: dict[str, Any] = {}

    # Load and merge user config if it exists
    if user_config_path is None:
        user_config_path = Path.home() / ".repologogen" / "config.yaml"

    if user_config_path.exists():
        user_data = load_yaml_file(user_config_path)
        merged = user_data
        sources.append(str(user_config_path))

    # Load and merge project config if it exists (highest priority)
    if project_config_path is None:
        project_config_path = Path.cwd() / ".config.yaml"

    if project_config_path.exists():
        if merged:
            merge_configs(merged, load_yaml_file(project_config_path))
        else:
            merged = load_yaml_file(project_config_path)
        sources.append(str(project_config_path))

    # Require at least one config file
    if not sources:
        raise ConfigValidationError(
            "No configuration file found. Create either:\n"
            "  - ~/.repologogen/config.yaml (user config)\n"
            "  - .config.yaml in your project directory"
        )

    # Validate no unresolved environment variables in merged config
    validate_no_unresolved_vars(merged)

    merged["meta"] = {"sources": sources}
    return Config.from_dict(merged)


def get_api_key(project_path: Path | None = None) -> str | None:
    """Get OpenRouter API key from environment, .env files, or config."""
    # Environment variable
    api_key = os.getenv("OPENROUTER_API_KEY")
    if api_key:
        return api_key

    # .env files
    try:
        from dotenv import load_dotenv

        for env_path in [
            project_path / ".env" if project_path else None,
            Path.cwd() / ".env",
        ]:
            if env_path and env_path.exists():
                load_dotenv(env_path, override=False)
                api_key = os.getenv("OPENROUTER_API_KEY")
                if api_key:
                    return api_key
    except ImportError:
        pass

    # User config
    user_config_path = Path.home() / ".repologogen" / "config.yaml"
    if user_config_path.exists():
        try:
            with open(user_config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)
                return config.get("openrouter_api_key") if config else None
        except (yaml.YAMLError, OSError):
            pass

    return None
