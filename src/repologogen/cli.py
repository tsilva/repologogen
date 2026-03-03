#!/usr/bin/env python3
"""CLI entry point for repologogen."""

import argparse
import os
import sys
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from repologogen.config import load_merged_config, expand_path
from repologogen.detector import detect_project, get_visual_metaphor
from repologogen.generator import ImageGenerator, ImageGeneratorError, build_prompt
from repologogen.processor import (
    chromakey_to_transparent,
    trim_transparent,
    compress_png,
    get_image_info,
)

console = Console()


def resolve_output_path(output_path: str, project_name: str, cwd: Path) -> Path:
    """Resolve output path to absolute path with project name substitution."""
    resolved = output_path.replace("{PROJECT_NAME}", project_name)
    return Path(resolved) if os.path.isabs(resolved) else cwd / resolved


def run_generation(
    project_path: Path,
    config_path: Path | None = None,
    verbose: bool = False,
    dry_run: bool = False,
) -> int:
    """Run the logo generation workflow."""
    project_name = project_path.resolve().name

    if config_path:
        user_config, project_config = None, config_path
    else:
        user_config, project_config = (
            expand_path("~/.repologogen/config.json"),
            project_path / ".repologogen.json",
        )

    with console.status("[bold green]Loading configuration..."):
        config = load_merged_config(
            user_config_path=user_config, project_config_path=project_config
        )

    if verbose:
        console.print(
            f"[dim]Config sources: {', '.join(config.meta.get('sources', ['defaults']))}[/dim]"
        )

    project_info = detect_project(project_path)
    project_type = project_info["type"]

    if verbose:
        console.print(
            f"[dim]Detected project type: {project_type} ({project_info['confidence']})[/dim]"
        )

    if config.logo.visual_metaphor == "none":
        visual_metaphor = "Abstract geometric shape"
    elif config.logo.visual_metaphor:
        visual_metaphor = config.logo.visual_metaphor
    else:
        visual_metaphor = get_visual_metaphor(project_type)

    resolved_output = resolve_output_path(config.logo.output_path, project_name, project_path)

    if verbose:
        console.print(f"[dim]Output path: {resolved_output}[/dim]")

    prompt = build_prompt(
        project_name=project_name,
        style=config.logo.style,
        icon_colors=config.logo.icon_colors,
        key_color=config.logo.key_color,
        visual_metaphor=visual_metaphor,
        include_repo_name=config.logo.include_repo_name,
        additional_instructions=config.logo.additional_instructions,
        prompt_template=config.logo.prompt_template,
    )

    if verbose:
        console.print(f"[dim]Prompt preview: {prompt[:100]}...[/dim]")

    if dry_run:
        console.print("\n[bold cyan]Dry Run Summary:[/bold cyan]")
        console.print(f"  Project: [green]{project_name}[/green]")
        console.print(f"  Type: [green]{project_type}[/green]")
        console.print(f"  Style: [green]{config.logo.style}[/green]")
        console.print(f"  Output: [green]{resolved_output}[/green]")
        console.print(f"  Model: [green]{config.logo.model}[/green]")
        console.print(f"\n[dim]Prompt:[/dim]")
        console.print(prompt)
        return 0

    try:
        generator = ImageGenerator(project_path=project_path)
    except ImageGeneratorError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        console.print(
            "[dim]Set OPENROUTER_API_KEY in environment, .env file, or ~/.repologogen/config.json[/dim]"
        )
        return 1

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("[green]Generating image...", total=None)
            generator.generate(
                prompt=prompt,
                model=config.logo.model,
                output_path=resolved_output,
                size=config.logo.size,
            )
            progress.update(task, completed=True)

            task = progress.add_task("[green]Applying transparency...", total=None)
            chromakey_result = chromakey_to_transparent(
                resolved_output,
                resolved_output,
                key_color=config.logo.key_color,
                tolerance=config.logo.tolerance,
            )
            progress.update(task, completed=True)

            if config.logo.trim:
                task = progress.add_task("[green]Trimming transparent padding...", total=None)
                trim_transparent(resolved_output, resolved_output, margin=config.logo.trim_margin)
                progress.update(task, completed=True)

            if config.logo.compress:
                task = progress.add_task("[green]Compressing image...", total=None)
                compress_png(resolved_output, resolved_output, quality=config.logo.compress_quality)
                progress.update(task, completed=True)

        info = get_image_info(resolved_output)

        console.print(f"\n[bold green]Logo generated successfully![/bold green]")
        console.print(f"  Output: [cyan]{resolved_output}[/cyan]")
        console.print(f"  Size: [cyan]{info['size'][0]}x{info['size'][1]}[/cyan]")
        console.print(f"  File size: [cyan]{info['file_size']:,} bytes[/cyan]")
        console.print(f"  Transparency: [cyan]{info['transparency_percent']}%[/cyan]")

        if verbose:
            console.print(
                f"\n[dim]Chromakey: {chromakey_result['transparent_pixels']:,} pixels made transparent[/dim]"
            )

        return 0

    except ImageGeneratorError as e:
        console.print(f"\n[bold red]Generation failed:[/bold red] {e}")
        return 1
    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        if verbose:
            console.print_exception()
        return 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="repologogen", description="Generate professional logos with transparent backgrounds"
    )

    parser.add_argument(
        "path", nargs="?", default=".", help="Project directory (default: current directory)"
    )
    parser.add_argument("-c", "--config", help="Path to custom configuration file")
    parser.add_argument("-o", "--output", help="Override output path")
    parser.add_argument("-s", "--style", help="Override style (e.g., minimalist, pixel-art)")
    parser.add_argument("-m", "--model", help="Override image generation model")
    parser.add_argument("-n", "--name", help="Override project name")
    parser.add_argument(
        "--no-trim", action="store_true", help="Disable transparent padding trimming"
    )
    parser.add_argument("--no-compress", action="store_true", help="Disable PNG compression")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be generated without executing"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")

    args = parser.parse_args()

    project_path = Path(args.path).resolve()

    if not project_path.is_dir():
        console.print(f"[bold red]Error:[/bold red] Not a directory: {project_path}")
        return 1

    return run_generation(
        project_path=project_path,
        config_path=Path(args.config) if args.config else None,
        verbose=args.verbose,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    sys.exit(main())
