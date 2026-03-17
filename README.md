<div align="center">
  <img src="https://raw.githubusercontent.com/tsilva/repologogen/main/logo.png" alt="repologogen" width="512"/>

  [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
  [![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org)
  [![OpenRouter](https://img.shields.io/badge/Powered_by-OpenRouter-6366F1.svg)](https://openrouter.ai)

  **🎨 Generate repo logos, brand packs, and platform assets from the command line ✨**

  [Installation](#-installation) · [Quick Start](#-quick-start) · [Configuration](#%EF%B8%8F-configuration)
</div>

---

## Overview

[![CI](https://github.com/tsilva/repologogen/actions/workflows/release.yml/badge.svg)](https://github.com/tsilva/repologogen/actions/workflows/release.yml)

**The pain:** Every project needs a logo, but commissioning one takes time and money. Stock icons look generic. AI tools require manual transparency cleanup, awkward cropping, and repetitive prompt engineering.

**The solution:** repologogen auto-detects your project type, builds tailored prompts, generates a primary logo, derives a dedicated icon mark from that logo, and expands the brand into core assets plus optional platform packs for Web SEO, Google Play, and the Apple App Store.

**The result:** Production-ready repo branding in under 30 seconds, with zero manual post-processing.

## ⚡ Features

- **One-Command Generation** — Point at any repo and get a polished logo, core brand pack, or targeted platform assets
- **Automatic Transparency** — Chromakey-to-alpha conversion with graduated edge detection
- **Smart Trimming** — Crops excess padding and resizes to fill the canvas
- **Logo-First Derivation** — Generate the main logo first, then derive the icon mark and resize-only small assets from it
- **Platform Packs** — Add Web SEO, Google Play, and Apple Store assets with repeatable `--target` flags
- **Reference-Guided Marketing Art** — Generate text-bearing graphics from the main logo as a visual reference instead of stretching/resizing them
- **Project Detection** — Recognizes Python, Node.js, Rust, Go, Java, .NET, Ruby, PHP, and C++ projects
- **CLI-Only Defaults** — Built-in defaults plus command-line overrides, with a short `--web` workflow for common Next.js-style branding
- **Custom Prompts** — Full template system with variables for style, colors, metaphors, and more
- **PNG Compression** — Optimized file size with configurable quality
- **Dry Run Mode** — Preview the generated prompt before spending API credits

## 📦 Installation

```bash
pip install repologogen
```

Set the API key:

```bash
export OPENROUTER_API_KEY="your-key"
```

Or write it to `~/.config/repologogen/.env`:

```bash
mkdir -p ~/.config/repologogen
printf 'OPENROUTER_API_KEY="your-key"\n' > ~/.config/repologogen/.env
```

Or install from source:

```bash
git clone https://github.com/tsilva/repologogen.git
cd repologogen
pip install -e .
```

## Codex Skill

This repo includes a Codex skill source at `skills/repologogen/`.

Install or refresh it into `~/.codex/skills/repologogen` with:

```bash
python3 scripts/install_codex_skill.py
```

Or via Make:

```bash
make install-skill
```

After installation, you can invoke it in any repo with prompts like:

```text
$repologogen generate web branding for this repo
```

## 🚀 Quick Start

**1. Set your API key**:

```bash
export OPENROUTER_API_KEY="your-key"
```

Or:

```bash
mkdir -p ~/.config/repologogen
printf 'OPENROUTER_API_KEY="your-key"\n' > ~/.config/repologogen/.env
```

**2. Generate:**

```bash
# Logo only
repologogen

# Shortest web brand pack flow
repologogen --web

# Core brand pack plus multiple platform assets
repologogen --target web-seo --target google-play --target apple-store
```

**3. Done.** Your `logo.png` or `repologogen-assets/` pack is ready.

## 🛠️ Usage

```bash
# Generate logo for current project
repologogen

# Generate platform-ready assets from the base logo
repologogen --target web-seo --target google-play

# Generate Next.js-ready SEO assets with the shortest command
repologogen --web

# Target a specific project
repologogen /path/to/project --target apple-store

# Custom style across generated assets
repologogen -s "pixel art"

# Custom output path
repologogen -o assets/logo.png

# Custom asset directory for the core brand bundle
repologogen --target web-seo --assets-dir branding

# Override project name
repologogen -n "My Project"

# Preview prompt without generating
repologogen --dry-run

# Verbose output
repologogen -v
```

### CLI Flags

| Flag | Description |
|------|-------------|
| `--bundle` | Select `logo` or target-driven `core-brand` generation mode |
| `--target` | Add `web-seo`, `google-play`, and/or `apple-store`; any target implies `core-brand` |
| `--web` | Shortest web workflow: implies `core-brand`, `web-seo`, and `public/brand` |
| `-s`, `--style` | Override logo style |
| `-o`, `--output` | Override output path for the `logo` bundle |
| `--assets-dir` | Override output directory for bundle assets |
| `--manifest` | Override manifest path (defaults to `<assets-dir>/manifest.json`) |
| `-n`, `--name` | Override project name |
| `-m`, `--model` | Override AI model |
| `--text-model` | Override text model for README digestion and prompt refinement |
| `--size` | Override image size (`1K`, `2K`, etc.) |
| `--visual-metaphor` | Override the visual metaphor or use `none` for abstract |
| `--icon-colors` | Override palette as a comma-separated list or descriptive string |
| `--instructions` | Append extra instructions to the prompt |
| `--key-color` | Override chromakey background color |
| `--tolerance` | Override chromakey edge tolerance |
| `--trim-margin` | Override transparent trim margin percentage |
| `--quality` | Override PNG compression quality |
| `--no-metadata` | Skip generated metadata outputs |
| `--no-trim` | Skip transparent padding trim |
| `--no-compress` | Skip PNG compression |
| `--no-refine` | Skip prompt refinement |
| `--dry-run` | Show prompt without generating |
| `--var KEY=VALUE` | Set template variable (repeatable) |
| `-v`, `--verbose` | Enable verbose output |

## ⚙️ Defaults

repologogen now runs with built-in defaults plus command-line overrides only. There are no project or user settings files in the runtime path.

### Built-In Defaults

| Option | Default | Description |
|--------|---------|-------------|
| `model` | `google/gemini-3-pro-image-preview` | AI model for image generation |
| `text_model` | `google/gemini-3-flash-preview` | LLM used for README digestion and prompt refinement |
| `size` | `1K` | Image size (`1K`, `2K`, etc.) |
| `style` | `bold, cinematic, sensory-rich brand icon` | Logo style descriptor |
| `visual_metaphor` | `null` | Custom visual metaphor (`null` = auto-detect, `none` = abstract) |
| `include_repo_name` | `false` | Include project name as text in generated assets. The primary logo always includes the project name. |
| `icon_colors` | `["#58a6ff", ...]` | Color palette (array or string) |
| `key_color` | `#00FF00` | Chromakey background color |
| `tolerance` | `70` | Chromakey edge detection tolerance (0–255) |
| `output_path` | `logo.png` | Output file path (supports `{PROJECT_NAME}`) |
| `trim` | `true` | Trim transparent padding |
| `trim_margin` | `5` | Margin percentage around trimmed content (0–25) |
| `compress` | `true` | Enable PNG compression |
| `compress_quality` | `80` | Compression quality (1–100) |
| `additional_instructions` | `""` | Extra text appended to the AI prompt |
| `prompt_template` | `null` | Fully custom prompt template |
| `bundle` | `logo` | Default bundle to generate (`logo` or `core-brand`) |
| `targets` | `[]` | Platform packs to add to the `core-brand` bundle |
| `assets_dir` | `repologogen-assets` | Output directory for bundle assets |
| `manifest_path` | `<assets-dir>/manifest.json` | Manifest path for the bundle output |

The primary `logo` asset always includes the project/repo name so README and top-level branding stay identifiable. `icon` and `favicon` stay text-free in the `core-brand` bundle.

`assets.social_card` controls the wide text-bearing graphics, including the `web-seo` OG image and Google Play feature graphic.
The `web-seo` OG image uses a typical preview-card layout: one short headline plus an optional short tagline.

### Bundle Output

`repologogen --bundle core-brand --target ...` writes shared logo/icon outputs and the selected platform pack folders:

```text
repologogen-assets/
├── icon/
│   └── icon-1024.png
├── logo/
│   └── logo-1024.png
├── web-seo/
│   ├── android-chrome-192.png
│   ├── android-chrome-512.png
│   ├── apple-touch-icon.png
│   ├── favicon/
│   │   ├── favicon-16.png
│   │   ├── favicon-32.png
│   │   ├── favicon-48.png
│   │   └── favicon.ico
│   ├── og-image-1200x630.png
│   └── site.webmanifest
├── google-play/
│   ├── feature-graphic-1024x500.png
│   └── google-play-icon-512.png
├── apple-store/
│   └── app-store-icon-1024.png
└── manifest.json
```

The manifest includes asset paths plus reusable metadata fields:

- `title`
- `short_description`
- `social_title`
- `social_description`
- `keywords`

When `web-seo` is selected, repologogen also writes Next.js-ready metadata helpers:

```text
web-seo-metadata.json
web-seo-metadata.ts
```

The generated TypeScript helper exports `createMetadata(metadataBase: URL)` so a Next.js app can wire it directly into `app/layout.ts`:

```ts
import { createMetadata } from "@/web-seo-metadata";

export const metadata = createMetadata(new URL(process.env.NEXT_PUBLIC_SITE_URL!));
```

For the smoothest Next.js setup, generate static assets into `public/brand`:

```bash
repologogen --web
```

### Custom Prompt Templates

Override the default prompt with your own template using any of these variables:

```text
Create a {STYLE} icon for {PROJECT_NAME}.
Use colors: {ICON_COLORS}. Background: {KEY_COLOR}.
{TEXT_INSTRUCTIONS}
```

Pass template variables with:

```bash
repologogen --var KEY=VALUE --var OTHER_KEY=OTHER_VALUE
```

Example template content:

```text
  Create a {STYLE} icon for {PROJECT_NAME}.
  Use colors: {ICON_COLORS}. Background: {KEY_COLOR}.
  {TEXT_INSTRUCTIONS}
```

**Built-in variables:** `{PROJECT_NAME}`, `{STYLE}`, `{ICON_COLORS}`, `{KEY_COLOR}`, `{VISUAL_METAPHOR}`, `{TEXT_INSTRUCTIONS}`

Additional variables can be passed via `--var KEY=VALUE` on the CLI.

## 🔧 How It Works

```
cli.py → config.py → detector.py → planner.py → generator.py → processor.py
```

1. **Default Resolution** — Starts from bundled defaults, then applies command-line overrides and shorthand presets
2. **Project Detection** — Matches file patterns (`pyproject.toml` → Python, `package.json` → Node.js, etc.)
3. **Planning** — Resolves the selected bundle, per-asset overrides, and output paths
4. **Image Generation** — Calls OpenRouter API (OpenAI-compatible) for a canonical transparent brand mark
5. **Processing** — Applies chromakey removal, trim, and compression to the generated logo and icon sources
6. **Icon Extraction** — Uses the main logo as a reference image to generate a text-free icon mark
7. **Derivation** — Resizes the icon mark into favicon, app-icon, and store-icon outputs where text is not required
8. **Reference Expansion** — Generates text-bearing SEO/store graphics from the main logo as a reference image
9. **Metadata** — Writes manifest JSON plus a `site.webmanifest` when the `web-seo` target is selected

### Supported Project Types

| File Pattern | Detected Type |
|-------------|---------------|
| `pyproject.toml`, `setup.py`, `Pipfile` | Python |
| `package.json` | Node.js |
| `Cargo.toml` | Rust |
| `go.mod` | Go |
| `pom.xml`, `build.gradle` | Java |
| `*.sln`, `*.csproj` | .NET |
| `Gemfile` | Ruby |
| `composer.json` | PHP |
| `CMakeLists.txt` | C++ |

## 🧑‍💻 Development

```bash
git clone https://github.com/tsilva/repologogen.git
cd repologogen
pip install -e ".[dev]"

# Run tests
pytest

# Lint & format
ruff check src/ tests/
ruff format src/ tests/

# Type checking
mypy src/repologogen/
```

## 📄 License

[MIT](LICENSE)

## 🔗 Related

This CLI is a standalone adaptation of the `project-logo-author` skill from [claudeskillz](https://github.com/tsilva/claudeskillz).
