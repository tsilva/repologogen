"""Fixed application entrypoint inside the Agent Vault OS sandbox."""

import importlib.util
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "vault_guard", Path(__file__).with_name("agentbridge_guard.py")
)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
guard.install()
sys.path.insert(0, str(ROOT / "src" if (ROOT / "src").is_dir() else ROOT))


def catalog():
    req = urllib.request.Request(
        guard.BASE + "/models", headers={"Authorization": "Bearer " + guard.MARKER}
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        body = json.load(response)
    rows = body.get("data")
    if not isinstance(rows, list):
        raise ValueError("Invalid model catalog")
    print(
        json.dumps(
            {
                "ok": True,
                "read_only": True,
                "credential_mode": "public-placeholder",
                "model_count": len(rows),
            }
        )
    )


def main():
    if sys.argv[1:] == ["check"]:
        catalog()
        return
    if sys.argv[1:2] != ["run"]:
        raise ValueError("Use the reviewed vault launcher")
    arguments = sys.argv[2:]
    if ROOT.name == "runbook":
        # Import only the planner. Never import/launch the Modal execution CLI.
        import argparse

        from runbook.requirements_plan import (
            generate_requirements,
            requirements_to_dict,
        )

        parser = argparse.ArgumentParser(
            description="Plan notebook requirements without executing the notebook"
        )
        parser.add_argument("notebook", type=Path)
        opts = parser.parse_args(arguments)
        plan = generate_requirements(opts.notebook.read_text(), api_key=guard.MARKER)
        target = Path.cwd() / (opts.notebook.name + ".yaml")
        import yaml

        target.write_text(yaml.safe_dump(requirements_to_dict(plan), sort_keys=False))
        print(
            json.dumps(
                {
                    "ok": True,
                    "planned_only": True,
                    "notebook_executed": False,
                    "output": target.name,
                }
            )
        )
        return
    modules = {
        "repologogen": "repologogen.cli",
        "parsehealthlog": "parsehealthlog.main",
        "paperclean-cli": "paperclean.cli",
        "parselabs": "parselabs.cli",
        "parsemedicalexams": "parsemedicalexams.cli",
    }
    if ROOT.name == "parsehealthlog":
        import parsehealthlog.config

        def accessible(_url, timeout=10):
            req = urllib.request.Request(
                guard.BASE + "/models",
                headers={"Authorization": "Bearer " + guard.MARKER},
            )
            with urllib.request.urlopen(req, timeout=timeout):
                return True

        parsehealthlog.config.check_api_accessibility = accessible
    sys.argv = [modules[ROOT.name], *arguments]
    import importlib

    raise SystemExit(importlib.import_module(modules[ROOT.name]).main())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(
            json.dumps(
                {
                    "ok": False,
                    "reason": "Vault client failed; provider diagnostics withheld",
                }
            )
        )
        sys.exit(1)
