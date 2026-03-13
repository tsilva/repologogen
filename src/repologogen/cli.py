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

from repologogen.config import ConfigValidationError, expand_path, get_api_key, load_merged_config
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
    compose_social_card,
    compress_png,
    export_favicon_set,
    get_image_info,
    resize_png,
    trim_transparent,
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
) -> str:
    return build_prompt(
        project_name=project_name,
        style=asset_config.style,
        icon_colors=asset_config.icon_colors,
        key_color=key_color,
        visual_metaphor=asset_config.visual_metaphor,
        include_repo_name=asset_config.include_repo_name,
        additional_instructions=asset_config.additional_instructions,
        prompt_template=asset_config.prompt_template,
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
) -> str:
    if not should_refine:
        return prompt

    api_key = get_api_key(project_path)
    if not api_key:
        return prompt

    return refine_prompt(prompt, target_model, api_key, text_model=text_model)


def _print_asset_settings(run_config: Any, plan: AssetPlan) -> None:
    table = Table(title="Resolved Asset Settings")
    table.add_column("Asset")
    table.add_column("Enabled")
    table.add_column("Model")
    table.add_column("Style")
    table.add_column("Output")

    seen_assets = set()
    for item in plan.items:
        asset_name = item.key.split("-")[0]
        if asset_name in {"app", "manifest"}:
            continue
        if asset_name == "social":
            asset_name = "social_card"
        if asset_name in seen_assets or asset_name not in run_config.assets:
            continue
        asset = run_config.assets[asset_name]
        asset_prefix = asset_name.replace("_card", "")
        output_path = next(
            entry.output_path for entry in plan.items if entry.key.startswith(asset_prefix)
        )
        table.add_row(
            asset_name,
            "yes" if asset.enabled else "no",
            asset.model,
            asset.style,
            str(output_path),
        )
        seen_assets.add(asset_name)

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
) -> dict[str, Any]:
    chromakey_result = chromakey_to_transparent(
        image_path,
        image_path,
        key_color=run_config.key_color,
        tolerance=run_config.tolerance,
    )

    if run_config.trim:
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
            "path": str(item.output_path.relative_to(root)),
        }
        if item.width and item.height:
            entry["size"] = [item.width, item.height]
        assets.append(entry)

    return {
        "project_name": run_config.project_name,
        "project_type": run_config.project_type,
        "bundle": run_config.bundle,
        "sources": list(run_config.sources),
        "metadata": metadata,
        "assets": assets,
    }


def _generate_core_brand(
    generator: ImageGenerator,
    run_config: Any,
    plan: AssetPlan,
    template_vars: dict[str, str] | None,
    project_description: str,
    metadata: dict[str, Any],
) -> int:
    master_config = run_config.assets["icon"]
    raw_prompt = _build_asset_prompt(
        master_config,
        project_name=run_config.project_name,
        project_description=project_description,
        key_color=run_config.key_color,
        template_vars=template_vars,
    )
    prompt = _maybe_refine_prompt(
        raw_prompt,
        should_refine=run_config.refine_prompt,
        target_model=master_config.model,
        project_path=run_config.project_path,
        text_model=run_config.text_model,
    )

    console.print("\n[bold blue]Master Prompt:[/bold blue]")
    console.print(prompt)

    run_config.assets_dir.mkdir(parents=True, exist_ok=True)

    with (
        tempfile.TemporaryDirectory(prefix="repologogen-") as temp_dir,
        Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress,
    ):
        temp_root = Path(temp_dir)
        master_path = temp_root / "master.png"

        task = progress.add_task("[green]Generating master brand mark...", total=None)
        generator.generate(
            prompt=prompt,
            model=master_config.model,
            output_path=master_path,
            size=master_config.size,
        )
        progress.update(task, completed=True)

        task = progress.add_task("[green]Applying transparency...", total=None)
        _apply_post_processing(run_config, master_path)
        progress.update(task, completed=True)

        for item in plan.items:
            if item.kind == "logo":
                resize_png(master_path, item.output_path, (item.width or 1024, item.height or 1024))
            elif item.kind in {"icon", "app-icon"}:
                resize_png(master_path, item.output_path, (item.width or 512, item.height or 512))
            elif item.kind == "favicon":
                if item.output_path.suffix == ".ico":
                    continue
                resize_png(master_path, item.output_path, (item.width or 32, item.height or 32))

        favicon_dir = run_config.assets_dir / "favicon"
        if run_config.assets["favicon"].enabled:
            export_favicon_set(master_path, favicon_dir)

        if run_config.assets["social_card"].enabled:
            social_path = run_config.assets_dir / "social" / "social-card-1200x630.png"
            compose_social_card(
                master_path,
                social_path,
                project_name=run_config.project_name,
                title=metadata.get("social_title", run_config.project_name),
                description=metadata.get(
                    "social_description",
                    project_description or run_config.project_name,
                ),
                accent_color=(
                    master_config.icon_colors[0]
                    if isinstance(master_config.icon_colors, list) and master_config.icon_colors
                    else "#58a6ff"
                ),
            )

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
