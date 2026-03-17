"""CLI workflow tests."""

from __future__ import annotations

import io
import json

from PIL import Image
from rich.console import Console

from repologogen import cli


class DummyGenerator:
    """Minimal image generator stub for workflow tests."""

    prompts: list[dict[str, str]] = []

    def __init__(self, project_path=None):
        self.project_path = project_path

    def generate(
        self,
        prompt,
        model,
        output_path,
        size="1K",
        aspect_ratio="1:1",
        reference_images=None,
    ):
        type(self).prompts.append(
            {
                "prompt": prompt,
                "model": model,
                "size": size,
                "aspect_ratio": aspect_ratio,
                "reference_images": list(reference_images or []),
                "output_path": str(output_path),
            }
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (1024, 1024), (0, 255, 0)).save(output_path, "PNG")


def _set_test_console(monkeypatch):
    buffer = io.StringIO()
    monkeypatch.setattr(
        cli,
        "console",
        Console(file=buffer, force_terminal=False, color_system=None),
    )
    return buffer


class TestRunGeneration:
    """Test end-to-end CLI workflows without external API calls."""

    def test_core_brand_dry_run_prints_bundle_summary(self, tmp_path, monkeypatch):
        _set_test_console(monkeypatch)
        (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n")
        (tmp_path / "README.md").write_text("# Demo\nA project.")

        result = cli.run_generation(
            project_path=tmp_path,
            bundle="core-brand",
            targets=["web-seo"],
            dry_run=True,
        )

        assert result == 0

    def test_core_brand_requires_targets(self, tmp_path, monkeypatch):
        _set_test_console(monkeypatch)
        (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n")

        result = cli.run_generation(
            project_path=tmp_path,
            bundle="core-brand",
        )

        assert result == 1

    def test_core_brand_bundle_writes_assets_and_manifest(self, tmp_path, monkeypatch):
        _set_test_console(monkeypatch)
        DummyGenerator.prompts = []
        monkeypatch.setattr(cli, "ImageGenerator", DummyGenerator)
        monkeypatch.setattr(cli, "get_api_key", lambda project_path=None: None)
        monkeypatch.setattr(cli, "digest_readme", lambda *args, **kwargs: "Generate brand assets.")

        def fake_metadata(*args, **kwargs):
            del args, kwargs
            return {
                "title": "Demo",
                "short_description": "Generate brand assets.",
                "social_title": "Demo brand assets",
                "social_description": "Generate brand assets.",
                "keywords": ["demo", "brand"],
            }

        monkeypatch.setattr(cli, "extract_repo_metadata", fake_metadata)

        (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n")
        (tmp_path / "README.md").write_text("# Demo\nA project.")

        result = cli.run_generation(
            project_path=tmp_path,
            bundle="core-brand",
            targets=["web-seo"],
        )

        assert result == 0
        manifest_path = tmp_path / "repologogen-assets" / "manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["bundle"] == "core-brand"
        assert (tmp_path / "repologogen-assets" / "logo" / "logo-1024.png").exists()
        assert (tmp_path / "repologogen-assets" / "web-seo" / "og-image-1200x630.png").exists()
        assert len(DummyGenerator.prompts) == 3
        assert "single bold symbol" in DummyGenerator.prompts[1]["prompt"]
        assert "legible at 16x16 and 32x32" in DummyGenerator.prompts[1]["prompt"]
        assert len(DummyGenerator.prompts[1]["reference_images"]) == 1
        assert DummyGenerator.prompts[2]["aspect_ratio"] == "40:21"
        assert len(DummyGenerator.prompts[2]["reference_images"]) == 1
        social_asset = next(
            asset for asset in manifest["assets"] if asset["key"] == "web-seo-og-image"
        )
        assert social_asset["strategy"] == "generated_from_logo_reference"

    def test_targeted_core_brand_writes_platform_assets(self, tmp_path, monkeypatch):
        _set_test_console(monkeypatch)
        DummyGenerator.prompts = []
        monkeypatch.setattr(cli, "ImageGenerator", DummyGenerator)
        monkeypatch.setattr(cli, "get_api_key", lambda project_path=None: None)
        monkeypatch.setattr(cli, "digest_readme", lambda *args, **kwargs: "Generate brand assets.")

        monkeypatch.setattr(
            cli,
            "extract_repo_metadata",
            lambda *args, **kwargs: {
                "title": "Demo",
                "short_description": "Generate brand assets.",
                "social_title": "Demo brand assets",
                "social_description": "Generate brand assets.",
                "keywords": ["demo", "brand"],
            },
        )

        (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n")
        (tmp_path / "README.md").write_text("# Demo\nA project.")

        result = cli.run_generation(
            project_path=tmp_path,
            bundle="core-brand",
            targets=["web-seo", "google-play", "apple-store"],
        )

        assert result == 0
        root = tmp_path / "repologogen-assets"
        assert (root / "logo" / "logo-1024.png").exists()
        assert (root / "icon" / "icon-1024.png").exists()
        assert (root / "web-seo" / "og-image-1200x630.png").exists()
        assert (root / "google-play" / "feature-graphic-1024x500.png").exists()
        assert (root / "apple-store" / "app-store-icon-1024.png").exists()
        assert (root / "web-seo" / "site.webmanifest").exists()

        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["targets"] == ["web-seo", "google-play", "apple-store"]
        assert len(DummyGenerator.prompts) == 4
        assert DummyGenerator.prompts[2]["aspect_ratio"] == "40:21"
        assert DummyGenerator.prompts[3]["aspect_ratio"] == "256:125"
        assert all(
            len(prompt["reference_images"]) == 1 for prompt in DummyGenerator.prompts[1:]
        )

    def test_logo_bundle_respects_output_override(self, tmp_path, monkeypatch):
        _set_test_console(monkeypatch)
        monkeypatch.setattr(cli, "ImageGenerator", DummyGenerator)
        monkeypatch.setattr(cli, "get_api_key", lambda project_path=None: None)

        (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n")
        output_path = "dist/logo.png"

        result = cli.run_generation(
            project_path=tmp_path,
            output_path=output_path,
        )

        assert result == 0
        assert (tmp_path / output_path).exists()
