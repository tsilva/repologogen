"""Trusted bootstrap for the repository's opt-in, sandboxed AI client."""

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOMAIN = "https://app.infisical.com"
MARKER = "agentbridge_public_placeholder"
BASE = "http://127.0.0.1:8082/api/v1"
PACKAGE = 'src/repologogen'


FINGERPRINT = (
    "SHA256:37:B2:E0:81:45:EC:C0:58:46:2E:D1:2F:E1:2B:E6:AE:"
    "2B:78:B1:B3:F0:21:CD:8F:EC:54:CC:30:2D:36:9E:37"
)


def source_files():
    package = ROOT / PACKAGE
    if package.resolve() != package or not package.is_dir():
        raise ValueError("The reviewed package directory changed")
    if any(path.is_symlink() for path in package.rglob("*")):
        raise ValueError("Symlinked package content requires trusted review")
    return {
        "scripts/infisical/" + name
        for name in (
            "agentbridge_vault.py", "agentbridge_guard.py",
            "agentbridge_entry.py", "agentbridge_python.sb",
        )
    } | {str(path.relative_to(ROOT)) for path in package.rglob("*.py")} | {
        "pyproject.toml", "uv.lock",
    }


def regular(path, private=False):
    if path.resolve() != path:
        raise ValueError("A canonical reviewed file is required")
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
        raise ValueError("A reviewed regular owner file is required")
    if private and info.st_mode & 0o077:
        raise ValueError("The protected profile must be owner-only")


def load_profile():
    path = (
        Path.home()
        / ".config/infisical/agentbridge-python/profiles"
        / (ROOT.name + ".json")
    )
    parent = path.parent.lstat()
    if (
        path.parent.resolve() != path.parent
        or not stat.S_ISDIR(parent.st_mode)
        or parent.st_uid != os.getuid()
        or parent.st_mode & 0o077
    ):
        raise ValueError("The profile directory must be canonical and owner-only")
    regular(path, True)
    p = json.loads(path.read_text())
    fields = {
        "version",
        "repository",
        "repo_path",
        "bundle",
        "native_sha256",
        "project_id",
        "python",
        "python_root",
        "venv",
        "infisical",
        "ca_file",
        "ca_fingerprint",
        "code_sha256",
        "runtime_sha256",
    }
    if set(p) != fields or type(p["version"]) is not int or p["version"] != 1:
        raise ValueError("Unsupported protected profile")
    if p["repository"] != ROOT.name or p["repo_path"] != str(ROOT):
        raise ValueError("Repository identity changed")
    if p["bundle"] != "local-" + ROOT.name + "-agentbridge":
        raise ValueError("Unreviewed bundle mapping")
    if (ROOT / ".infisical.json").exists():
        raise ValueError("Conflicting native identity requires trusted review")
    regular(ROOT / ".infisical.yaml")
    raw = (ROOT / ".infisical.yaml").read_bytes()
    if hashlib.sha256(raw).hexdigest() != p["native_sha256"]:
        raise ValueError("Native binding changed; trusted review is required")
    native = json.loads(raw)
    expected = {
        "version": 1,
        "general": {"domain": DOMAIN},
        "secrets-management": {
            "project-id": p["project_id"],
            "environment": "dev",
            "secret-path": "/agents/agentbridge",
        },
    }
    uuid.UUID(p["project_id"])
    if type(native.get("version")) is not int or native != expected:
        raise ValueError("Unreviewed native binding")
    if (
        not isinstance(p["code_sha256"], dict)
        or set(p["code_sha256"]) != source_files()
    ):
        raise ValueError("Incomplete reviewed source pins")
    for rel, digest in p["code_sha256"].items():
        regular(ROOT / rel)
        if hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() != digest:
            raise ValueError("Vault entrypoint changed; trusted review is required")
    prefix = Path.home() / ".config/infisical"
    if p["infisical"] != str(prefix / "cli/0.45.6/infisical") or p["ca_file"] != str(
        prefix / "agent-vault-ca.pem"
    ):
        raise ValueError("Unreviewed CLI or CA")
    if p["venv"] != str(prefix / "agentbridge-python/runtimes" / ROOT.name):
        raise ValueError("Unreviewed runtime")
    if p["python"] != str(Path(p["venv"]) / "bin/python"):
        raise ValueError("Unreviewed Python executable")
    for key in ("python", "infisical", "ca_file"):
        if not Path(p[key]).is_file():
            raise ValueError("A reviewed runtime, CLI or CA is unavailable")
    if p["ca_fingerprint"] != FINGERPRINT:
        raise ValueError("Unreviewed CA fingerprint")
    if Path(p["python"]).resolve() != Path(p["python_root"]) / "bin/python3.11":
        raise ValueError("Python executable target changed")
    if not isinstance(p["runtime_sha256"], dict) or set(p["runtime_sha256"]) != {
        "python",
        "infisical",
        "ca_file",
    }:
        raise ValueError("Incomplete reviewed runtime pins")
    for name, digest in p["runtime_sha256"].items():
        if hashlib.sha256(Path(p[name]).read_bytes()).hexdigest() != digest:
            raise ValueError("Runtime or public CA changed; trusted review required")
    return p


def command(p, mode, workspace, arguments):
    sandbox = ["/usr/bin/sandbox-exec"]
    values = {
        "USER_HOME": str(Path.home()),
        "REPO_ROOT": str(ROOT),
        "CA_FILE": p["ca_file"],
        "VENV_ROOT": p["venv"],
        "PYTHON_ROOT": p["python_root"],
        "PYTHON_BIN": p["python"],
        "PYTHON_REAL": str(Path(p["python"]).resolve()),
        "WORKSPACE": str(workspace),
    }
    for key, value in values.items():
        sandbox += ["-D", key + "=" + value]
    sandbox += ["-f", str(ROOT / "scripts/infisical/agentbridge_python.sb")]
    child = [
        p["python"],
        "-I",
        "-B",
        str(ROOT / "scripts/infisical/agentbridge_entry.py"),
        mode,
        *arguments,
    ]
    return [
        p["infisical"],
        "agent-vault",
        "run",
        "--domain=" + DOMAIN,
        "--project-id=5078c850-3f93-46d8-8afe-82107df8b931",
        "--access-bundle=" + p["bundle"],
        "--proxy=127.0.0.1:8283",
        "--ca-fingerprint=" + p["ca_fingerprint"],
        "--ttl=30m",
        "--no-ca-trust",
        "--silent",
        "--telemetry=false",
        "--no-skills",
        "--",
        "/usr/bin/env",
        "HOME=" + str(workspace / "home"),
        "AGENTBRIDGE_API_KEY=" + MARKER,
        "AGENTBRIDGE_BASE_URL=" + BASE,
        "NO_PROXY=",
        "no_proxy=",
        "SSL_CERT_FILE=" + p["ca_file"],
        "REQUESTS_CA_BUNDLE=" + p["ca_file"],
        "PYTHONDONTWRITEBYTECODE=1",
        "HF_HUB_DISABLE_IMPLICIT_TOKEN=1",
        *sandbox,
        *child,
    ]


def validate_workspace(path):
    workspace = path.absolute()
    allowed = ROOT / ".internal/agent-vault/work"
    if workspace != allowed and not workspace.is_relative_to(allowed):
        raise ValueError("Use only the repository's reviewed staging workspace")
    if (
        workspace.is_symlink()
        or workspace.resolve() != workspace
        or not workspace.is_dir()
    ):
        raise ValueError("Workspace must be an existing canonical directory")
    return workspace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["check", "run"])
    parser.add_argument(
        "--workspace",
        type=Path,
        required=True,
        help="Explicit non-secret input/output staging directory",
    )
    opts, rest = parser.parse_known_args()
    if opts.mode == "check" and rest:
        raise ValueError("The read-only check accepts no client overrides")
    if rest and rest[0] == "--":
        rest = rest[1:]
    p = load_profile()
    workspace = validate_workspace(opts.workspace)
    if (
        workspace.is_symlink()
        or workspace.resolve() != workspace
        or not workspace.is_dir()
    ):
        raise ValueError("Workspace must be an existing canonical directory")
    blocked = [
        Path.home() / x for x in (".config", ".ssh", ".codex", ".local", "Library")
    ]
    if workspace == Path.home() or any(
        workspace == x or workspace.is_relative_to(x) for x in blocked
    ):
        raise ValueError("Credential/application directories cannot be workspaces")
    if workspace == ROOT or ROOT.is_relative_to(workspace):
        raise ValueError("Use a dedicated staging directory")
    (workspace / "home").mkdir(mode=0o700, exist_ok=True)
    env = {
        "HOME": str(Path.home()),
        "PATH": "/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
    }
    os.chdir(workspace)
    if opts.mode == "run":
        os.execve(p["infisical"], command(p, "run", workspace, rest), env)
    result = subprocess.run(
        command(p, "check", workspace, []),
        env=env,
        capture_output=True,
        text=True,
        timeout=65,
    )
    records = [
        json.loads(s) for s in result.stdout.splitlines() if s.startswith('{"ok":')
    ]
    if not records:
        raise ValueError(
            "Vault check failed; login/profile/gateway diagnostics withheld"
        )
    print(json.dumps(records[-1]))
    return 0 if result.returncode == 0 and records[-1].get("ok") is True else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        print(
            json.dumps(
                {
                    "ok": False,
                    "reason": "Agent Vault failed; credential diagnostics withheld",
                }
            )
        )
        sys.exit(1)
