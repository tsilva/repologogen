"""Tests for repologogen configuration module."""

from pathlib import Path

import pytest
import yaml

from repologogen.config import (
    Config,
    ConfigValidationError,
    find_unresolved_vars,
    get_bundled_defaults,
    has_unresolved_vars,
    load_merged_config,
    load_yaml_file,
    merge_configs,
    validate_config,
    validate_no_unresolved_vars,
)


class TestConfigModel:
    """Test Config model."""

    def test_default_values(self):
        """Test default configuration values."""
        config = Config()
        assert config.style == "minimalist"
        assert config.key_color == "#00FF00"
        assert config.output_path == "logo.png"
        assert config.targets == []
        assert config.trim is True
        assert config.compress is True
        assert config.refine_prompt is True

    def test_custom_values(self):
        """Test custom configuration values."""
        config = Config(style="pixel art", key_color="#FF00FF", output_path="assets/icon.png")
        assert config.style == "pixel art"
        assert config.key_color == "#FF00FF"
        assert config.output_path == "assets/icon.png"

    def test_from_dict(self):
        """Test creating config from dictionary."""
        data = {"style": "vintage", "key_color": "#0000FF"}
        config = Config.from_dict(data)
        assert config.style == "vintage"
        assert config.key_color == "#0000FF"
        assert config.output_path == "logo.png"  # Default preserved


class TestMergeConfigs:
    """Test merge_configs function."""

    def test_simple_merge(self):
        """Test merging simple dictionaries."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        merge_configs(base, override)
        assert base == {"a": 1, "b": 3, "c": 4}

    def test_flat_merge(self):
        """Test merging flat configuration dictionaries."""
        base = {"style": "minimalist", "size": "1K"}
        override = {"style": "pixel art"}
        merge_configs(base, override)
        assert base["style"] == "pixel art"
        assert base["size"] == "1K"  # Preserved

    def test_skips_metadata_keys(self):
        """Test that keys starting with _ are skipped."""
        base = {"a": 1}
        override = {"_meta": "ignored", "a": 2}
        merge_configs(base, override)
        assert base["a"] == 2
        assert "_meta" not in base


class TestSchemaValidation:
    """Test strict schema validation."""

    def test_valid_config_passes(self):
        """Test that valid configuration passes validation."""
        valid_config = get_bundled_defaults()
        # Should not raise
        validate_config(valid_config)

    def test_targets_must_be_known(self):
        invalid_config = {**get_bundled_defaults(), "targets": ["desktop"]}
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_config(invalid_config)
        assert "targets" in str(exc_info.value)

    def test_partial_override_config_passes(self):
        """Test that partial override configs are allowed."""
        invalid_config = {
            "model": "test",
            "size": "1K",
            "style": "minimalist",
            "output_path": "logo.png",
        }
        validate_config(invalid_config)

    def test_missing_required_field_fails_for_complete_validation(self):
        """Test that complete validation still requires bundled defaults."""
        invalid_config = {
            "model": "test",
            "size": "1K",
            "style": "minimalist",
            "output_path": "logo.png",
        }
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_config(invalid_config, require_complete=True)
        assert "validation error" in str(exc_info.value).lower()

    def test_unknown_property_fails(self):
        """Test that unknown properties fail validation."""
        invalid_config = {**get_bundled_defaults(), "unknown_field": "value"}
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_config(invalid_config)
        assert "Additional properties" in str(exc_info.value)

    def test_invalid_hex_color_fails(self):
        """Test that invalid hex color format fails validation."""
        invalid_config = {**get_bundled_defaults(), "key_color": "invalid"}
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_config(invalid_config)
        assert "key_color" in str(exc_info.value)

    def test_tolerance_out_of_range_fails(self):
        """Test that tolerance outside 0-255 range fails validation."""
        invalid_config = {**get_bundled_defaults(), "tolerance": 300}
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_config(invalid_config)
        assert "tolerance" in str(exc_info.value)

    def test_quality_out_of_range_fails(self):
        """Test that compress_quality outside 0-100 range fails validation."""
        invalid_config = {**get_bundled_defaults(), "compress_quality": 150}
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_config(invalid_config)
        assert "compress_quality" in str(exc_info.value)


class TestLoadYamlFile:
    """Test load_yaml_file function with strict validation."""

    def test_loads_valid_yaml(self, tmp_path):
        """Test loading valid YAML config."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(get_bundled_defaults()))

        result = load_yaml_file(config_file)
        assert "style" in result
        assert result["style"] == "minimalist"

    def test_raises_for_missing_file(self, tmp_path):
        """Test raises ConfigValidationError for missing file."""
        with pytest.raises(ConfigValidationError) as exc_info:
            load_yaml_file(tmp_path / "nonexistent.yaml")
        assert "not found" in str(exc_info.value).lower()

    def test_raises_for_invalid_yaml(self, tmp_path):
        """Test raises ConfigValidationError for invalid YAML."""
        config_file = tmp_path / "bad.yaml"
        config_file.write_text("not valid: yaml: : : :")

        with pytest.raises(ConfigValidationError) as exc_info:
            load_yaml_file(config_file)
        assert "invalid yaml" in str(exc_info.value).lower()

    def test_raises_for_invalid_schema(self, tmp_path):
        """Test raises ConfigValidationError for schema violations."""
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text(yaml.dump({"invalid": "data"}))

        with pytest.raises(ConfigValidationError) as exc_info:
            load_yaml_file(config_file)
        assert "validation error" in str(exc_info.value).lower()

    def test_can_skip_validation(self, tmp_path):
        """Test that validation can be disabled."""
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text(yaml.dump({"invalid": "data"}))

        # Should not raise when validate_schema=False
        result = load_yaml_file(config_file, validate_schema=False)
        assert "invalid" in result


class TestLoadMergedConfig:
    """Test load_merged_config function."""

    def test_uses_bundled_defaults(self):
        """Test that bundled defaults are used as base."""
        config = load_merged_config(
            user_config_path=Path("/nonexistent-user-config.yaml"),
            project_config_path=Path("/nonexistent-project-config.yaml"),
        )
        assert config.style == "minimalist"
        assert config.key_color == "#00FF00"

    def test_user_config_overrides_bundled(self, tmp_path):
        """Test user config overrides bundled defaults."""
        # Create user config
        user_config = tmp_path / "user_config.yaml"
        user_data = get_bundled_defaults()
        user_data["style"] = "user_custom"
        user_config.write_text(yaml.dump(user_data))

        config = load_merged_config(
            user_config_path=user_config,
            project_config_path=tmp_path / "missing-project.yaml",
        )
        assert config.style == "user_custom"
        assert config.key_color == "#00FF00"  # Bundled default preserved

    def test_project_config_overrides_user(self, tmp_path):
        """Test project config has highest priority."""
        # Create user config
        user_config = tmp_path / "user_config.yaml"
        user_data = get_bundled_defaults()
        user_data["style"] = "user_custom"
        user_config.write_text(yaml.dump(user_data))

        # Create project config
        project_config = tmp_path / "project_config.yaml"
        project_data = get_bundled_defaults()
        project_data["style"] = "project_custom"
        project_config.write_text(yaml.dump(project_data))

        config = load_merged_config(
            user_config_path=user_config,
            project_config_path=project_config,
        )
        assert config.style == "project_custom"

    def test_tracks_sources_in_meta(self, tmp_path):
        """Test that config sources are tracked in meta."""
        # Create user config
        user_config = tmp_path / "user_config.yaml"
        user_data = get_bundled_defaults()
        user_data["style"] = "custom"
        user_config.write_text(yaml.dump(user_data))

        config = load_merged_config(
            user_config_path=user_config,
            project_config_path=tmp_path / "missing-project.yaml",
        )
        sources = config.meta.get("sources", [])
        assert "bundled_defaults" in sources
        assert str(user_config) in sources

    def test_raises_on_invalid_user_config(self, tmp_path):
        """Test raises when user config is invalid."""
        # Create invalid user config
        user_config = tmp_path / "user_config.yaml"
        user_config.write_text(yaml.dump({"invalid": "config"}))

        with pytest.raises(ConfigValidationError):
            load_merged_config(
                user_config_path=user_config,
                project_config_path=tmp_path / "missing-project.yaml",
            )

    def test_raises_on_invalid_project_config(self, tmp_path):
        """Test raises when project config is invalid."""
        # Create invalid project config
        project_config = tmp_path / "project_config.yaml"
        project_config.write_text(yaml.dump({"invalid": "config"}))

        with pytest.raises(ConfigValidationError):
            load_merged_config(
                user_config_path=tmp_path / "missing-user.yaml",
                project_config_path=project_config,
            )

    def test_resolves_project_config_from_target_repo(self, tmp_path):
        """Test that target repo config is loaded from project_root."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".config.yaml").write_text(yaml.dump({"style": "repo_style"}))

        config = load_merged_config(
            user_config_path=tmp_path / "missing-user.yaml",
            project_root=project_root,
        )
        assert config.style == "repo_style"

    def test_asset_overrides_are_loaded(self, tmp_path):
        """Test that per-asset overrides are preserved in merged config."""
        project_config = tmp_path / "project_config.yaml"
        project_config.write_text(
            yaml.dump(
                {
                    "assets": {
                        "icon": {
                            "style": "flat badge",
                            "enabled": True,
                        }
                    }
                }
            )
        )

        config = load_merged_config(
            user_config_path=tmp_path / "missing-user.yaml",
            project_config_path=project_config,
        )
        assert config.assets["icon"]["style"] == "flat badge"
        assert config.assets["icon"]["enabled"] is True


class TestBundledDefaults:
    """Test bundled default configuration loading."""

    def test_loads_bundled_defaults(self):
        """Test that bundled defaults can be loaded."""
        defaults = get_bundled_defaults()
        assert "style" in defaults
        assert defaults["style"] == "minimalist"
        assert "model" in defaults

    def test_returns_dict(self):
        """Test that bundled defaults returns a dictionary."""
        defaults = get_bundled_defaults()
        assert isinstance(defaults, dict)


class TestHasUnresolvedVars:
    """Test has_unresolved_vars function."""

    def test_detects_dollar_var(self):
        """Test that $VAR pattern is detected."""
        assert has_unresolved_vars("$HOME/path") is True
        assert has_unresolved_vars("path/$VAR/end") is True

    def test_detects_braced_var(self):
        """Test that ${VAR} pattern is detected."""
        assert has_unresolved_vars("${HOME}/path") is True
        assert has_unresolved_vars("path/${VAR}/end") is True

    def test_ignores_escaped_var(self):
        """Test that $$VAR is treated as literal."""
        assert has_unresolved_vars("$$HOME/path") is False
        assert has_unresolved_vars("path/$$VAR/end") is False

    def test_ignores_non_string(self):
        """Test that non-strings return False."""
        assert has_unresolved_vars(None) is False
        assert has_unresolved_vars(123) is False
        assert has_unresolved_vars(["$VAR"]) is False

    def test_no_vars_in_plain_string(self):
        """Test that plain strings return False."""
        assert has_unresolved_vars("plain string") is False
        assert has_unresolved_vars("/path/to/file") is False
        assert has_unresolved_vars("color: #FF0000") is False


class TestFindUnresolvedVars:
    """Test find_unresolved_vars function."""

    def test_finds_single_var(self):
        """Test finding single unresolved var."""
        data = {"output_path": "$HOME/logo.png"}
        result = find_unresolved_vars(data)
        assert len(result) == 1
        assert result[0] == ("output_path", "$HOME/logo.png")

    def test_finds_multiple_vars(self):
        """Test finding multiple unresolved vars."""
        data = {
            "output_path": "$HOME/logo.png",
            "style": "$STYLE",
        }
        result = find_unresolved_vars(data)
        assert len(result) == 2

    def test_finds_vars_in_list(self):
        """Test finding vars in list values."""
        data = {
            "icon_colors": ["$COLOR1", "#FF0000", "$COLOR2"],
        }
        result = find_unresolved_vars(data)
        assert len(result) == 2
        assert ("icon_colors[0]", "$COLOR1") in result
        assert ("icon_colors[2]", "$COLOR2") in result

    def test_finds_vars_in_nested_dict(self):
        """Test finding vars in nested dict."""
        data = {
            "nested": {
                "deep": "$DEEP_VAR",
            },
        }
        result = find_unresolved_vars(data)
        assert len(result) == 1
        assert result[0] == ("nested.deep", "$DEEP_VAR")

    def test_returns_empty_when_no_vars(self):
        """Test empty list when no vars found."""
        data = {
            "output_path": "logo.png",
            "style": "minimalist",
        }
        result = find_unresolved_vars(data)
        assert len(result) == 0


class TestValidateNoUnresolvedVars:
    """Test validate_no_unresolved_vars function."""

    def test_passes_with_no_vars(self):
        """Test no error when no unresolved vars."""
        data = {"output_path": "logo.png"}
        validate_no_unresolved_vars(data)  # Should not raise

    def test_raises_with_unresolved_vars(self):
        """Test error raised when unresolved vars found."""
        data = {"output_path": "$HOME/logo.png"}
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_no_unresolved_vars(data)
        assert "unresolved environment variables" in str(exc_info.value)
        assert "$HOME/logo.png" in str(exc_info.value)

    def test_error_includes_all_vars(self):
        """Test error includes all unresolved vars."""
        data = {
            "output_path": "$HOME/logo.png",
            "style": "$STYLE",
        }
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_no_unresolved_vars(data)
        message = str(exc_info.value)
        assert "output_path" in message
        assert "style" in message


class TestLoadMergedConfigWithUnresolvedVars:
    """Test load_merged_config rejects unresolved variables."""

    def test_rejects_project_config_with_unresolved_vars(self, tmp_path):
        """Test rejects project config with unresolved vars."""
        project_config = tmp_path / "project_config.yaml"
        data = get_bundled_defaults()
        data["output_path"] = "$HOME/logo.png"
        project_config.write_text(yaml.dump(data))

        with pytest.raises(ConfigValidationError) as exc_info:
            load_merged_config(
                user_config_path=tmp_path / "missing-user.yaml",
                project_config_path=project_config,
            )

        assert "unresolved environment variables" in str(exc_info.value)

    def test_rejects_user_config_with_unresolved_vars(self, tmp_path):
        """Test rejects user config with unresolved vars."""
        user_config = tmp_path / "user_config.yaml"
        data = get_bundled_defaults()
        data["style"] = "$MY_STYLE"
        user_config.write_text(yaml.dump(data))

        with pytest.raises(ConfigValidationError) as exc_info:
            load_merged_config(
                user_config_path=user_config,
                project_config_path=tmp_path / "missing-project.yaml",
            )

        assert "unresolved environment variables" in str(exc_info.value)
