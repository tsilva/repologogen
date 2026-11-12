"""Black-box macOS regression for credential-file read denial."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(sys.platform == "darwin", "Requires the native macOS sandbox")
class SandboxFileReadTests(unittest.TestCase):
    def test_credential_files_are_denied_but_source_files_are_readable(self):
        policy = Path(__file__).resolve().parents[1] / "scripts/infisical/agentbridge_python.sb"
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary).resolve()
            repo = home / "repo"
            workspace = repo / ".internal/work"
            workspace.mkdir(parents=True)
            values = {
                "USER_HOME": str(home), "REPO_ROOT": str(repo),
                "WORKSPACE": str(workspace), "PYTHON_ROOT": "/usr",
                "VENV_ROOT": str(repo / "venv"), "PYTHON_BIN": "/bin/cat",
                "PYTHON_REAL": "/bin/cat", "CA_FILE": str(home / "ca.pem"),
            }
            command = ["/usr/bin/sandbox-exec"]
            for name, value in values.items():
                command += ["-D", name + "=" + value]
            command += ["-f", str(policy), "/bin/cat"]
            public = repo / "source.txt"
            public.write_text("synthetic public fixture")
            control = subprocess.run(command + [str(public)], capture_output=True, timeout=5)
            self.assertEqual(control.returncode, 0)
            self.assertEqual(control.stdout, b"synthetic public fixture")
            protected = [repo / name for name in
                         (".env", ".env.local", ".env.production.local", ".netrc", ".access.local.toml")]
            protected.append(workspace / ".env")
            for path in protected:
                with self.subTest(file=path.name):
                    path.write_text("synthetic private fixture")
                    result = subprocess.run(command + [str(path)], capture_output=True, timeout=5)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, b"")
