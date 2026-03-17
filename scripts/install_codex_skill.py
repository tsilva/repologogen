#!/usr/bin/env python3
"""Install the repo-owned repologogen Codex skill into ~/.codex/skills."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_target_dir() -> Path:
    return Path.home() / ".codex" / "skills"


def install_skill(target_dir: Path, *, validate: bool = True) -> Path:
    repo_root = _repo_root()
    source_dir = repo_root / "skills" / "repologogen"
    target_skill_dir = target_dir / "repologogen"

    if not (source_dir / "SKILL.md").exists():
        raise FileNotFoundError(f"Missing skill source: {source_dir / 'SKILL.md'}")

    target_dir.mkdir(parents=True, exist_ok=True)
    if target_skill_dir.exists():
        shutil.rmtree(target_skill_dir)
    shutil.copytree(source_dir, target_skill_dir)

    if validate:
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
            subprocess.run(
                [sys.executable, str(validator), str(target_skill_dir)],
                check=True,
            )

    return target_skill_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install the repologogen Codex skill into a Codex skills directory.",
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
