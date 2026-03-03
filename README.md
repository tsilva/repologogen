# Logogen

CLI tool for generating professional logos with transparent backgrounds using AI image generation.

## Features

- **AI-Powered Generation**: Uses OpenAI-compatible APIs (default: OpenRouter) to generate logos
- **Automatic Transparency**: Applies chromakey technique for clean transparent backgrounds
- **Smart Trimming**: Maximizes canvas utilization by trimming transparent padding
- **Project Detection**: Auto-detects project type from repository structure
- **Configurable**: JSON-based configuration with user and project-level overrides
- **PNG Compression**: Optimizes file size while maintaining quality

## Installation

```bash
pip install repologogen
```

Or install from source:

```bash
git clone https://github.com/tsilva/repologogen.git
cd repologogen
pip install -e .
```

## Quick Start

1. Set your API key (choose one method):

   **Option A - Environment variable:**
   ```bash
   export OPENROUTER_API_KEY="your-api-key-here"
   ```

   **Option B - .env file (in project root):**
   ```bash
   cp .env.example .env
   # Edit .env and add your key
   ```

   **Option C - Tool install config (for `uv tool install`):**
   ```bash
   mkdir -p ~/.repologogen
   echo '{"openrouter_api_key": "your-api-key-here"}' > ~/.repologogen/config.json
   ```

2. Generate a logo:
```bash
repologogen  # Uses current directory
```

3. View results:
```bash
open logo.png
```

## Usage

### Basic Commands

```bash
# Generate logo for current project
repologogen

# Generate for specific project
repologogen /path/to/project

# Preview what would be generated (dry run)
repologogen --dry-run

# Verbose output
repologogen -v

# Custom style
repologogen -s "pixel art"

# Custom output path
repologogen -o assets/logo.png
```

### Configuration

Configuration files are loaded in this priority order:
1. Project config: `.repologogen.json` in project root
2. User config: `~/.repologogen/config.json`
3. Built-in defaults

**Example `.repologogen.json`:**
```json
{
  "logo": {
    "style": "minimalist",
    "icon_colors": ["#58a6ff", "#d29922"],
    "key_color": "#00FF00",
    "output_path": "docs/logo.png",
    "trim": true,
    "compress": true
  }
}
```

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `model` | `google/gemini-3-pro-image-preview` | AI model for generation |
| `style` | `minimalist` | Logo style descriptor |
| `visual_metaphor` | `null` | Override visual metaphor (or `none`) |
| `include_repo_name` | `false` | Include project name as text |
| `icon_colors` | `["#58a6ff", ...]` | Color palette |
| `key_color` | `#00FF00` | Chromakey background color |
| `tolerance` | `70` | Edge detection tolerance |
| `output_path` | `logo.png` | Output file path |
| `trim` | `true` | Trim transparent padding |
| `trim_margin` | `5` | Trim margin percentage |
| `compress` | `true` | Enable PNG compression |
| `compress_quality` | `80` | Compression quality (1-100) |

## How It Works

1. **Configuration Loading**: Merges project, user, and default configs
2. **Project Analysis**: Detects project type (Python, Node.js, Rust, etc.)
3. **Prompt Building**: Constructs an AI prompt based on project context
4. **Image Generation**: Calls AI API to generate logo with chromakey background
5. **Transparency**: Converts chromakey color to transparent pixels
6. **Trimming**: Crops excess transparent space and resizes to fill canvas
7. **Compression**: Optimizes PNG file size
8. **Verification**: Reports file size, dimensions, and transparency percentage

## Development

```bash
# Clone repository
git clone https://github.com/tsilva/repologogen.git
cd repologogen

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check src/
ruff format src/

# Type checking
mypy src/repologogen/
```

## Requirements

- Python 3.10+
- OpenRouter API key (configured via environment variable, .env file, or ~/.repologogen/config.json)
- Supported models: Any OpenAI-compatible image generation API

## License

MIT License - see LICENSE file for details.

## Related

This CLI tool is a standalone adaptation of the `project-logo-author` skill from the [claudeskillz](https://github.com/tsilva/claudeskillz) project.
