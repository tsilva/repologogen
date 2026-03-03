<div align="center">
  <img src="logo.png" alt="repologogen" width="512"/>

  [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
  [![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org)
  [![OpenRouter](https://img.shields.io/badge/Powered_by-OpenRouter-6366F1.svg)](https://openrouter.ai)

  **🎨 Generate professional logos with transparent backgrounds from the command line ✨**

  [Installation](#-installation) · [Quick Start](#-quick-start) · [Configuration](#%EF%B8%8F-configuration)
</div>

---

## Overview

**The pain:** Every project needs a logo, but commissioning one takes time and money. Stock icons look generic. AI tools require manual transparency cleanup, awkward cropping, and repetitive prompt engineering.

**The solution:** repologogen auto-detects your project type, builds a tailored prompt, generates a logo via OpenRouter's 300+ AI models, and produces a clean transparent PNG — all in one command.

**The result:** A production-ready logo in under 30 seconds, with zero manual post-processing.

## ⚡ Features

- **One-Command Generation** — Point at any repo and get a polished logo
- **Automatic Transparency** — Chromakey-to-alpha conversion with graduated edge detection
- **Smart Trimming** — Crops excess padding and resizes to fill the canvas
- **Project Detection** — Recognizes Python, Node.js, Rust, Go, Java, .NET, Ruby, PHP, and C++ projects
- **3-Tier Config** — Project `.config.yaml` > User `~/.repologogen/config.yaml` > Built-in defaults
- **Custom Prompts** — Full template system with variables for style, colors, metaphors, and more
- **PNG Compression** — Optimized file size with configurable quality
- **Dry Run Mode** — Preview the generated prompt before spending API credits

## 📦 Installation

```bash
pip install repologogen
```

Or install from source:

```bash
git clone https://github.com/tsilva/repologogen.git
cd repologogen
pip install -e .
```

## 🚀 Quick Start

**1. Set your API key** (pick one):

```bash
# Option A: Environment variable
export OPENROUTER_API_KEY="your-key"

# Option B: User config (persists across projects)
mkdir -p ~/.repologogen
echo 'openrouter_api_key: your-key' > ~/.repologogen/config.yaml
```

**2. Generate:**

```bash
repologogen
```

**3. Done.** Your `logo.png` is ready with a transparent background.

## 🛠️ Usage

```bash
# Generate logo for current project
repologogen

# Target a specific project
repologogen /path/to/project

# Custom style
repologogen -s "pixel art"

# Custom output path
repologogen -o assets/logo.png

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
| `-s`, `--style` | Override logo style |
| `-o`, `--output` | Override output path |
| `-n`, `--name` | Override project name |
| `-m`, `--model` | Override AI model |
| `-c`, `--config` | Path to custom config file |
| `--no-trim` | Skip transparent padding trim |
| `--no-compress` | Skip PNG compression |
| `--dry-run` | Show prompt without generating |
| `--var KEY=VALUE` | Set template variable (repeatable) |
| `-v`, `--verbose` | Enable verbose output |

## ⚙️ Configuration

Configuration loads in priority order — project overrides user, user overrides defaults:

```
.config.yaml (project) > ~/.repologogen/config.yaml (user) > built-in defaults
```

**Example `.config.yaml`:**

```yaml
model: google/gemini-3-pro-image-preview
size: 1K
style: "SNES 16-bit pixel art"
icon_colors:
  - "#58a6ff"
  - "#d29922"
  - "#a371f7"
key_color: "#00FF00"
tolerance: 70
output_path: logo.png
include_repo_name: true
trim: true
trim_margin: 5
compress: true
compress_quality: 80
```

### All Options

| Option | Default | Description |
|--------|---------|-------------|
| `model` | `google/gemini-3-pro-image-preview` | AI model for image generation |
| `size` | `1K` | Image size (`1K`, `2K`, etc.) |
| `style` | `minimalist` | Logo style descriptor |
| `visual_metaphor` | `null` | Custom visual metaphor (`null` = auto-detect, `none` = abstract) |
| `include_repo_name` | `false` | Include project name as text in logo |
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

### Custom Prompt Templates

Override the default prompt with your own template using any of these variables:

```yaml
prompt_template: >-
  Create a {STYLE} icon for {PROJECT_NAME}.
  Use colors: {ICON_COLORS}. Background: {KEY_COLOR}.
  {TEXT_INSTRUCTIONS}
```

**Built-in variables:** `{PROJECT_NAME}`, `{STYLE}`, `{ICON_COLORS}`, `{KEY_COLOR}`, `{VISUAL_METAPHOR}`, `{TEXT_INSTRUCTIONS}`

Additional variables can be passed via `--var KEY=VALUE` on the CLI.

## 🔧 How It Works

```
cli.py → config.py → detector.py → generator.py → processor.py
```

1. **Config Loading** — Merges project, user, and default YAML configs with JSON Schema validation
2. **Project Detection** — Matches file patterns (`pyproject.toml` → Python, `package.json` → Node.js, etc.)
3. **Prompt Building** — Fills template with project name, style, colors, and visual metaphor
4. **Image Generation** — Calls OpenRouter API (OpenAI-compatible) with the constructed prompt
5. **Chromakey → Transparent** — Pixel-level color distance matching converts background to alpha
6. **Trim** — Crops transparent padding, resizes to fill original canvas with configurable margin
7. **Compress** — Optimizes PNG with configurable quality/compression level

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
