"""Tests for repologogen generator module."""

import json
from unittest.mock import Mock, patch

import pytest

from repologogen.generator import (
    ImageGenerator,
    ImageGeneratorError,
    build_prompt,
    digest_readme,
    extract_repo_metadata,
    refine_prompt,
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
        template = (
            "Project: {PROJECT_NAME}, Style: {STYLE}, Colors: {ICON_COLORS}, "
            "Key: {KEY_COLOR}, Metaphor: {VISUAL_METAPHOR}, Text: {TEXT_INSTRUCTIONS}"
        )

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


class TestBuildPromptWithDescription:
    """Test build_prompt with project_description parameter."""

    def test_description_appears_in_prompt(self):
        """Test that project description is included in prompt."""
        prompt = build_prompt(
            project_name="MyProject",
            style="minimalist",
            icon_colors=["#FF0000"],
            key_color="#00FF00",
            visual_metaphor="geometric shapes",
            include_repo_name=False,
            project_description="A CLI tool for generating logos",
        )
        assert "A CLI tool for generating logos" in prompt

    def test_works_without_description(self):
        """Test backward compatibility when no description is provided."""
        prompt = build_prompt(
            project_name="MyProject",
            style="minimalist",
            icon_colors=["#FF0000"],
            key_color="#00FF00",
            visual_metaphor="geometric shapes",
            include_repo_name=False,
        )
        assert "MyProject" in prompt
        # No double spaces or orphan periods from empty description
        assert ".." not in prompt

    def test_var_override_takes_precedence(self):
        """Test that --var PROJECT_DESCRIPTION overrides extracted value."""
        prompt = build_prompt(
            project_name="MyProject",
            style="minimalist",
            icon_colors=["#FF0000"],
            key_color="#00FF00",
            visual_metaphor="geometric shapes",
            include_repo_name=False,
            project_description="From README",
            template_vars={"PROJECT_DESCRIPTION": " Custom override."},
        )
        assert "Custom override" in prompt
        assert "From README" not in prompt


class TestDigestReadme:
    """Test digest_readme function."""

    def test_returns_description_on_success(self):
        """Test that a description is extracted from API response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "A tool for generating logos."}}]
        }

        with patch("repologogen.generator.httpx.Client") as mock_client_cls:
            mock_client = Mock()
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = digest_readme("# My Project\nDoes stuff", "test-key")
            assert result == "A tool for generating logos."

            # Verify the API was called with correct model
            call_args = mock_client.post.call_args
            payload = call_args[1]["json"]
            assert payload["model"] == "google/gemini-3-flash-preview"

    def test_returns_empty_on_api_error(self):
        """Test graceful fallback on API error."""
        with patch("repologogen.generator.httpx.Client") as mock_client_cls:
            mock_client = Mock()
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=False)
            mock_client.post.side_effect = Exception("API error")
            mock_client_cls.return_value = mock_client

            result = digest_readme("# My Project", "test-key")
            assert result == ""

    def test_returns_empty_for_blank_readme(self):
        """Test that blank README content returns empty string."""
        result = digest_readme("", "test-key")
        assert result == ""
        result = digest_readme("   ", "test-key")
        assert result == ""


class TestExtractRepoMetadata:
    """Test extract_repo_metadata function."""

    def test_returns_structured_metadata_on_success(self):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "title": "RepoLogoGen",
                                "short_description": "Generate repo brand assets.",
                                "social_title": "RepoLogoGen",
                                "social_description": "Generate repo brand assets.",
                                "keywords": ["logos", "seo"],
                            }
                        )
                    }
                }
            ]
        }

        with patch("repologogen.generator.httpx.Client") as mock_client_cls:
            mock_client = Mock()
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = extract_repo_metadata(
                "# RepoLogoGen",
                "test-key",
                "RepoLogoGen",
                "python",
            )

            assert result["title"] == "RepoLogoGen"
            assert result["keywords"] == ["logos", "seo"]

    def test_falls_back_on_invalid_json(self):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "not json"}}]}

        with patch("repologogen.generator.httpx.Client") as mock_client_cls:
            mock_client = Mock()
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = extract_repo_metadata(
                "# RepoLogoGen",
                "test-key",
                "RepoLogoGen",
                "python",
            )

            assert result["title"] == "RepoLogoGen"
            assert "python" in result["keywords"]


class TestRefinePrompt:
    """Test refine_prompt function."""

    def test_returns_refined_text_on_success(self):
        """Test that a refined prompt is returned from API response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Refined prompt text."}}]
        }

        with patch("repologogen.generator.httpx.Client") as mock_client_cls:
            mock_client = Mock()
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = refine_prompt("Messy redundant prompt", "google/gemini-3-pro", "test-key")
            assert result == "Refined prompt text."

    def test_system_prompt_includes_target_model(self):
        """Test that the system prompt mentions the target model."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "Refined."}}]}

        with patch("repologogen.generator.httpx.Client") as mock_client_cls:
            mock_client = Mock()
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            refine_prompt("Test prompt", "google/gemini-3-pro", "test-key")

            call_args = mock_client.post.call_args
            payload = call_args[1]["json"]
            system_msg = payload["messages"][0]["content"]
            assert "google/gemini-3-pro" in system_msg

    def test_returns_original_on_api_error(self):
        """Test graceful fallback on API error."""
        with patch("repologogen.generator.httpx.Client") as mock_client_cls:
            mock_client = Mock()
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=False)
            mock_client.post.side_effect = Exception("API error")
            mock_client_cls.return_value = mock_client

            result = refine_prompt("Original prompt", "some-model", "test-key")
            assert result == "Original prompt"

    def test_returns_as_is_for_empty_prompt(self):
        """Test that empty prompt is returned without API call."""
        with patch("repologogen.generator.httpx.Client") as mock_client_cls:
            result = refine_prompt("", "some-model", "test-key")
            assert result == ""
            mock_client_cls.assert_not_called()

            result = refine_prompt("   ", "some-model", "test-key")
            assert result == "   "
            mock_client_cls.assert_not_called()
