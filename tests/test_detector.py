"""Tests for repologogen detector module."""

from repologogen.detector import (
    detect_project,
    find_readme,
    get_visual_metaphor,
    glob_match,
)


class TestGlobMatch:
    """Test glob_match function."""

    def test_exact_match(self):
        """Test exact filename matching."""
        files = ["package.json", "setup.py", "README.md"]
        assert glob_match("package.json", files) == ["package.json"]
        assert glob_match("README.md", files) == ["README.md"]

    def test_wildcard_extension(self):
        """Test wildcard extension matching."""
        files = ["test.csproj", "app.csproj", "lib.dll"]
        assert glob_match("*.csproj", files) == ["test.csproj", "app.csproj"]
        assert glob_match("*.dll", files) == ["lib.dll"]

    def test_no_match(self):
        """Test no matches found."""
        files = ["a.py", "b.py"]
        assert glob_match("*.js", files) == []


class TestDetectProject:
    """Test detect_project function."""

    def test_detects_nodejs(self, tmp_path):
        """Test Node.js project detection."""
        (tmp_path / "package.json").write_text("{}")
        result = detect_project(tmp_path)
        assert result["type"] == "nodejs"
        assert result["confidence"] == "high"
        assert "package.json" in result["files"]

    def test_detects_python(self, tmp_path):
        """Test Python project detection."""
        (tmp_path / "pyproject.toml").write_text("")
        result = detect_project(tmp_path)
        assert result["type"] == "python"
        assert result["confidence"] == "high"
        assert "pyproject.toml" in result["files"]

    def test_detects_rust(self, tmp_path):
        """Test Rust project detection."""
        (tmp_path / "Cargo.toml").write_text("")
        result = detect_project(tmp_path)
        assert result["type"] == "rust"
        assert result["confidence"] == "high"

    def test_unknown_project_type(self, tmp_path):
        """Test unknown project type."""
        result = detect_project(tmp_path)
        assert result["type"] == "unknown"
        assert result["confidence"] == "none"

    def test_returns_error_for_non_directory(self, tmp_path):
        """Test error handling for non-directory path."""
        file_path = tmp_path / "not-a-dir.txt"
        file_path.write_text("")
        result = detect_project(file_path)
        assert result["type"] == "unknown"
        assert "error" in result


class TestFindReadme:
    """Test find_readme function."""

    def test_finds_readme_md(self, tmp_path):
        """Test finding standard README.md."""
        (tmp_path / "README.md").write_text("# Hello")
        result = find_readme(tmp_path)
        assert result is not None
        assert result.name == "README.md"

    def test_finds_lowercase_readme(self, tmp_path):
        """Test finding lowercase readme.md (case-insensitive)."""
        (tmp_path / "readme.md").write_text("# Hello")
        result = find_readme(tmp_path)
        assert result is not None
        assert result.name == "readme.md"

    def test_returns_none_when_no_readme(self, tmp_path):
        """Test returns None when no README exists."""
        (tmp_path / "setup.py").write_text("")
        result = find_readme(tmp_path)
        assert result is None

    def test_returns_none_for_non_directory(self, tmp_path):
        """Test returns None for non-directory path."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("")
        result = find_readme(file_path)
        assert result is None


class TestGetVisualMetaphor:
    """Test get_visual_metaphor function."""

    def test_nodejs_metaphor(self):
        """Test Node.js visual metaphor."""
        metaphor = get_visual_metaphor("nodejs")
        assert "interface" in metaphor.lower() or "web" in metaphor.lower()

    def test_python_metaphor(self):
        """Test Python visual metaphor."""
        metaphor = get_visual_metaphor("python")
        assert len(metaphor) > 0

    def test_rust_metaphor(self):
        """Test Rust visual metaphor."""
        metaphor = get_visual_metaphor("rust")
        assert len(metaphor) > 0

    def test_unknown_uses_default(self):
        """Test unknown type uses default metaphor."""
        metaphor = get_visual_metaphor("unknown")
        assert len(metaphor) > 0  # Any non-empty metaphor is acceptable
