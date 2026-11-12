"""Request guard loaded only by the opt-in, sandboxed Agent Vault entrypoint."""

import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

MARKER = "agentbridge_public_placeholder"
BASE = "http://127.0.0.1:8082/api/v1"
FAILED = False


class VaultPolicyError(RuntimeError):
    """A sanitized error without provider response content."""


def validate(method, url, headers):
    if FAILED:
        raise VaultPolicyError("The vault session stopped after a request failure")
    parsed = urllib.parse.urlsplit(str(url))
    if parsed.scheme != "http" or parsed.netloc != "127.0.0.1:8082":
        raise VaultPolicyError("Unreviewed destination rejected")
    if parsed.query or parsed.fragment or "%" in parsed.path:
        raise VaultPolicyError("Unreviewed URL parameters rejected")
    routes = {("GET", "/api/v1/models"), ("POST", "/api/v1/chat/completions")}
    if Path(__file__).resolve().parents[2].name == "paperclean-cli":
        routes |= {
            ("GET", "/api/v1/capabilities"),
            ("POST", "/api/v1/images"),
            ("GET", "/api/v1/openrouter/credits"),
            ("GET", "/api/v1/openrouter/key"),
            ("GET", "/api/v1/openrouter/endpoints/zdr"),
        }
        if method.upper() == "GET" and re.fullmatch(
            r"/api/v1/openrouter/(images/)?models/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/endpoints",
            parsed.path,
        ):
            routes.add(("GET", parsed.path))
    if (method.upper(), parsed.path) not in routes:
        raise VaultPolicyError("Unreviewed method or route rejected")
    normalized = {str(k).lower(): str(v) for k, v in headers.items()}
    if normalized.get("authorization") != "Bearer " + MARKER:
        raise VaultPolicyError("Expected public placeholder is missing")
    if any(k in normalized for k in ("api-key", "x-api-key", "cookie")):
        raise VaultPolicyError("Additional authentication rejected")


def install():
    if os.environ.get("AGENTBRIDGE_API_KEY") != MARKER:
        raise VaultPolicyError("Expected public placeholder is missing")
    if os.environ.get("AGENTBRIDGE_BASE_URL") != BASE:
        raise VaultPolicyError("Reviewed gateway mapping is required")
    proxy = urllib.parse.urlsplit(os.environ.get("HTTP_PROXY", ""))
    if proxy.scheme != "http" or proxy.hostname != "127.0.0.1" or proxy.port != 8283:
        raise VaultPolicyError("Reviewed scoped proxy is required")
    if os.environ.get("NO_PROXY") or os.environ.get("no_proxy"):
        raise VaultPolicyError("Proxy bypass rejected")
    original = urllib.request.OpenerDirector.open

    def guarded_open(self, fullurl, data=None, timeout=60):
        global FAILED
        req = (
            fullurl
            if isinstance(fullurl, urllib.request.Request)
            else urllib.request.Request(fullurl, data=data)
        )
        validate(req.get_method(), req.full_url, dict(req.header_items()))
        try:
            result = original(self, req, data, timeout)
            if not 200 <= result.status < 300:
                result.close()
                raise VaultPolicyError("Gateway request failed; details withheld")
            return result
        except Exception:
            FAILED = True
            raise VaultPolicyError("Gateway request failed; details withheld") from None

    urllib.request.OpenerDirector.open = guarded_open

    def no_redirect(*_args, **_kwargs):
        raise VaultPolicyError("Redirect rejected")

    urllib.request.HTTPRedirectHandler.redirect_request = no_redirect
    try:
        import httpx
    except ImportError:
        httpx = None
    if httpx:
        send = httpx.Client.send
        async_send = httpx.AsyncClient.send

        def guarded_send(self, request, **kwargs):
            global FAILED
            validate(request.method, request.url, request.headers)
            if request.method == "GET" and request.url.path.startswith(
                "/api/v1/openrouter/"
            ):
                # A separate GET-only service prevents this metadata route granting POST /keys.
                request.url = request.url.copy_with(host="localhost")
            kwargs["follow_redirects"] = False
            try:
                response = send(self, request, **kwargs)
                if not 200 <= response.status_code < 300:
                    response.close()
                    raise VaultPolicyError("Gateway request failed; details withheld")
                return response
            except Exception:
                FAILED = True
                raise VaultPolicyError(
                    "Gateway request failed; details withheld"
                ) from None

        async def guarded_async_send(self, request, **kwargs):
            global FAILED
            validate(request.method, request.url, request.headers)
            kwargs["follow_redirects"] = False
            try:
                response = await async_send(self, request, **kwargs)
                if not 200 <= response.status_code < 300:
                    await response.aclose()
                    raise VaultPolicyError("Gateway request failed; details withheld")
                return response
            except Exception:
                FAILED = True
                raise VaultPolicyError(
                    "Gateway request failed; details withheld"
                ) from None

        httpx.Client.send = guarded_send
        httpx.AsyncClient.send = guarded_async_send
    try:
        import openai
    except ImportError:
        openai = None
    if openai:
        for cls in (openai.OpenAI, openai.AsyncOpenAI):
            constructor = cls.__init__

            def init(self, *args, _constructor=constructor, **kwargs):
                kwargs["max_retries"] = 0
                _constructor(self, *args, **kwargs)

            cls.__init__ = init
    try:
        import dotenv
    except ImportError:
        pass
    else:
        dotenv.load_dotenv = lambda *_args, **_kwargs: False
