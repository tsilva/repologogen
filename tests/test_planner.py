"""Tests for repologogen planner module."""

from repologogen.config import Config
from repologogen.planner import plan_assets, resolve_run_config


class TestResolveRunConfig:
    """Test run config resolution and asset inheritance."""

    def test_logo_bundle_resolves_output_path(self, tmp_path):
        config = Config()
        resolved = resolve_run_config(config, tmp_path, "python")

        assert resolved.bundle == "logo"
        assert resolved.output_path == tmp_path / "logo.png"
        assert resolved.assets["logo"].style == "minimalist"

    def test_asset_overrides_inherit_from_globals(self, tmp_path):
        config = Config(
            style="global-style",
            assets={
                "icon": {
                    "style": "icon-style",
                    "model": "icon-model",
                }
            },
        )

        resolved = resolve_run_config(config, tmp_path, "python")

        assert resolved.assets["icon"].style == "icon-style"
        assert resolved.assets["icon"].model == "icon-model"
        assert resolved.assets["icon"].additional_instructions == ""
        assert resolved.assets["icon"].visual_metaphor

    def test_cli_overrides_win(self, tmp_path):
        config = Config(style="global-style", model="global-model", targets=["web-seo"])
        resolved = resolve_run_config(
            config,
            tmp_path,
            "python",
            cli_overrides={
                "style": "cli-style",
                "model": "cli-model",
                "bundle": "core-brand",
                "targets": ["google-play"],
            },
        )

        assert resolved.bundle == "core-brand"
        assert resolved.targets == ("google-play",)
        assert resolved.assets["logo"].style == "cli-style"
        assert resolved.assets["icon"].model == "cli-model"

    def test_core_brand_disables_repo_name_only_for_small_assets(self, tmp_path):
        config = Config(include_repo_name=True)
        resolved = resolve_run_config(
            config,
            tmp_path,
            "python",
            cli_overrides={"bundle": "core-brand"},
        )

        assert resolved.assets["logo"].include_repo_name is True
        assert resolved.assets["icon"].include_repo_name is False
        assert resolved.assets["favicon"].include_repo_name is False


class TestPlanAssets:
    """Test bundle output planning."""

    def test_logo_bundle_plans_single_output(self, tmp_path):
        run_config = resolve_run_config(Config(), tmp_path, "python")
        plan = plan_assets(run_config)

        assert plan.bundle == "logo"
        assert len(plan.items) == 1
        assert plan.items[0].output_path == tmp_path / "logo.png"

    def test_core_brand_plans_expected_outputs(self, tmp_path):
        run_config = resolve_run_config(
            Config(bundle="core-brand"),
            tmp_path,
            "python",
            cli_overrides={"bundle": "core-brand"},
        )
        plan = plan_assets(run_config)

        paths = {item.output_path.relative_to(run_config.assets_dir) for item in plan.items[:-1]}
        assert plan.bundle == "core-brand"
        assert "logo/logo-1024.png" in {str(path) for path in paths}
        assert "icon/icon-512.png" in {str(path) for path in paths}
        assert "favicon/favicon.ico" in {str(path) for path in paths}
        assert "social/social-card-1200x630.png" in {str(path) for path in paths}
        source_keys = {item.key: item.source_key for item in plan.items}
        assert source_keys["logo"] == "logo-mark"
        assert source_keys["icon"] == "logo-mark"
        assert source_keys["social-card"] == "logo-mark"
        strategies = {item.key: item.strategy for item in plan.items}
        assert strategies["icon"] == "generated_from_logo_reference"
        assert strategies["favicon-16"] == "resized_from_icon"
        assert strategies["social-card"] == "generated_from_logo_reference"

    def test_disabled_assets_are_skipped(self, tmp_path):
        config = Config(
            bundle="core-brand",
            assets={"social_card": {"enabled": False}},
        )
        run_config = resolve_run_config(
            config,
            tmp_path,
            "python",
            cli_overrides={"bundle": "core-brand"},
        )
        plan = plan_assets(run_config)

        assert all(item.kind != "social-card" for item in plan.items)

    def test_targeted_core_brand_uses_platform_layout(self, tmp_path):
        run_config = resolve_run_config(
            Config(bundle="core-brand", targets=["web-seo", "google-play", "apple-store"]),
            tmp_path,
            "python",
            cli_overrides={"bundle": "core-brand"},
        )

        plan = plan_assets(run_config)
        paths = {str(item.output_path.relative_to(run_config.assets_dir)) for item in plan.items}
        strategies = {item.key: item.strategy for item in plan.items}

        assert "logo/logo-1024.png" in paths
        assert "icon/icon-1024.png" in paths
        assert "web-seo/og-image-1200x630.png" in paths
        assert "web-seo/site.webmanifest" in paths
        assert "google-play/feature-graphic-1024x500.png" in paths
        assert "apple-store/app-store-icon-1024.png" in paths
        assert strategies["web-seo-og-image"] == "generated_from_logo_reference"
        assert strategies["web-seo-android-chrome-512"] == "resized_from_icon"
        assert strategies["web-seo-site-webmanifest"] == "written_metadata"
