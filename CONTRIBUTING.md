# Contributing to repologogen

## Development Setup

```bash
# Clone the repository
git clone https://github.com/tsilva/repologogen.git
cd repologogen

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=repologogen --cov-report=html

# Run specific test file
pytest tests/test_config.py
```

## Code Quality

```bash
# Linting
ruff check src/

# Format code
ruff format src/

# Type checking
mypy src/repologogen/
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## Code Style

- Follow PEP 8 guidelines
- Use type hints where possible
- Add docstrings to public functions
- Keep functions focused and small
- Write tests for new features

## Reporting Issues

When reporting issues, please include:
- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Any error messages
