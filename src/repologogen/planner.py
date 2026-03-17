"""Planning and config resolution for repologogen asset bundles."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from repologogen.config import ASSET_NAMES, Config
from repologogen.detector import get_visual_metaphor

CORE_BRAND_ASSET_ORDER = ("logo", "icon", "favicon", "social_card")
ASSET_OVERRIDE_FIELDS = (
    "style",
    "visual_metaphor",
    "include_repo_name",
    "icon_colors",
    "additional_instructions",
    "model",
    "size",
    "prompt_template",
)


@dataclass(frozen=True)
class ResolvedAssetConfig:
    """Resolved effective config for a single asset type."""

    name: str
    enabled: bool
    style: str
    visual_metaphor: str
    include_repo_name: bool
    icon_colors: list[str] | str
    additional_instructions: str
    model: str
    size: str
    prompt_template: str | None


@dataclass(frozen=True)
class ResolvedRunConfig:
    """Resolved effective config for the full run."""

    project_path: Path
    project_name: str
    project_type: str
    bundle: str
    targets: tuple[str, ...]
    output_path: Path
    assets_dir: Path
    manifest_path: Path
    metadata_enabled: bool
    text_model: str
    key_color: str
    tolerance: int
    compress: bool
    compress_quality: int
    trim: bool
    trim_margin: int
    refine_prompt: bool
    sources: tuple[str, ...]
    assets: dict[str, ResolvedAssetConfig]


@dataclass(frozen=True)
class AssetPlanItem:
    """Single output artifact within a bundle plan."""

    key: str
    kind: str
    output_path: Path
    target: str
    strategy: str
    width: int | None = None
    height: int | None = None
    aspect_ratio: str | None = None
    source_key: str | None = None


@dataclass(frozen=True)
class AssetPlan:
    """Resolved output plan for a run."""

    bundle: str
    assets_dir: Path
    manifest_path: Path
    items: tuple[AssetPlanItem, ...]


def _resolve_visual_metaphor(value: str | None, project_type: str) -> str:
    if value == "none":
        return "Abstract geometric shape"
    return value or get_visual_metaphor(project_type)


def _resolve_path(path_value: str, project_path: Path, project_name: str) -> Path:
    rendered = path_value.replace("{PROJECT_NAME}", project_name).replace(
        "{project_name}", project_name
    )
    path = Path(rendered)
    return path if path.is_absolute() else project_path / path


def _resolve_asset_config(
    name: str,
    config: Config,
    project_type: str,
    cli_overrides: dict[str, Any],
    bundle: str,
) -> ResolvedAssetConfig:
    overrides = dict((config.assets or {}).get(name, {}))

    enabled = bool(overrides.get("enabled", True))

    style = str(cli_overrides.get("style") or overrides.get("style") or config.style)
    visual_metaphor_value = (
        cli_overrides.get("visual_metaphor")
        or overrides.get("visual_metaphor")
        or config.visual_metaphor
    )
    visual_metaphor = _resolve_visual_metaphor(
        visual_metaphor_value,
        project_type,
    )
    include_repo_name = bool(overrides.get("include_repo_name", config.include_repo_name))

    # Small assets in the brand bundle should always use a text-free symbol.
    if bundle == "core-brand" and name in {"icon", "favicon"}:
        include_repo_name = False

    return ResolvedAssetConfig(
        name=name,
        enabled=enabled,
        style=style,
        visual_metaphor=visual_metaphor,
        include_repo_name=include_repo_name,
        icon_colors=overrides.get("icon_colors", config.icon_colors),
        additional_instructions=str(
            overrides.get("additional_instructions", config.additional_instructions)
        ),
        model=str(cli_overrides.get("model") or overrides.get("model") or config.model),
        size=str(overrides.get("size") or config.size),
        prompt_template=overrides.get("prompt_template", config.prompt_template),
    )


def resolve_run_config(
    config: Config,
    project_path: Path,
    project_type: str,
    *,
    project_name_override: str | None = None,
    cli_overrides: dict[str, Any] | None = None,
) -> ResolvedRunConfig:
    """Resolve merged config, per-asset inheritance, and CLI overrides."""
    cli = cli_overrides or {}
    project_name = project_name_override or project_path.resolve().name
    bundle = str(cli.get("bundle") or config.bundle)
    raw_targets = cli.get("targets")
    targets = tuple(raw_targets if raw_targets is not None else config.targets)

    output_path = _resolve_path(
        str(cli.get("output_path") or config.output_path),
        project_path,
        project_name,
    )
    assets_dir = _resolve_path(
        str(cli.get("assets_dir") or config.assets_dir),
        project_path,
        project_name,
    )
    manifest_path = _resolve_path(
        str(cli.get("manifest_path") or config.manifest_path), project_path, project_name
    )

    assets = {
        name: _resolve_asset_config(name, config, project_type, cli, bundle) for name in ASSET_NAMES
    }

    return ResolvedRunConfig(
        project_path=project_path,
        project_name=project_name,
        project_type=project_type,
        bundle=bundle,
        targets=targets,
        output_path=output_path,
        assets_dir=assets_dir,
        manifest_path=manifest_path,
        metadata_enabled=bool(config.metadata.enabled),
        text_model=config.text_model,
        key_color=config.key_color,
        tolerance=config.tolerance,
        compress=False if cli.get("no_compress") else config.compress,
        compress_quality=config.compress_quality,
        trim=False if cli.get("no_trim") else config.trim,
        trim_margin=config.trim_margin,
        refine_prompt=False if cli.get("no_refine") else config.refine_prompt,
        sources=tuple(config.meta.get("sources", ("bundled_defaults",))),
        assets=assets,
    )


def _plan_targeted_core_brand(run_config: ResolvedRunConfig) -> AssetPlan:
    items: list[AssetPlanItem] = []

    if run_config.assets["logo"].enabled:
        items.append(
            AssetPlanItem(
                "logo",
                "logo",
                run_config.assets_dir / "logo" / "logo-1024.png",
                target="shared",
                strategy="generated",
                width=1024,
                height=1024,
                aspect_ratio="1:1",
                source_key="logo-mark",
            )
        )

    if run_config.assets["icon"].enabled:
        items.append(
            AssetPlanItem(
                "icon",
                "icon",
                run_config.assets_dir / "icon" / "icon-1024.png",
                target="shared",
                strategy="generated_from_logo_reference",
                width=1024,
                height=1024,
                aspect_ratio="1:1",
                source_key="logo-mark",
            )
        )

    if "web-seo" in run_config.targets and run_config.assets["favicon"].enabled:
        items.extend(
            [
                AssetPlanItem(
                    "web-seo-favicon-16",
                    "favicon",
                    run_config.assets_dir / "web-seo" / "favicon" / "favicon-16.png",
                    target="web-seo",
                    strategy="resized_from_icon",
                    width=16,
                    height=16,
                    source_key="icon-mark",
                ),
                AssetPlanItem(
                    "web-seo-favicon-32",
                    "favicon",
                    run_config.assets_dir / "web-seo" / "favicon" / "favicon-32.png",
                    target="web-seo",
                    strategy="resized_from_icon",
                    width=32,
                    height=32,
                    source_key="icon-mark",
                ),
                AssetPlanItem(
                    "web-seo-favicon-48",
                    "favicon",
                    run_config.assets_dir / "web-seo" / "favicon" / "favicon-48.png",
                    target="web-seo",
                    strategy="resized_from_icon",
                    width=48,
                    height=48,
                    source_key="icon-mark",
                ),
                AssetPlanItem(
                    "web-seo-favicon-ico",
                    "favicon",
                    run_config.assets_dir / "web-seo" / "favicon" / "favicon.ico",
                    target="web-seo",
                    strategy="resized_from_icon",
                    source_key="icon-mark",
                ),
            ]
        )

    if "web-seo" in run_config.targets and run_config.assets["icon"].enabled:
        items.extend(
            [
                AssetPlanItem(
                    "web-seo-apple-touch-icon",
                    "app-icon",
                    run_config.assets_dir / "web-seo" / "apple-touch-icon.png",
                    target="web-seo",
                    strategy="resized_from_icon",
                    width=180,
                    height=180,
                    source_key="icon-mark",
                ),
                AssetPlanItem(
                    "web-seo-android-chrome-192",
                    "app-icon",
                    run_config.assets_dir / "web-seo" / "android-chrome-192.png",
                    target="web-seo",
                    strategy="resized_from_icon",
                    width=192,
                    height=192,
                    source_key="icon-mark",
                ),
                AssetPlanItem(
                    "web-seo-android-chrome-512",
                    "app-icon",
                    run_config.assets_dir / "web-seo" / "android-chrome-512.png",
                    target="web-seo",
                    strategy="resized_from_icon",
                    width=512,
                    height=512,
                    source_key="icon-mark",
                ),
            ]
        )

    if "web-seo" in run_config.targets and run_config.assets["social_card"].enabled:
        items.append(
            AssetPlanItem(
                "web-seo-og-image",
                "social-card",
                run_config.assets_dir / "web-seo" / "og-image-1200x630.png",
                target="web-seo",
                strategy="generated_from_logo_reference",
                width=1200,
                height=630,
                aspect_ratio="16:9",
                source_key="logo-mark",
            )
        )

    if "web-seo" in run_config.targets and run_config.assets["icon"].enabled:
        items.append(
            AssetPlanItem(
                "web-seo-site-webmanifest",
                "metadata",
                run_config.assets_dir / "web-seo" / "site.webmanifest",
                target="web-seo",
                strategy="written_metadata",
            )
        )

    if "google-play" in run_config.targets and run_config.assets["icon"].enabled:
        items.append(
            AssetPlanItem(
                "google-play-icon",
                "app-icon",
                run_config.assets_dir / "google-play" / "google-play-icon-512.png",
                target="google-play",
                strategy="resized_from_icon",
                width=512,
                height=512,
                source_key="icon-mark",
            )
        )

    if "google-play" in run_config.targets and run_config.assets["social_card"].enabled:
        items.append(
            AssetPlanItem(
                "google-play-feature-graphic",
                "feature-graphic",
                run_config.assets_dir / "google-play" / "feature-graphic-1024x500.png",
                target="google-play",
                strategy="generated_from_logo_reference",
                width=1024,
                height=500,
                aspect_ratio="16:9",
                source_key="logo-mark",
            )
        )

    if "apple-store" in run_config.targets and run_config.assets["icon"].enabled:
        items.append(
            AssetPlanItem(
                "apple-store-app-store-icon",
                "app-icon",
                run_config.assets_dir / "apple-store" / "app-store-icon-1024.png",
                target="apple-store",
                strategy="resized_from_icon",
                width=1024,
                height=1024,
                source_key="icon-mark",
            )
        )

    items.append(
        AssetPlanItem(
            "manifest",
            "manifest",
            run_config.manifest_path,
            target="shared",
            strategy="written_metadata",
        )
    )

    return AssetPlan(
        bundle="core-brand",
        assets_dir=run_config.assets_dir,
        manifest_path=run_config.manifest_path,
        items=tuple(items),
    )


def plan_assets(run_config: ResolvedRunConfig) -> AssetPlan:
    """Create the resolved output plan for the selected bundle."""
    if run_config.bundle == "logo":
        return AssetPlan(
            bundle="logo",
            assets_dir=run_config.output_path.parent,
            manifest_path=run_config.output_path.parent / "manifest.json",
            items=(
                AssetPlanItem(
                    "logo",
                    "logo",
                    run_config.output_path,
                    target="shared",
                    strategy="generated",
                    aspect_ratio="1:1",
                ),
            ),
        )
    return _plan_targeted_core_brand(run_config)
