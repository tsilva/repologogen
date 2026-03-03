import copy
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class LogoConfig:
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


@dataclass
class Config:
    """Root configuration model."""

    logo: LogoConfig = field(default_factory=LogoConfig)
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        """Create config from dictionary."""
        logo_data = data.get("logo", {})
        return cls(
            logo=LogoConfig(**logo_data),
            meta=data.get("meta", {}),
        )


DEFAULTS: dict[str, Any] = {
    "logo": {
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
}


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

    # Tool config
    config_path = Path.home() / ".repologogen" / "config.json"
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                return json.load(f).get("openrouter_api_key")
        except (json.JSONDecodeError, OSError):
            pass

    return None


def load_config_file(path: Path) -> dict[str, Any]:
    """Load configuration from a JSON file."""
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


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


def load_merged_config(
    user_config_path: Path | None = None,
    project_config_path: Path | None = None,
) -> Config:
    """Load and merge configuration (priority: project > user > defaults)."""
    merged = copy.deepcopy(DEFAULTS)
    sources = ["defaults"]

    if user_config_path:
        user_data = load_config_file(user_config_path)
        if user_data:
            merge_configs(merged, user_data)
            sources.append("user")

    if project_config_path:
        project_data = load_config_file(project_config_path)
        if project_data:
            merge_configs(merged, project_data)
            sources.append("project")

    merged["meta"] = {"sources": sources}
    return Config.from_dict(merged)


def get_bundled_defaults() -> dict[str, Any]:
    """Load bundled default configuration from package."""
    import importlib.resources as pkg_resources

    try:
        with (
            pkg_resources.files("repologogen")
            .joinpath("default_config.json")
            .open("r", encoding="utf-8") as f
        ):
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return DEFAULTS
