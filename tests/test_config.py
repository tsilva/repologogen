"""Tests for repologogen configuration module."""

import json
import tempfile
from pathlib import Path

import pytest

from repologogen.config import (
    Config,
    LogoConfig,
    load_merged_config,
    merge_configs,
    load_config_file,
    get_bundled_defaults,
)


class TestLogoConfig:
    """Test LogoConfig model."""

    def test_default_values(self):
        """Test default configuration values."""
        config = LogoConfig()
        assert config.style == "minimalist"
        assert config.key_color == "#00FF00"
        assert config.output_path == "logo.png"
        assert config.trim is True
        assert config.compress is True

    def test_custom_values(self):
        """Test custom configuration values."""
        config = LogoConfig(style="pixel art", key_color="#FF00FF", output_path="assets/icon.png")
        assert config.style == "pixel art"
        assert config.key_color == "#FF00FF"
        assert config.output_path == "assets/icon.png"


class TestConfigModel:
    """Test Config model."""

    def test_from_dict(self):
        """Test creating config from dictionary."""
        data = {"logo": {"style": "vintage", "key_color": "#0000FF"}}
        config = Config.from_dict(data)
        assert config.logo.style == "vintage"
        assert config.logo.key_color == "#0000FF"
        assert config.logo.output_path == "logo.png"  # Default preserved


class TestMergeConfigs:
    """Test merge_configs function."""

    def test_simple_merge(self):
        """Test merging simple dictionaries."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        merge_configs(base, override)
        assert base == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        """Test merging nested dictionaries."""
        base = {"logo": {"style": "minimalist", "size": "1K"}}
        override = {"logo": {"style": "pixel art"}}
        merge_configs(base, override)
        assert base["logo"]["style"] == "pixel art"
        assert base["logo"]["size"] == "1K"  # Preserved

    def test_skips_metadata_keys(self):
        """Test that keys starting with _ are skipped."""
        base = {"a": 1}
        override = {"_meta": "ignored", "a": 2}
        merge_configs(base, override)
        assert base["a"] == 2
        assert "_meta" not in base


class TestLoadConfigFile:
    """Test load_config_file function."""

    def test_loads_valid_json(self, tmp_path):
        """Test loading valid JSON config."""
        config_file = tmp_path / "config.json"
        data = {"logo": {"style": "modern"}}
        config_file.write_text(json.dumps(data))

        result = load_config_file(config_file)
        assert result == data

    def test_returns_empty_for_missing_file(self, tmp_path):
        """Test returns empty dict for missing file."""
        result = load_config_file(tmp_path / "nonexistent.json")
        assert result == {}

    def test_returns_empty_for_invalid_json(self, tmp_path):
        """Test returns empty dict for invalid JSON."""
        config_file = tmp_path / "bad.json"
        config_file.write_text("not valid json")

        result = load_config_file(config_file)
        assert result == {}


class TestLoadMergedConfig:
    """Test load_merged_config function."""

    def test_uses_defaults(self, tmp_path):
        """Test that defaults are used when no configs provided."""
        config = load_merged_config()
        assert config.logo.style == "minimalist"
        assert config.logo.key_color == "#00FF00"

    def test_user_config_overrides_defaults(self, tmp_path):
        """Test user config overrides defaults."""
        user_file = tmp_path / "user.json"
        user_file.write_text(json.dumps({"logo": {"style": "custom"}}))

        config = load_merged_config(user_config_path=user_file)
        assert config.logo.style == "custom"
        assert config.logo.key_color == "#00FF00"  # Default preserved

    def test_project_config_highest_priority(self, tmp_path):
        """Test project config has highest priority."""
        user_file = tmp_path / "user.json"
        user_file.write_text(json.dumps({"logo": {"style": "user"}}))

        project_file = tmp_path / "project.json"
        project_file.write_text(json.dumps({"logo": {"style": "project"}}))

        config = load_merged_config(user_config_path=user_file, project_config_path=project_file)
        assert config.logo.style == "project"  # Project wins


class TestBundledDefaults:
    """Test bundled default configuration loading."""

    def test_loads_bundled_defaults(self):
        """Test that bundled defaults can be loaded."""
        defaults = get_bundled_defaults()
        assert "logo" in defaults
        assert defaults["logo"]["style"] == "minimalist"
        assert defaults["logo"]["output_path"] == "logo.png"

    def test_load_merged_uses_defaults(self):
        """Test load_merged_config uses defaults."""
        config = load_merged_config()
        assert config.logo.style == "minimalist"
        # Check meta to verify defaults was used
        assert "defaults" in config.meta["sources"]

    def test_project_config_overrides_defaults(self, tmp_path):
        """Test project config overrides defaults."""
        project_file = tmp_path / "project.json"
        project_file.write_text(json.dumps({"logo": {"style": "project"}}))

        config = load_merged_config(project_config_path=project_file)
        assert config.logo.style == "project"
        # Verify both defaults and project in sources
        assert "defaults" in config.meta["sources"]
        assert "project" in config.meta["sources"]

    def test_user_config_overrides_defaults(self, tmp_path):
        """Test user config overrides defaults."""
        user_file = tmp_path / "user.json"
        user_file.write_text(json.dumps({"logo": {"style": "user"}}))

        config = load_merged_config(user_config_path=user_file)
        assert config.logo.style == "user"
        # Verify both defaults and user in sources
        assert "defaults" in config.meta["sources"]
        assert "user" in config.meta["sources"]
