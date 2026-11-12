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

CLI tool that generates professional logos with transparent backgrounds using OpenRouter models
through AgentBridge.

**Module pipeline**: `cli.py` → `config.py` → `detector.py` → `generator.py` → `processor.py`

- **cli.py** - Argparse entry point, orchestrates the generation workflow
- **config.py** - Built-in defaults and config-related helpers used by the planner/runtime
- **detector.py** - Project type detection from file patterns (pyproject.toml → python, etc.)
- **generator.py** - AgentBridge API client (OpenAI-compatible), prompt template builder
- **processor.py** - Pillow-based image processing: chromakey→transparent, trim, compress

**Runtime config**: built-in defaults + command-line overrides only

**Gateway settings**: `AGENTBRIDGE_BASE_URL` defaults to `http://127.0.0.1:8082/api/v1`;
`AGENTBRIDGE_API_KEY` is an optional access token read only from the environment.

## Code Style

Configured in `pyproject.toml`:
- **ruff**: line-length 100, double quotes, py311 target, select E/F/I/N/W/UP/B/C4/SIM
- **mypy**: strict mode enabled
- **pytest**: testpaths=tests, `-v --tb=short`

## Maintenance

- README.md must be kept up to date with any significant project changes
- The repo-owned Codex skill lives in `skills/repologogen_generate-brand-assets/`
- Any change to CLI flags, defaults, output paths, auth requirements, or workflow shortcuts must update `skills/repologogen_generate-brand-assets/SKILL.md` and `skills/repologogen_generate-brand-assets/agents/openai.yaml` if needed
- Keep `scripts/install_codex_skill.py` working whenever the skill layout changes

## Agent Vault access for local AI calls

For agent-operated AI requests, use the opt-in repository launcher:

```sh
mkdir -p .internal/agent-vault/work
python3 -I -S scripts/infisical/agentbridge_vault.py check --workspace "$PWD/.internal/agent-vault/work"
python3 -I -S scripts/infisical/agentbridge_vault.py run --workspace "$PWD/.internal/agent-vault/work" -- --help
```

The workspace must be `.internal/agent-vault/work` under this checkout, or a
subdirectory of it; broader directory overrides are rejected.

Pass the ordinary tool arguments after `--`. The workspace is the working
directory and the only writable directory under the user's home. Stage only
explicitly selected non-secret inputs and profiles there. The launcher uses an
isolated HOME inside that directory, skips dotenv loading, and does not discover
existing personal profiles, caches or credentials. Worktrees and changes to the
native binding/guard require a separate trusted profile review; never borrow a
different repository's profile or inject a raw key as a fallback.

The reviewed service mapping is bundle `local-repologogen-agentbridge`, service
`repologogen-agentbridge-0`, for `127.0.0.1:8082` GET `/api/v1/models` and POST
`/api/v1/chat/completions`. The native `.infisical.yaml` uses YAML's JSON subset
and pins this repository's metadata-only Development identity and
`/agents/agentbridge` folder. No service keys are copied into or read from that
folder. The gateway's existing upstream Agent Vault route owns provider keys.

The protected profile under
`~/.config/infisical/agentbridge-python/profiles/repologogen.json` pins native and
loaded application-source hashes, the dedicated bundle, Python environment, HTTPS instance, proxy
and public CA. The child receives `agentbridge_public_placeholder` and a scoped
proxy capability. The native Agent Vault session plus an enforced OS sandbox
blocks other egress, home credential reads and credential-helper execution.
Trust is process-local; global shell, CA trust and MCP/app defaults are unchanged.
Trusted setup and full-access host processes remain outside the child boundary.

Fake tests exercise the actual application HTTP client, rejection sanitization,
placeholder guards and filesystem/network restrictions. `check` is a bounded
live catalog GET; it does not establish live inference availability. Prompts,
documents, uploads and generation require the usual separate content approval.
Models, normal tool entrypoints and production behavior are unchanged. External
image download hosts and non-Python conversion executables are not enabled;
unsupported operations stop explicitly without broadening access or falling back.
Use synthetic fixtures for checks; never process personal documents as migration
validation. Run `python3 -m unittest discover -s tests -p test_agentbridge_vault.py`
for the offline boundary regressions.

The reviewed launcher pins Infisical CLI 0.45.6 and explicitly selects its Vault
project. The protected profile checks every Python file in the application
package, the four Vault bootstrap files, the dependency manifests, Python, CLI
and public CA before authentication. Added, changed or symlinked source files,
conflicting native identity files and altered runtime pins fail closed and need
trusted review. This integrity check does not isolate the full-access host or
verify provider inference; the catalog check remains metadata-only.
