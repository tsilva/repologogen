#!/usr/bin/env python3
"""CLI entry point for repologogen."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, cast

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from repologogen.config import (
    TARGET_NAMES,
    ConfigValidationError,
    expand_path,
    get_api_key,
    load_merged_config,
)
from repologogen.detector import detect_project, find_readme
from repologogen.generator import (
    ImageGenerator,
    ImageGeneratorError,
    build_prompt,
    digest_readme,
    extract_repo_metadata,
    refine_prompt,
)
from repologogen.planner import (
    AssetPlan,
    ResolvedAssetConfig,
    plan_assets,
    resolve_run_config,
)
from repologogen.processor import (
    chromakey_to_transparent,
    compose_marketing_graphic,
    compress_png,
    export_favicon_set,
    get_image_info,
    resize_cover_png,
    resize_png,
    trim_transparent,
    write_site_webmanifest,
)

console = Console()


def _parse_template_vars(values: list[str]) -> dict[str, str]:
    template_vars: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"Invalid --var format: {value}. Use KEY=VALUE")
        key, parsed_value = value.split("=", 1)
        template_vars[key] = parsed_value
    return template_vars


def _load_config(project_path: Path, config_path: Path | None) -> Any:
    if config_path:
        return load_merged_config(
            user_config_path=expand_path("~/.repologogen/config.yaml"),
            project_config_path=config_path,
            require_project_config=True,
            project_root=project_path,
        )

    return load_merged_config(project_root=project_path)


def _get_project_description(
    project_path: Path,
    readme_path: Path | None,
    text_model: str,
    template_vars: dict[str, str] | None,
) -> str:
    if not readme_path or (template_vars and "PROJECT_DESCRIPTION" in template_vars):
        return ""

    try:
        readme_content = readme_path.read_text(encoding="utf-8")
    except OSError:
        return ""

    api_key = get_api_key(project_path)
    if not api_key:
        return ""

    return digest_readme(readme_content, api_key, text_model=text_model)


def _build_asset_prompt(
    asset_config: ResolvedAssetConfig,
    *,
    project_name: str,
    project_description: str,
    key_color: str,
    template_vars: dict[str, str] | None,
    purpose: str = "default",
    metadata: dict[str, Any] | None = None,
) -> str:
    additional_instructions = asset_config.additional_instructions
    prompt_template = asset_config.prompt_template
    include_repo_name = asset_config.include_repo_name
    if purpose == "icon-mark":
        icon_focus = (
            "Use the provided reference logo as the brand source. "
            "Create a single bold symbol extracted from the main brand idea. "
            "No text, letters, words, banners, mascots with tiny details, "
            "or multiple competing elements. "
            "Prioritize one dominant silhouette that remains legible at 16x16 and 32x32. "
            "Use simple shapes, high contrast, and minimal internal detail."
        )
        additional_instructions = (
            f"{additional_instructions}\n{icon_focus}".strip()
            if additional_instructions
            else icon_focus
        )
    elif purpose == "web-seo-social":
        prompt_template = (
            "A {STYLE} marketing graphic for {PROJECT_NAME}.{PROJECT_DESCRIPTION} "
            "{VISUAL_METAPHOR}.\n"
            "Brand palette from: {ICON_COLORS}.\n"
            "{TEXT_INSTRUCTIONS} Full-bleed composition sized for social sharing. "
            "No chromakey background, no transparency requirement."
        )
        include_repo_name = True
        social_title = (metadata or {}).get("social_title", project_name)
        social_description = (metadata or {}).get(
            "social_description",
            project_description or project_name,
        )
        social_instructions = (
            f'Use "{social_title}" as the primary headline. '
            f'Include this supporting line or close paraphrase: "{social_description}". '
            "Make the typography prominent and readable in a link preview. "
            "Keep all critical text and the focal brand elements inside a centered safe area "
            "so the image can be cropped slightly to the final export size."
        )
        additional_instructions = (
            f"{additional_instructions}\n{social_instructions}".strip()
            if additional_instructions
            else social_instructions
        )
    elif purpose == "google-play-feature":
        prompt_template = (
            "A {STYLE} Google Play feature graphic for {PROJECT_NAME}.{PROJECT_DESCRIPTION} "
            "{VISUAL_METAPHOR}.\n"
            "Brand palette from: {ICON_COLORS}.\n"
            "{TEXT_INSTRUCTIONS} Wide promotional artwork that feels native to an app store. "
            "No chromakey background, no transparency requirement."
        )
        include_repo_name = True
        social_title = (metadata or {}).get("social_title", project_name)
        feature_instructions = (
            f'Use "{social_title}" as the main marketing title. '
            "Preserve the reference logo's visual identity while expanding it into a wide, "
            "store-ready promotional composition. Keep the title and main artwork safely "
            "inside the center region so the export can be cropped to the final store size."
        )
        additional_instructions = (
            f"{additional_instructions}\n{feature_instructions}".strip()
            if additional_instructions
            else feature_instructions
        )

    return build_prompt(
        project_name=project_name,
        style=asset_config.style,
        icon_colors=asset_config.icon_colors,
        key_color=key_color,
        visual_metaphor=asset_config.visual_metaphor,
        include_repo_name=include_repo_name,
        additional_instructions=additional_instructions,
        prompt_template=prompt_template,
        template_vars=template_vars,
        project_description=project_description,
    )


def _maybe_refine_prompt(
    prompt: str,
    *,
    should_refine: bool,
    target_model: str,
    project_path: Path,
    text_model: str,
    reference_based: bool = False,
) -> str:
    if not should_refine or reference_based:
        return prompt

    api_key = get_api_key(project_path)
    if not api_key:
        return prompt

    return refine_prompt(prompt, target_model, api_key, text_model=text_model)


def _print_asset_settings(run_config: Any, plan: AssetPlan) -> None:
    table = Table(title="Resolved Asset Plan")
    table.add_column("Key")
    table.add_column("Target")
    table.add_column("Strategy")
    table.add_column("Output")

    del run_config
    for item in plan.items:
        table.add_row(item.key, item.target, item.strategy, str(item.output_path))

    console.print(table)


def _print_dry_run_summary(
    run_config: Any,
    plan: AssetPlan,
    project_description: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    console.print("\n[bold cyan]Dry Run Summary:[/bold cyan]")
    console.print(f"  Project: [green]{run_config.project_name}[/green]")
    console.print(f"  Type: [green]{run_config.project_type}[/green]")
    console.print(f"  Bundle: [green]{run_config.bundle}[/green]")
    console.print(f"  Config sources: [green]{', '.join(run_config.sources)}[/green]")
    if run_config.targets:
        console.print(f"  Targets: [green]{', '.join(run_config.targets)}[/green]")
    if run_config.bundle == "logo":
        console.print(f"  Output: [green]{run_config.output_path}[/green]")
    else:
        console.print(f"  Assets dir: [green]{run_config.assets_dir}[/green]")
        console.print(f"  Manifest: [green]{run_config.manifest_path}[/green]")
    if project_description:
        console.print(f"  Description: [green]{project_description}[/green]")
    if metadata:
        console.print(f"  Social title: [green]{metadata['social_title']}[/green]")
    _print_asset_settings(run_config, plan)


def _collect_metadata(
    run_config: Any,
    readme_path: Path | None,
    project_description: str,
) -> dict[str, Any]:
    if not run_config.metadata_enabled:
        return {}

    readme_content = ""
    if readme_path:
        try:
            readme_content = readme_path.read_text(encoding="utf-8")
        except OSError:
            readme_content = ""

    api_key = get_api_key(run_config.project_path)
    if not api_key:
        return extract_repo_metadata(
            "",
            "",
            run_config.project_name,
            run_config.project_type,
            project_description=project_description,
            text_model=run_config.text_model,
        )

    return extract_repo_metadata(
        readme_content,
        api_key,
        run_config.project_name,
        run_config.project_type,
        project_description=project_description,
        text_model=run_config.text_model,
    )


def _apply_post_processing(
    run_config: Any,
    image_path: Path,
    *,
    remove_background: bool = True,
) -> dict[str, Any]:
    chromakey_result: dict[str, Any] = {"processed": False}
    if remove_background:
        chromakey_result = chromakey_to_transparent(
            image_path,
            image_path,
            key_color=run_config.key_color,
            tolerance=run_config.tolerance,
        )

    if remove_background and run_config.trim:
        trim_transparent(image_path, image_path, margin=run_config.trim_margin)

    if run_config.compress:
        compress_png(image_path, image_path, quality=run_config.compress_quality)

    return chromakey_result


def _generate_single_logo(
    generator: ImageGenerator,
    run_config: Any,
    template_vars: dict[str, str] | None,
    project_description: str,
    *,
    verbose: bool,
) -> int:
    asset_config = run_config.assets["logo"]
    raw_prompt = _build_asset_prompt(
        asset_config,
        project_name=run_config.project_name,
        project_description=project_description,
        key_color=run_config.key_color,
        template_vars=template_vars,
    )
    prompt = _maybe_refine_prompt(
        raw_prompt,
        should_refine=run_config.refine_prompt,
        target_model=asset_config.model,
        project_path=run_config.project_path,
        text_model=run_config.text_model,
    )

    console.print("\n[bold blue]Prompt:[/bold blue]")
    console.print(prompt)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[green]Generating image...", total=None)
        generator.generate(
            prompt=prompt,
            model=asset_config.model,
            output_path=run_config.output_path,
            size=asset_config.size,
        )
        progress.update(task, completed=True)

        task = progress.add_task("[green]Applying transparency...", total=None)
        chromakey_result = _apply_post_processing(run_config, run_config.output_path)
        progress.update(task, completed=True)

    info = get_image_info(run_config.output_path)
    image_size = cast(tuple[int, int], info["size"])
    file_size = cast(int, info["file_size"])
    transparency_percent = cast(float, info["transparency_percent"])

    console.print("\n[bold green]Logo generated successfully![/bold green]")
    console.print(f"  Output: [cyan]{run_config.output_path}[/cyan]")
    console.print(f"  Size: [cyan]{image_size[0]}x{image_size[1]}[/cyan]")
    console.print(f"  File size: [cyan]{file_size:,} bytes[/cyan]")
    console.print(f"  Transparency: [cyan]{transparency_percent}%[/cyan]")
    if verbose:
        transparent_pixels = cast(int, chromakey_result["transparent_pixels"])
        console.print(f"\n[dim]Chromakey: {transparent_pixels:,} pixels made transparent[/dim]")

    return 0


def _build_manifest(
    run_config: Any,
    plan: AssetPlan,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    assets: list[dict[str, Any]] = []
    root = run_config.assets_dir
    for item in plan.items:
        if item.kind == "manifest":
            continue
        entry: dict[str, Any] = {
            "key": item.key,
            "kind": item.kind,
            "target": item.target,
            "strategy": item.strategy,
            "path": str(item.output_path.relative_to(root)),
        }
        if item.width and item.height:
            entry["size"] = [item.width, item.height]
        assets.append(entry)

    return {
        "project_name": run_config.project_name,
        "project_type": run_config.project_type,
        "bundle": run_config.bundle,
        "targets": list(run_config.targets),
        "sources": list(run_config.sources),
        "metadata": metadata,
        "assets": assets,
    }


def _purpose_for_plan_item(item: Any) -> str:
    if item.kind == "icon":
        return "icon-mark"
    if item.kind == "feature-graphic":
        return "google-play-feature"
    if item.kind == "social-card":
        return "web-seo-social"
    return "logo-mark"


def _generate_asset(
    generator: ImageGenerator,
    run_config: Any,
    *,
    asset_config: ResolvedAssetConfig,
    output_path: Path,
    template_vars: dict[str, str] | None,
    project_description: str,
    purpose: str,
    progress: Progress,
    task_label: str,
    metadata: dict[str, Any] | None = None,
    reference_images: list[Path] | None = None,
    aspect_ratio: str = "1:1",
    remove_background: bool = True,
) -> None:
    raw_prompt = _build_asset_prompt(
        asset_config,
        project_name=run_config.project_name,
        project_description=project_description,
        key_color=run_config.key_color,
        template_vars=template_vars,
        purpose=purpose,
        metadata=metadata,
    )
    prompt = _maybe_refine_prompt(
        raw_prompt,
        should_refine=run_config.refine_prompt,
        target_model=asset_config.model,
        project_path=run_config.project_path,
        text_model=run_config.text_model,
        reference_based=bool(reference_images),
    )

    console.print(f"\n[bold blue]{task_label} Prompt:[/bold blue]")
    console.print(prompt)

    task = progress.add_task(f"[green]Generating {task_label.lower()}...", total=None)
    generator.generate(
        prompt=prompt,
        model=asset_config.model,
        output_path=output_path,
        size=asset_config.size,
        aspect_ratio=aspect_ratio,
        reference_images=reference_images,
    )
    progress.update(task, completed=True)

    task_label_text = (
        f"[green]Applying transparency to {task_label.lower()}..."
        if remove_background
        else f"[green]Finalizing {task_label.lower()}..."
    )
    task = progress.add_task(task_label_text, total=None)
    _apply_post_processing(run_config, output_path, remove_background=remove_background)
    progress.update(task, completed=True)


def _write_web_target_manifest(
    run_config: Any,
    plan: AssetPlan,
    metadata: dict[str, Any],
    project_description: str,
) -> None:
    webmanifest_item = next(
        (item for item in plan.items if item.key == "web-seo-site-webmanifest"),
        None,
    )
    if webmanifest_item is None:
        return

    icons: list[dict[str, str]] = []
    for item in plan.items:
        if item.target != "web-seo":
            continue
        if item.key == "web-seo-android-chrome-192":
            icons.append(
                {"src": "android-chrome-192.png", "sizes": "192x192", "type": "image/png"}
            )
        elif item.key == "web-seo-android-chrome-512":
            icons.append(
                {"src": "android-chrome-512.png", "sizes": "512x512", "type": "image/png"}
            )

    write_site_webmanifest(
        webmanifest_item.output_path,
        name=str(metadata.get("title") or run_config.project_name),
        description=str(
            metadata.get("short_description") or project_description or run_config.project_name
        ),
        icons=icons,
    )


def _compose_marketing_fallback(
    run_config: Any,
    item: Any,
    metadata: dict[str, Any],
    *,
    logo_master_path: Path,
    icon_master_path: Path,
) -> None:
    source_path = icon_master_path if icon_master_path.exists() else logo_master_path
    title = str(metadata.get("social_title") or run_config.project_name)
    description = str(
        metadata.get("social_description") or metadata.get("short_description") or ""
    )
    compose_marketing_graphic(
        source_path,
        item.output_path,
        project_name=run_config.project_name,
        title=title,
        description=description,
        size=(item.width or 1200, item.height or 630),
        accent_color=(
            run_config.assets["icon"].icon_colors[0]
            if (
                isinstance(run_config.assets["icon"].icon_colors, list)
                and run_config.assets["icon"].icon_colors
            )
            else "#58a6ff"
        ),
    )
    if run_config.compress:
        compress_png(item.output_path, item.output_path, quality=run_config.compress_quality)


def _generate_core_brand(
    generator: ImageGenerator,
    run_config: Any,
    plan: AssetPlan,
    template_vars: dict[str, str] | None,
    project_description: str,
    metadata: dict[str, Any],
) -> int:
    run_config.assets_dir.mkdir(parents=True, exist_ok=True)
    requires_logo = any(
        item.source_key == "logo-mark" for item in plan.items if item.kind != "manifest"
    )
    if requires_logo and not run_config.assets["logo"].enabled:
        raise ImageGeneratorError(
            "Core brand generation requires the logo asset to remain enabled."
        )

    with (
        tempfile.TemporaryDirectory(prefix="repologogen-") as temp_dir,
        Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress,
    ):
        temp_root = Path(temp_dir)
        logo_master_path = temp_root / "logo-master.png"
        icon_master_path = temp_root / "icon-master.png"
        logo_item = next((item for item in plan.items if item.kind == "logo"), None)
        icon_item = next((item for item in plan.items if item.kind == "icon"), None)

        if logo_item:
            _generate_asset(
                generator,
                run_config,
                asset_config=run_config.assets["logo"],
                output_path=logo_master_path,
                template_vars=template_vars,
                project_description=project_description,
                purpose="logo-mark",
                progress=progress,
                task_label="Primary Logo",
            )
            resize_png(
                logo_master_path,
                logo_item.output_path,
                (logo_item.width or 1024, logo_item.height or 1024),
            )

        icon_source_required = any(
            item.source_key == "icon-mark"
            for item in plan.items
            if item.kind not in {"manifest", "metadata"}
        )
        if icon_source_required:
            _generate_asset(
                generator,
                run_config,
                asset_config=run_config.assets["icon"],
                output_path=icon_master_path,
                template_vars=template_vars,
                project_description=project_description,
                purpose="icon-mark",
                progress=progress,
                task_label="Icon Mark",
                reference_images=[logo_master_path],
            )
            if icon_item:
                resize_png(
                    icon_master_path,
                    icon_item.output_path,
                    (icon_item.width or 1024, icon_item.height or 1024),
                )

        favicon_dirs = {item.output_path.parent for item in plan.items if item.kind == "favicon"}
        for favicon_dir in favicon_dirs:
            export_favicon_set(icon_master_path, favicon_dir)

        for item in plan.items:
            if item.kind in {"manifest", "metadata", "logo", "icon", "favicon"}:
                continue
            if item.strategy == "resized_from_icon":
                resize_png(
                    icon_master_path,
                    item.output_path,
                    (item.width or 512, item.height or 512),
                )
            elif item.strategy == "generated_from_logo_reference":
                asset_name = (
                    "social_card"
                    if item.kind in {"social-card", "feature-graphic"}
                    else item.kind
                )
                try:
                    _generate_asset(
                        generator,
                        run_config,
                        asset_config=run_config.assets[asset_name],
                        output_path=item.output_path,
                        template_vars=template_vars,
                        project_description=project_description,
                        purpose=_purpose_for_plan_item(item),
                        progress=progress,
                        task_label=item.key.replace("-", " ").title(),
                        metadata=metadata,
                        reference_images=[logo_master_path],
                        aspect_ratio=item.aspect_ratio or "1:1",
                        remove_background=False,
                    )
                    if item.width and item.height:
                        resize_cover_png(
                            item.output_path,
                            item.output_path,
                            (item.width, item.height),
                        )
                except ImageGeneratorError as error:
                    if item.kind not in {"social-card", "feature-graphic"}:
                        raise
                    console.print(
                        "[yellow]Falling back to deterministic composition for "
                        f"{item.key}:[/yellow] {error}"
                    )
                    _compose_marketing_fallback(
                        run_config,
                        item,
                        metadata,
                        logo_master_path=logo_master_path,
                        icon_master_path=icon_master_path,
                    )

        if run_config.targets:
            _write_web_target_manifest(run_config, plan, metadata, project_description)

    manifest = _build_manifest(run_config, plan, metadata)
    run_config.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    run_config.manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    console.print("\n[bold green]Core brand pack generated successfully![/bold green]")
    console.print(f"  Assets dir: [cyan]{run_config.assets_dir}[/cyan]")
    console.print(f"  Manifest: [cyan]{run_config.manifest_path}[/cyan]")
    return 0


def run_generation(
    project_path: Path,
    config_path: Path | None = None,
    *,
    verbose: bool = False,
    dry_run: bool = False,
    template_vars: dict[str, str] | None = None,
    bundle: str | None = None,
    targets: list[str] | None = None,
    assets_dir: str | None = None,
    manifest_path: str | None = None,
    output_path: str | None = None,
    style: str | None = None,
    model: str | None = None,
    project_name_override: str | None = None,
    no_refine: bool = False,
    no_trim: bool = False,
    no_compress: bool = False,
) -> int:
    """Run the configured generation workflow."""
    try:
        with console.status("[bold green]Loading configuration..."):
            config = _load_config(project_path, config_path)
    except ConfigValidationError as error:
        console.print(f"[bold red]Configuration Error:[/bold red] {error}")
        if error.file_path:
            console.print(f"[dim]File: {error.file_path}[/dim]")
        return 1

    project_info = detect_project(project_path)
    project_type = cast(str, project_info["type"])

    if verbose:
        console.print(
            f"[dim]Detected project type: {project_type} ({project_info['confidence']})[/dim]"
        )

    cli_overrides = {
        "bundle": bundle,
        "targets": targets,
        "assets_dir": assets_dir,
        "manifest_path": manifest_path,
        "output_path": output_path,
        "style": style,
        "model": model,
        "no_refine": no_refine,
        "no_trim": no_trim,
        "no_compress": no_compress,
    }
    run_config = resolve_run_config(
        config,
        project_path,
        project_type,
        project_name_override=project_name_override,
        cli_overrides=cli_overrides,
    )

    if run_config.bundle != "logo" and output_path:
        console.print("[bold red]Error:[/bold red] --output can only be used with the logo bundle")
        return 1
    if run_config.bundle == "logo" and run_config.targets:
        console.print(
            "[bold red]Error:[/bold red] --target can only be used with the core-brand bundle"
        )
        return 1
    if run_config.bundle == "core-brand" and not run_config.targets:
        console.print(
            "[bold red]Error:[/bold red] core-brand now requires at least one --target "
            "(web-seo, google-play, apple-store)"
        )
        return 1

    plan = plan_assets(run_config)
    readme_path = find_readme(project_path)
    project_description = _get_project_description(
        project_path,
        readme_path,
        run_config.text_model,
        template_vars,
    )
    metadata = _collect_metadata(run_config, readme_path, project_description)

    if dry_run:
        _print_dry_run_summary(run_config, plan, project_description, metadata or None)
        return 0

    try:
        generator = ImageGenerator(project_path=project_path)
    except ImageGeneratorError as error:
        console.print(f"[bold red]Error:[/bold red] {error}")
        console.print(
            "[dim]Set OPENROUTER_API_KEY in environment or ~/.repologogen/config.yaml[/dim]"
        )
        return 1

    try:
        if run_config.bundle == "logo":
            return _generate_single_logo(
                generator,
                run_config,
                template_vars,
                project_description,
                verbose=verbose,
            )
        return _generate_core_brand(
            generator,
            run_config,
            plan,
            template_vars,
            project_description,
            metadata,
        )
    except ImageGeneratorError as error:
        console.print(f"\n[bold red]Generation failed:[/bold red] {error}")
        return 1
    except Exception as error:
        console.print(f"\n[bold red]Error:[/bold red] {error}")
        if verbose:
            console.print_exception()
        return 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="repologogen",
        description="Generate professional logos and core brand assets",
    )

    parser.add_argument(
        "path", nargs="?", default=".", help="Project directory (default: current directory)"
    )
    parser.add_argument("-c", "--config", help="Path to custom configuration file")
    parser.add_argument(
        "--bundle",
        choices=["logo", "core-brand"],
        help="Bundle to generate (default: logo)",
    )
    parser.add_argument(
        "--target",
        action="append",
        choices=list(TARGET_NAMES),
        help="Target platform asset pack (repeatable, core-brand only)",
    )
    parser.add_argument("-o", "--output", help="Override output path for logo bundle")
    parser.add_argument("--assets-dir", help="Override output directory for bundle assets")
    parser.add_argument("--manifest", help="Override manifest path for bundle assets")
    parser.add_argument("-s", "--style", help="Override style (e.g., minimalist, pixel-art)")
    parser.add_argument("-m", "--model", help="Override image generation model")
    parser.add_argument("-n", "--name", help="Override project name")
    parser.add_argument(
        "--no-trim", action="store_true", help="Disable transparent padding trimming"
    )
    parser.add_argument("--no-compress", action="store_true", help="Disable PNG compression")
    parser.add_argument("--no-refine", action="store_true", help="Disable LLM prompt refinement")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be generated without executing"
    )
    parser.add_argument(
        "--var",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Template variable for prompt (can be used multiple times)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")

    args = parser.parse_args()

    try:
        template_vars = _parse_template_vars(args.var)
    except ValueError as error:
        console.print(f"[bold red]Error:[/bold red] {error}")
        return 1

    project_path = Path(args.path).resolve()
    if not project_path.is_dir():
        console.print(f"[bold red]Error:[/bold red] Not a directory: {project_path}")
        return 1

    return run_generation(
        project_path=project_path,
        config_path=Path(args.config) if args.config else None,
        verbose=args.verbose,
        dry_run=args.dry_run,
        template_vars=template_vars,
        bundle=args.bundle,
        targets=args.target,
        assets_dir=args.assets_dir,
        manifest_path=args.manifest,
        output_path=args.output,
        style=args.style,
        model=args.model,
        project_name_override=args.name,
        no_refine=args.no_refine,
        no_trim=args.no_trim,
        no_compress=args.no_compress,
    )


if __name__ == "__main__":
    sys.exit(main())
