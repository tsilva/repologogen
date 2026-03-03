#!/usr/bin/env python3
"""CLI entry point for repologogen."""

import argparse
import os
import sys
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from repologogen.config import ConfigValidationError, expand_path, load_merged_config
from repologogen.detector import detect_project, find_readme, get_visual_metaphor
from repologogen.generator import (
    ImageGenerator,
    ImageGeneratorError,
    build_prompt,
    digest_readme,
    refine_prompt,
)
from repologogen.processor import (
    chromakey_to_transparent,
    compress_png,
    get_image_info,
    trim_transparent,
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
    template_vars: dict | None = None,
    no_refine: bool = False,
) -> int:
    """Run the logo generation workflow."""
    project_name = project_path.resolve().name

    try:
        with console.status("[bold green]Loading configuration..."):
            if config_path:
                # If custom config provided, use it as project config override
                config = load_merged_config(
                    project_config_path=config_path,
                    user_config_path=expand_path("~/.repologogen/config.yaml"),
                )
            else:
                # Use bundled defaults with user and project overrides
                config = load_merged_config(
                    project_config_path=project_path / ".config.yaml",
                    user_config_path=expand_path("~/.repologogen/config.yaml"),
                )

        if verbose:
            console.print(
                f"[dim]Config sources: {', '.join(config.meta.get('sources', ['defaults']))}[/dim]"
            )
    except ConfigValidationError as e:
        console.print(f"[bold red]Configuration Error:[/bold red] {e}")
        if e.file_path:
            console.print(f"[dim]File: {e.file_path}[/dim]")
        return 1

    project_info = detect_project(project_path)
    project_type = project_info["type"]

    if verbose:
        console.print(
            f"[dim]Detected project type: {project_type} ({project_info['confidence']})[/dim]"
        )

    # Read and digest README for project description
    project_description = ""
    readme_path = find_readme(project_path)
    if readme_path and not (template_vars and "PROJECT_DESCRIPTION" in template_vars):
        with console.status("[bold green]Reading project description..."):
            try:
                readme_content = readme_path.read_text(encoding="utf-8")
                api_key = os.environ.get("OPENROUTER_API_KEY", "")
                if not api_key:
                    from repologogen.config import get_api_key

                    api_key = get_api_key(project_path) or ""
                if api_key:
                    project_description = digest_readme(
                        readme_content, api_key, text_model=config.text_model
                    )
            except Exception:
                pass  # Fail gracefully — description is optional

        if verbose and project_description:
            console.print(f"[dim]Project description: {project_description}[/dim]")

    if config.visual_metaphor == "none":
        visual_metaphor = "Abstract geometric shape"
    elif config.visual_metaphor:
        visual_metaphor = config.visual_metaphor
    else:
        visual_metaphor = get_visual_metaphor(project_type)

    resolved_output = resolve_output_path(config.output_path, project_name, project_path)

    console.print(f"[bold blue]Target path:[/bold blue] {resolved_output}")
    console.print(
        f"[bold blue]Config sources:[/bold blue] {', '.join(config.meta.get('sources', ['defaults']))}"
    )

    if verbose:
        console.print(f"[dim]Output path: {resolved_output}[/dim]")

    raw_prompt = build_prompt(
        project_name=project_name,
        style=config.style,
        icon_colors=config.icon_colors,
        key_color=config.key_color,
        visual_metaphor=visual_metaphor,
        include_repo_name=config.include_repo_name,
        additional_instructions=config.additional_instructions,
        prompt_template=config.prompt_template,
        template_vars=template_vars,
        project_description=project_description,
    )

    # Refine prompt via LLM unless disabled
    prompt = raw_prompt
    should_refine = config.refine_prompt and not no_refine
    if should_refine:
        with console.status("[bold green]Refining prompt..."):
            api_key = os.environ.get("OPENROUTER_API_KEY", "")
            if not api_key:
                from repologogen.config import get_api_key

                api_key = get_api_key(project_path) or ""
            if api_key:
                prompt = refine_prompt(
                    raw_prompt, config.model, api_key, text_model=config.text_model
                )

    if verbose and prompt != raw_prompt:
        console.print("\n[dim]Raw prompt:[/dim]")
        console.print(f"[dim]{raw_prompt}[/dim]")

    console.print("\n[bold blue]Prompt:[/bold blue]")
    console.print(prompt)

    if dry_run:
        console.print("\n[bold cyan]Dry Run Summary:[/bold cyan]")
        console.print(f"  Project: [green]{project_name}[/green]")
        console.print(f"  Type: [green]{project_type}[/green]")
        console.print(f"  Style: [green]{config.style}[/green]")
        console.print(f"  Output: [green]{resolved_output}[/green]")
        console.print(f"  Model: [green]{config.model}[/green]")
        if project_description:
            console.print(f"  Description: [green]{project_description}[/green]")
        console.print(f"  Refinement: [green]{'enabled' if should_refine else 'disabled'}[/green]")
        return 0

    try:
        generator = ImageGenerator(project_path=project_path)
    except ImageGeneratorError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        console.print(
            "[dim]Set OPENROUTER_API_KEY in environment or ~/.repologogen/config.yaml[/dim]"
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
                model=config.model,
                output_path=resolved_output,
                size=config.size,
            )
            progress.update(task, completed=True)

            task = progress.add_task("[green]Applying transparency...", total=None)
            chromakey_result = chromakey_to_transparent(
                resolved_output,
                resolved_output,
                key_color=config.key_color,
                tolerance=config.tolerance,
            )
            progress.update(task, completed=True)

            if config.trim:
                task = progress.add_task("[green]Trimming transparent padding...", total=None)
                trim_transparent(resolved_output, resolved_output, margin=config.trim_margin)
                progress.update(task, completed=True)

            if config.compress:
                task = progress.add_task("[green]Compressing image...", total=None)
                compress_png(resolved_output, resolved_output, quality=config.compress_quality)
                progress.update(task, completed=True)

        info = get_image_info(resolved_output)

        console.print("\n[bold green]Logo generated successfully![/bold green]")
        console.print(f"  Output: [cyan]{resolved_output}[/cyan]")
        console.print(f"  Size: [cyan]{info['size'][0]}x{info['size'][1]}[/cyan]")
        console.print(f"  File size: [cyan]{info['file_size']:,} bytes[/cyan]")
        console.print(f"  Transparency: [cyan]{info['transparency_percent']}%[/cyan]")

        if verbose:
            console.print(
                f"\n[dim]Chromakey: {chromakey_result['transparent_pixels']:,} "
                "pixels made transparent[/dim]"
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

    # Parse --var arguments into a dictionary
    template_vars = {}
    if args.var:
        for var in args.var:
            if "=" not in var:
                console.print(
                    f"[bold red]Error:[/bold red] Invalid --var format: {var}. Use KEY=VALUE"
                )
                return 1
            key, value = var.split("=", 1)
            template_vars[key] = value

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
        no_refine=args.no_refine,
    )


if __name__ == "__main__":
    sys.exit(main())
