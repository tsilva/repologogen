"""Offline regression tests for the opt-in vault request boundary."""

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "scripts/infisical" / (name + ".py")
    )
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class VaultTests(unittest.TestCase):
    def setUp(self):
        self.guard = module("agentbridge_guard")
        self.headers = {"Authorization": "Bearer " + self.guard.MARKER}

    def test_expected_routes(self):
        self.guard.validate("GET", self.guard.BASE + "/models", self.headers)
        self.guard.validate("POST", self.guard.BASE + "/chat/completions", self.headers)

    def test_unreviewed_requests_rejected(self):
        for method, url in [
            ("GET", "https://example.com/api/v1/models"),
            ("POST", self.guard.BASE + "/keys"),
            ("DELETE", self.guard.BASE + "/models"),
            ("GET", self.guard.BASE + "/models?token=x"),
            ("GET", self.guard.BASE + "/models%2f..%2fkeys"),
        ]:
            with (
                self.subTest(method=method, url=url),
                self.assertRaises(self.guard.VaultPolicyError),
            ):
                self.guard.validate(method, url, self.headers)

    def test_credentials_rejected(self):
        for headers in [
            {},
            {"Authorization": "Bearer synthetic-unreviewed-key"},
            {**self.headers, "Cookie": "synthetic"},
            {**self.headers, "X-API-Key": "synthetic"},
        ]:
            with (
                self.subTest(headers=list(headers)),
                self.assertRaises(self.guard.VaultPolicyError),
            ):
                self.guard.validate("GET", self.guard.BASE + "/models", headers)

    def test_no_fallback_after_failure(self):
        self.guard.FAILED = True
        with self.assertRaises(self.guard.VaultPolicyError):
            self.guard.validate("GET", self.guard.BASE + "/models", self.headers)

    def test_install_requires_placeholder(self):
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            self.assertRaises(self.guard.VaultPolicyError),
        ):
            self.guard.install()

    def test_missing_protected_binding_fails(self):
        launcher = module("agentbridge_vault")
        with (
            mock.patch.object(
                Path, "home", return_value=ROOT / "nonexistent-synthetic-home"
            ),
            self.assertRaises(FileNotFoundError),
        ):
            launcher.load_profile()

    def test_workspace_override_cannot_broaden_filesystem_access(self):
        launcher = module("agentbridge_vault")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "repo"
            allowed = root / ".internal/agent-vault/work"
            allowed.mkdir(parents=True)
            outside = root.parent / "unreviewed"
            outside.mkdir()
            with mock.patch.object(launcher, "ROOT", root):
                self.assertEqual(launcher.validate_workspace(allowed), allowed)
                with self.assertRaises(ValueError):
                    launcher.validate_workspace(outside)

    def test_httpx_provider_error_body_is_hidden(self):
        try:
            import httpx
        except ImportError:
            self.skipTest("HTTPX is available in the reviewed runtime")
        import urllib.request

        originals = [
            (httpx.Client, "send", httpx.Client.send),
            (httpx.AsyncClient, "send", httpx.AsyncClient.send),
            (urllib.request.OpenerDirector, "open", urllib.request.OpenerDirector.open),
            (
                urllib.request.HTTPRedirectHandler,
                "redirect_request",
                urllib.request.HTTPRedirectHandler.redirect_request,
            ),
        ]
        try:
            import openai
        except ImportError:
            pass
        else:
            originals.extend(
                [
                    (openai.OpenAI, "__init__", openai.OpenAI.__init__),
                    (openai.AsyncOpenAI, "__init__", openai.AsyncOpenAI.__init__),
                ]
            )
        try:
            import dotenv
        except ImportError:
            pass
        else:
            originals.append((dotenv, "load_dotenv", dotenv.load_dotenv))
        reflected = "synthetic-upstream-key"

        def response(_self, request, **_kwargs):
            return httpx.Response(401, text=reflected, request=request)

        env = {
            "AGENTBRIDGE_API_KEY": self.guard.MARKER,
            "AGENTBRIDGE_BASE_URL": self.guard.BASE,
            "HTTP_PROXY": "http://synthetic:session@127.0.0.1:8283",
            "NO_PROXY": "",
            "no_proxy": "",
        }
        try:
            httpx.Client.send = response
            with mock.patch.dict(os.environ, env, clear=True):
                self.guard.install()
                with (
                    httpx.Client(trust_env=False) as client,
                    self.assertRaises(self.guard.VaultPolicyError) as error,
                ):
                    client.get(self.guard.BASE + "/models", headers=self.headers)
                self.assertNotIn(reflected, str(error.exception))
                self.assertTrue(self.guard.FAILED)
        finally:
            for owner, attribute, value in originals:
                setattr(owner, attribute, value)


if __name__ == "__main__":
    unittest.main()
