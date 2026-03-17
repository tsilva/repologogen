# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Build & Run Commands

- **Install**: `pip install -e ".[dev]"`
- **Run**: `repologogen [path] [options]`
- **Install Codex skill**: `python3 scripts/install_codex_skill.py`
- **Test all**: `pytest`
- **Test single**: `pytest tests/test_config.py::TestClassName::test_name -v`
- **Lint**: `ruff check src/ tests/`
- **Format**: `ruff format src/ tests/`
- **Type check**: `mypy src/repologogen/`

## Architecture

CLI tool that generates professional logos with transparent backgrounds via OpenRouter API.

**Module pipeline**: `cli.py` → `config.py` → `detector.py` → `generator.py` → `processor.py`

- **cli.py** - Argparse entry point, orchestrates the generation workflow
- **config.py** - Built-in defaults and config-related helpers used by the planner/runtime
- **detector.py** - Project type detection from file patterns (pyproject.toml → python, etc.)
- **generator.py** - OpenRouter API client (OpenAI-compatible), prompt template builder
- **processor.py** - Pillow-based image processing: chromakey→transparent, trim, compress

**Runtime config**: built-in defaults + command-line overrides only

**API key sources** (checked in order): `OPENROUTER_API_KEY` env var → `~/.config/repologogen/.env`

## Code Style

Configured in `pyproject.toml`:
- **ruff**: line-length 100, double quotes, py310 target, select E/F/I/N/W/UP/B/C4/SIM
- **mypy**: strict mode enabled
- **pytest**: testpaths=tests, `-v --tb=short`

## Maintenance

- README.md must be kept up to date with any significant project changes
- The repo-owned Codex skill lives in `skills/repologogen/`
- Any change to CLI flags, defaults, output paths, auth requirements, or workflow shortcuts must update `skills/repologogen/SKILL.md` and `skills/repologogen/agents/openai.yaml` if needed
- Keep `scripts/install_codex_skill.py` working whenever the skill layout changes
