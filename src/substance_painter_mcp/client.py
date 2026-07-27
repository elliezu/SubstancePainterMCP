"""HTTP client for Substance 3D Painter's remote scripting endpoint."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import http.client
import json
import os
from typing import Any, Literal


Language = Literal["js", "python"]


class PainterRemoteError(RuntimeError):
    """Base error raised by the Painter remote client."""


class PainterConnectionError(PainterRemoteError):
    """Painter is not listening on the configured remote scripting port."""


class PainterHTTPError(PainterRemoteError):
    """Painter returned an unexpected HTTP response."""


class PainterScriptError(PainterRemoteError):
    """Painter rejected or failed to execute a script."""


@dataclass(frozen=True, slots=True)
class PainterRemoteConfig:
    host: str = "localhost"
    port: int = 60041
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> "PainterRemoteConfig":
        return cls(
            host=os.getenv("SP_MCP_HOST", "localhost"),
            port=int(os.getenv("SP_MCP_PORT", "60041")),
            timeout_seconds=float(os.getenv("SP_MCP_TIMEOUT", "30")),
        )


class PainterRemote:
    """Small, typed client for Painter's ``/run.json`` endpoint."""

    route = "/run.json"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    def __init__(self, config: PainterRemoteConfig | None = None):
        self.config = config or PainterRemoteConfig.from_env()

    def check_connection(self) -> str:
        """Return the Painter application version or raise a useful error."""
        return str(self.execute_js("alg.version.painter"))

    def execute_python(self, code: str) -> Any:
        return self._send_request(code, "python")

    def execute_js(self, code: str) -> Any:
        return self._send_request(code, "js")

    def execute_python_json(
        self,
        code: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run statements in an isolated namespace and return a JSON envelope.

        ``code`` may read the JSON-compatible ``params`` mapping and assign its
        return value to ``result``. Values are transported as base64 JSON instead
        of interpolated into Python source, preventing quoting/code-injection bugs.
        """
        code_b64 = base64.b64encode(code.encode("utf-8")).decode("ascii")
        params_json = json.dumps(params or {}, ensure_ascii=False)
        params_b64 = base64.b64encode(params_json.encode("utf-8")).decode("ascii")
        # Painter only returns a value when the whole payload is an expression.
        # A lambda keeps execution and serialization in one isolated expression,
        # avoiding fixed result files and shared global state.
        wrapper = (
            "(lambda _ns: ("
            f"exec(compile(__import__('base64').b64decode('{code_b64}').decode('utf-8'), "
            "'<substance-painter-mcp>', 'exec'), _ns, _ns), "
            "__import__('json').dumps({'success': True, 'data': _ns.get('result')}, "
            "ensure_ascii=False, default=str))[1])"
            f"({{'params': __import__('json').loads(__import__('base64').b64decode('{params_b64}').decode('utf-8'))}})"
        )
        raw = self.execute_python(wrapper)
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise PainterScriptError(f"Painter returned invalid JSON: {raw!r}") from exc
        if not isinstance(raw, dict) or "success" not in raw:
            raise PainterScriptError(f"Painter returned an invalid result envelope: {raw!r}")
        return raw

    def _send_request(self, code: str, language: Language) -> Any:
        encoded = base64.b64encode(code.encode("utf-8")).decode("ascii")
        body = json.dumps({language: encoded}).encode("utf-8")
        connection = http.client.HTTPConnection(
            self.config.host,
            self.config.port,
            timeout=self.config.timeout_seconds,
        )
        try:
            connection.request("POST", self.route, body=body, headers=self.headers)
            response = connection.getresponse()
            payload = response.read()
        except (ConnectionError, OSError, TimeoutError) as exc:
            raise PainterConnectionError(
                f"Cannot connect to Painter at {self.config.host}:{self.config.port}. "
                "Start Painter with --enable-remote-scripting."
            ) from exc
        finally:
            connection.close()

        text = payload.decode("utf-8", errors="replace").strip()
        if not 200 <= response.status < 300:
            raise PainterHTTPError(f"Painter HTTP {response.status}: {text or '<empty>'}")
        if not text:
            return None

        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            result = text
        if isinstance(result, dict) and "error" in result:
            raise PainterScriptError(str(result["error"]))
        return result
