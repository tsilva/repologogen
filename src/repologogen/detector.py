"""Project type detection utilities."""

from pathlib import Path
from typing import Dict, List, Tuple

# Detection rules: (file patterns, project type, confidence)
DETECTION_RULES: List[Tuple[List[str], str, str]] = [
    (["package.json"], "nodejs", "high"),
    (["pyproject.toml"], "python", "high"),
    (["setup.py"], "python", "high"),
    (["requirements.txt"], "python", "medium"),
    (["Pipfile"], "python", "high"),
    (["Cargo.toml"], "rust", "high"),
    (["go.mod"], "go", "high"),
    (["pom.xml"], "java", "high"),
    (["build.gradle"], "java", "high"),
    (["build.gradle.kts"], "java", "high"),
    (["*.sln"], "dotnet", "high"),
    (["*.csproj"], "dotnet", "high"),
    (["Gemfile"], "ruby", "high"),
    (["composer.json"], "php", "high"),
    (["CMakeLists.txt"], "cpp", "high"),
]

# Visual metaphors by project type
VISUAL_METAPHORS: Dict[str, str] = {
    "cli": "Origami transformation, geometric terminal",
    "library": "Interconnected building blocks",
    "web": "Modern interface window",
    "api": "Messenger bird carrying data packet",
    "framework": "Architectural scaffold",
    "converter": "Metamorphosis symbol",
    "database": "Stacked cylinders, data nodes",
    "security": "Shield, lock, key",
}


def find_readme(path: Path) -> Path | None:
    """Find README.md in the project directory (case-insensitive).

    Args:
        path: Directory to search

    Returns:
        Path to README file, or None if not found
    """
    if not path.is_dir():
        return None
    for f in path.iterdir():
        if f.is_file() and f.name.lower() == "readme.md":
            return f
    return None


def glob_match(pattern: str, files: List[str]) -> List[str]:
    """Simple glob matching for *.ext patterns."""
    if pattern.startswith("*."):
        ext = pattern[1:]  # includes the dot
        return [f for f in files if f.endswith(ext)]
    return [f for f in files if f == pattern]


def detect_project(path: Path) -> Dict:
    """Detect project type from files in the given directory.

    Args:
        path: Directory to analyze

    Returns:
        Dictionary with type, confidence, and detected files
    """
    if not path.is_dir():
        return {
            "type": "unknown",
            "confidence": "none",
            "files": [],
            "error": f"Path is not a directory: {path}",
        }

    try:
        root_files = [f.name for f in path.iterdir() if f.is_file()]
    except PermissionError:
        return {
            "type": "unknown",
            "confidence": "none",
            "files": [],
            "error": f"Permission denied: {path}",
        }

    detected_files = []
    detected_type = "unknown"
    confidence = "none"

    for patterns, proj_type, conf in DETECTION_RULES:
        for pattern in patterns:
            matches = glob_match(pattern, root_files)
            if matches:
                detected_files.extend(matches)
                if detected_type == "unknown":
                    detected_type = proj_type
                    confidence = conf
                break

    # Deduplicate while preserving order
    seen = set()
    unique_files = []
    for f in detected_files:
        if f not in seen:
            seen.add(f)
            unique_files.append(f)

    return {"type": detected_type, "confidence": confidence, "files": unique_files}


def get_visual_metaphor(project_type: str) -> str:
    """Get visual metaphor for a project type.

    Args:
        project_type: Detected project type

    Returns:
        Visual metaphor description
    """
    # Map project types to metaphor categories
    type_mapping = {
        "nodejs": "web",
        "python": "library",
        "rust": "library",
        "go": "cli",
        "java": "library",
        "dotnet": "library",
        "ruby": "web",
        "php": "web",
        "cpp": "library",
    }

    category = type_mapping.get(project_type, "library")
    return VISUAL_METAPHORS.get(category, "Abstract geometric shape")
