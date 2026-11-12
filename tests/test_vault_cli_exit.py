"""The real sandbox entrypoint must preserve the application's CLI exit status."""

import importlib.machinery
import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


class GuardLoader:
    def create_module(self, _spec):
        return None

    def exec_module(self, module):
        # Transport enforcement has its own native fake tests. This test isolates
        # the entrypoint's application/process boundary without making requests.
        module.install = lambda: None


class ExitStatusTests(unittest.TestCase):
    def entry(self):
        path = Path(__file__).resolve().parents[1] / "scripts/infisical/agentbridge_entry.py"
        spec = importlib.util.spec_from_file_location("entry_under_test", path)
        entry = importlib.util.module_from_spec(spec)
        guard_spec = importlib.machinery.ModuleSpec("synthetic_guard", GuardLoader())
        with (
            patch.object(importlib.util, "spec_from_file_location", return_value=guard_spec),
            patch.object(sys, "path", list(sys.path)),
        ):
            spec.loader.exec_module(entry)
        return entry

    def test_application_return_status_reaches_the_process_boundary(self):
        for code in [0, 1, 2, None]:
            with self.subTest(code=code):
                entry = self.entry()
                app = SimpleNamespace(main=lambda code=code: code)
                with (
                    patch.object(sys, "argv", ["entry", "run"]),
                    patch("importlib.import_module", return_value=app) as load,
                    self.assertRaises(SystemExit) as result,
                ):
                    entry.main()
                self.assertEqual(result.exception.code, code)
                load.assert_called_once_with("repologogen.cli")

    def test_application_system_exit_is_preserved(self):
        entry = self.entry()

        def fail():
            raise SystemExit(3)

        with (
            patch.object(sys, "argv", ["entry", "run"]),
            patch("importlib.import_module", return_value=SimpleNamespace(main=fail)),
            self.assertRaises(SystemExit) as result,
        ):
            entry.main()
        self.assertEqual(result.exception.code, 3)


if __name__ == "__main__":
    unittest.main()
