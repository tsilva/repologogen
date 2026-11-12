"""Credential-free validation of the opt-in Python launcher and its protected pins."""

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "vault", Path(__file__).parents[1] / "scripts/infisical/agentbridge_vault.py"
)
vault = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vault)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ProfileTests(unittest.TestCase):
    def test_exact_source_runtime_identity_and_ownership_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory).resolve()
            root = home / ROOT.name
            root.mkdir()
            prefix = home / ".config/infisical"
            target = prefix / "agentbridge-python/profiles" / (ROOT.name + ".json")
            target.parent.mkdir(parents=True, mode=0o700)
            venv = prefix / "agentbridge-python/runtimes" / ROOT.name
            real = home / "trusted-python/bin/python3.11"
            real.parent.mkdir(parents=True)
            real.write_text("synthetic runtime fixture")
            (venv / "bin").mkdir(parents=True)
            (venv / "bin/python").symlink_to(real)
            cli = prefix / "cli/0.45.6/infisical"
            cli.parent.mkdir(parents=True)
            cli.write_text("synthetic CLI fixture")
            ca = prefix / "agent-vault-ca.pem"
            ca.write_text("synthetic public CA fixture")
            native = {
                "version": 1,
                "general": {"domain": vault.DOMAIN},
                "secrets-management": {
                    "project-id": "68f682cd-f379-40cc-af36-1b9747da4ad2",
                    "environment": "dev",
                    "secret-path": "/agents/agentbridge",
                },
            }
            (root / ".infisical.yaml").write_text(json.dumps(native))
            package = root / vault.PACKAGE
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("synthetic module")
            with patch.object(vault, "ROOT", root):
                expected_sources = vault.source_files()
            for name in expected_sources:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("synthetic source fixture: " + name)
            profile = {
                "version": 1,
                "repository": ROOT.name,
                "repo_path": str(root),
                "bundle": "local-" + ROOT.name + "-agentbridge",
                "native_sha256": sha(root / ".infisical.yaml"),
                "project_id": native["secrets-management"]["project-id"],
                "python": str(venv / "bin/python"),
                "python_root": str(real.parent.parent),
                "venv": str(venv),
                "infisical": str(cli),
                "ca_file": str(ca),
                "ca_fingerprint": vault.FINGERPRINT,
                "code_sha256": {
                    name: sha(root / name) for name in expected_sources
                },
                "runtime_sha256": {
                    "python": sha(real),
                    "infisical": sha(cli),
                    "ca_file": sha(ca),
                },
            }

            def write(value):
                target.write_text(json.dumps(value))
                target.chmod(0o600)

            with (
                patch.object(vault, "ROOT", root),
                patch.object(vault.Path, "home", return_value=home),
            ):
                write(profile)
                self.assertEqual(vault.load_profile()["repository"], ROOT.name)
                mutations = [
                    {"version": True},
                    {"extra": "unreviewed"},
                    {"bundle": "other"},
                    {"infisical": "/bin/sh"},
                    {"code_sha256": {}},
                    {"code_sha256": {**profile["code_sha256"], "../escape": "0" * 64}},
                    {"native_sha256": "0" * 64},
                    {"ca_fingerprint": "unreviewed"},
                ]
                mutations += [
                    {"code_sha256": {**profile["code_sha256"], name: "0" * 64}}
                    for name in expected_sources
                ]
                mutations += [
                    {"runtime_sha256": {**profile["runtime_sha256"], name: "0" * 64}}
                    for name in profile["runtime_sha256"]
                ]
                for mutation in mutations:
                    with self.subTest(fields=list(mutation)):
                        write({**profile, **mutation})
                        with self.assertRaises(ValueError):
                            vault.load_profile()
                write(profile)
                target.chmod(0o644)
                with self.assertRaises(ValueError):
                    vault.load_profile()
                write(profile)
                extra = package / "unreviewed.py"
                extra.write_text("unreviewed import")
                with self.assertRaises(ValueError):
                    vault.load_profile()
                extra.unlink()
                source = package / "__init__.py"
                original = source.read_text()
                source.unlink()
                source.symlink_to(real)
                with self.assertRaises(ValueError):
                    vault.load_profile()
                source.unlink()
                source.write_text(original)
                target.parent.chmod(0o755)
                with self.assertRaises(ValueError):
                    vault.load_profile()
                target.parent.chmod(0o700)
                (root / ".infisical.json").write_text("{}")
                with self.assertRaises(ValueError):
                    vault.load_profile()

    def test_native_command_keeps_project_and_sandbox_pinned(self):
        profile = {
            "python": "/trusted/venv/bin/python",
            "python_root": "/trusted/python",
            "venv": "/trusted/venv",
            "infisical": "/trusted/infisical",
            "ca_file": "/trusted/public.pem",
            "ca_fingerprint": vault.FINGERPRINT,
            "bundle": "reviewed",
        }
        for mode in ["check", "run"]:
            command = vault.command(profile, mode, Path("/synthetic/workspace"), [])
            self.assertIn("--project-id=5078c850-3f93-46d8-8afe-82107df8b931", command)
            self.assertIn("--domain=https://app.infisical.com", command)
            self.assertIn("--no-skills", command)
            self.assertIn("--no-ca-trust", command)
            self.assertIn("/usr/bin/sandbox-exec", command)
            self.assertIn("AGENTBRIDGE_API_KEY=agentbridge_public_placeholder", command)



if __name__ == "__main__":
    unittest.main()
