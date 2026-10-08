<p align="center">
  <img src="https://raw.githubusercontent.com/tsilva/repologogen/main/logo.png" alt="repologogen" width="420" />
  <br />
  <!-- repo-tagline:start -->
  <strong>🎨 Generate repository logos, brand packs, and platform assets ✨</strong>
  <!-- repo-tagline:end -->
</p>

<p align="center">
  <a href="https://github.com/tsilva/repologogen/blob/main/pyproject.toml"><img src="https://img.shields.io/badge/python-%E2%89%A53.10-blue" alt="Python 3.10 or newer" /></a>
  <a href="https://github.com/tsilva/repologogen/blob/main/LICENSE"><img src="https://img.shields.io/github/license/tsilva/repologogen" alt="MIT license" /></a>
</p>

repologogen is a Python command-line tool for developers who need logos and matching brand
assets for their projects. Point it at a repository to generate a transparent PNG logo,
or create a pack with icons, favicons, social images, and app store graphics.

It reads the project's files and README to guide generation, then removes the logo's
chromakey background, trims padding, and compresses the output. Model requests go through
AgentBridge, which manages the upstream OpenRouter credentials.

## Install

Requires Python 3.10+, [uv](https://docs.astral.sh/uv/getting-started/installation/), and a
running AgentBridge gateway for generation. Install from source:

```bash
git clone https://github.com/tsilva/repologogen.git
cd repologogen
uv sync --extra dev
uv run repologogen --help
```

Run `uv run repologogen /path/to/project` to write `logo.png` in that project. Existing
output files are overwritten.

## Use

```bash
uv run repologogen /path/to/project --web
uv run repologogen /path/to/project --target web-seo --target google-play --target apple-store
uv run repologogen /path/to/project -s "pixel art" -n "My Project"
```

## Commands

```bash
uv run repologogen                              # generate logo.png in the current project
uv run repologogen --dry-run                    # preview the output plan
uv run repologogen --web                        # write web assets to public/brand
uv run repologogen --target google-play         # include Play icon and feature graphic
uv run repologogen --target apple-store         # include App Store icon
uv run repologogen -o assets/logo.png           # choose the logo output path
uv run repologogen --web --assets-dir branding  # choose the brand pack directory
uv run repologogen --var KEY=VALUE              # pass a prompt-template variable
uv run repologogen --no-trim --no-compress      # skip trimming and PNG compression
uv run repologogen --help                       # list all options
uv run pytest                                  # run tests
uv run ruff check src/ tests/                   # lint
uv run mypy src/repologogen/                    # type check
```

## Notes

- AgentBridge defaults to `http://127.0.0.1:8082/api/v1`. Set `AGENTBRIDGE_BASE_URL`
  to use a different gateway API root and `AGENTBRIDGE_API_KEY` if it requires an
  access token. The CLI does not read upstream keys or fall back to a direct provider.
- Model IDs gain the gateway's `openrouter/` namespace when needed. Use `--model`
  and `--text-model` to override the image and text models.
- Runtime settings come from built-in defaults and CLI flags; settings files are not read.
- `--dry-run` skips image generation and file writes, but README analysis and metadata
  extraction can still make text-model requests.
- `--web` implies `core-brand`, adds the `web-seo` target, and writes assets to
  `public/brand`. It also writes `web-seo-metadata.json` and `web-seo-metadata.ts`
  in the target project for Next.js integration.
- Each `--target` implies `core-brand`; targets can be combined. Without `--web`,
  brand packs default to `repologogen-assets`. All output paths are relative to
  the target project unless absolute.
- Brand packs write `<assets-dir>/manifest.json`; override it with `--manifest`.
- Install or refresh the [repo-owned Codex skill](skills/repologogen/SKILL.md) with
  `python3 scripts/install_codex_skill.py` or `make install-skill`.

## License

[MIT](LICENSE)
