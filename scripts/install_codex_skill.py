#!/usr/bin/env python3
"""Install the repo-owned repologogen Codex skill into ~/.codex/skills."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_ID = "repologogen_generate-brand-assets"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_target_dir() -> Path:
    return Path.home() / ".codex" / "skills"


def install_skill(target_dir: Path, *, validate: bool = True) -> Path:
    repo_root = _repo_root()
    source_dir = repo_root / "skills" / SKILL_ID
    target_skill_dir = target_dir / SKILL_ID

    if not (source_dir / "SKILL.md").exists():
        raise FileNotFoundError(f"Missing skill source: {source_dir / 'SKILL.md'}")

    if validate:
        source = (source_dir / "SKILL.md").read_text(encoding="utf-8")
        header = re.match(r"\A---\n(.*?)\n---(?:\n|\Z)", source, re.DOTALL)
        name_line = f"name: {SKILL_ID}"
        if header is None or header[1].splitlines().count(name_line) != 1:
            raise ValueError(f"Expected {name_line} in the skill frontmatter")
        validator = (
            Path.home()
            / ".codex"
            / "skills"
            / ".system"
            / "skill-creator"
            / "scripts"
            / "quick_validate.py"
        )
        if validator.exists():
            # The bundled validator requires hyphens. Validate a temporary
            # copy while preserving the actual invocation ID in the install.
            normalized_id = SKILL_ID.replace("_", "-")
            normalized_header = header[1].replace(name_line, f"name: {normalized_id}", 1)
            normalized = source[:header.start(1)] + normalized_header + source[header.end(1):]
            with tempfile.TemporaryDirectory(prefix="repologogen-skill-validation-") as tmp:
                validation_dir = Path(tmp) / normalized_id
                validation_dir.mkdir()
                (validation_dir / "SKILL.md").write_text(normalized, encoding="utf-8")
                subprocess.run([sys.executable, str(validator), str(validation_dir)], check=True)

    target_dir.mkdir(parents=True, exist_ok=True)
    if target_skill_dir.exists():
        shutil.rmtree(target_skill_dir)
    shutil.copytree(source_dir, target_skill_dir)

    return target_skill_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description=f"Install the {SKILL_ID} Codex skill into a Codex skills directory.",
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=_default_target_dir(),
        help="Codex skills directory (default: ~/.codex/skills)",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip validation with quick_validate.py after install",
    )
    args = parser.parse_args()

    installed_path = install_skill(args.target_dir, validate=not args.no_validate)
    print(installed_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
