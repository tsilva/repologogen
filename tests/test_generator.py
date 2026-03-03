"""Tests for repologogen generator module."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from repologogen.generator import (
    ImageGenerator,
    ImageGeneratorError,
    build_prompt,
)


class TestImageGenerator:
    """Test ImageGenerator class."""

    def test_raises_error_without_api_key(self, monkeypatch):
        """Test that missing API key raises error."""
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        # Mock get_api_key to return None (patch where it's used, not where it's defined)
        monkeypatch.setattr("repologogen.generator.get_api_key", lambda project_path=None: None)

        with pytest.raises(ImageGeneratorError) as exc_info:
            ImageGenerator()

        assert "API key required" in str(exc_info.value)

    def test_uses_provided_api_key(self):
        """Test that provided API key is used."""
        generator = ImageGenerator(api_key="test-key")
        assert generator.api_key == "test-key"

    def test_uses_env_var_api_key(self, monkeypatch):
        """Test that environment variable API key is used."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "env-key")
        generator = ImageGenerator()
        assert generator.api_key == "env-key"


class TestBuildPrompt:
    """Test build_prompt function."""

    def test_includes_project_name(self):
        """Test that project name is included in prompt."""
        prompt = build_prompt(
            project_name="MyProject",
            style="minimalist",
            icon_colors=["#FF0000"],
            key_color="#00FF00",
            visual_metaphor="geometric shapes",
            include_repo_name=False,
        )
        assert "MyProject" in prompt

    def test_includes_style(self):
        """Test that style is included in prompt."""
        prompt = build_prompt(
            project_name="Test",
            style="pixel art",
            icon_colors=["#FF0000"],
            key_color="#00FF00",
            visual_metaphor="test",
            include_repo_name=False,
        )
        assert "pixel art" in prompt

    def test_includes_colors(self):
        """Test that colors are included in prompt."""
        prompt = build_prompt(
            project_name="Test",
            style="minimalist",
            icon_colors=["#FF0000", "#00FF00"],
            key_color="#0000FF",
            visual_metaphor="test",
            include_repo_name=False,
        )
        assert "#FF0000" in prompt
        assert "#00FF00" in prompt

    def test_no_text_when_include_repo_name_false(self):
        """Test that no text instruction is added when include_repo_name is False."""
        prompt = build_prompt(
            project_name="TestProject",
            style="minimalist",
            icon_colors=["#FF0000"],
            key_color="#00FF00",
            visual_metaphor="test",
            include_repo_name=False,
        )
        assert "No text, no letters, no words" in prompt

    def test_text_when_include_repo_name_true(self):
        """Test that text instruction is added when include_repo_name is True."""
        prompt = build_prompt(
            project_name="TestProject",
            style="minimalist",
            icon_colors=["#FF0000"],
            key_color="#00FF00",
            visual_metaphor="test",
            include_repo_name=True,
        )
        assert 'Include "TestProject" as stylized text' in prompt

    def test_appends_additional_instructions(self):
        """Test that additional instructions are appended."""
        prompt = build_prompt(
            project_name="Test",
            style="minimalist",
            icon_colors=["#FF0000"],
            key_color="#00FF00",
            visual_metaphor="test",
            include_repo_name=False,
            additional_instructions="Make it blue.",
        )
        assert "Make it blue." in prompt

    def test_uses_custom_template(self):
        """Test that custom template is used when provided."""
        custom_template = "Custom: {PROJECT_NAME} with {STYLE}"
        prompt = build_prompt(
            project_name="MyApp",
            style="modern",
            icon_colors=["#FF0000"],
            key_color="#00FF00",
            visual_metaphor="test",
            include_repo_name=False,
            prompt_template=custom_template,
        )
        assert prompt == "Custom: MyApp with modern"


class TestPromptVariables:
    """Test prompt template variable substitution."""

    def test_all_variables_substituted(self):
        """Test that all template variables are substituted."""
        template = "Project: {PROJECT_NAME}, Style: {STYLE}, Colors: {ICON_COLORS}, Key: {KEY_COLOR}, Metaphor: {VISUAL_METAPHOR}, Text: {TEXT_INSTRUCTIONS}"

        prompt = build_prompt(
            project_name="TestApp",
            style="minimalist",
            icon_colors=["#FF0000", "#00FF00"],
            key_color="#0000FF",
            visual_metaphor="geometric shapes",
            include_repo_name=True,
            prompt_template=template,
        )

        # Check no template variables remain
        assert "{" not in prompt or "}" not in prompt.replace("{", "").replace("}", "")
        assert "TestApp" in prompt
        assert "minimalist" in prompt
        assert "#FF0000" in prompt
        assert "#0000FF" in prompt
