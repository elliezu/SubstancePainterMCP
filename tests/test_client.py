import json

import pytest

from substance_painter_mcp.client import (
    PainterConnectionError,
    PainterRemote,
    PainterRemoteConfig,
    PainterScriptError,
)


class FakeResponse:
    def __init__(self, payload: bytes, status: int = 200):
        self.payload = payload
        self.status = status

    def read(self):
        return self.payload


class FakeConnection:
    response = FakeResponse(b"null")
    request_args = None

    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout

    def request(self, *args, **kwargs):
        type(self).request_args = (args, kwargs)

    def getresponse(self):
        return type(self).response

    def close(self):
        pass


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("SP_MCP_HOST", "::1")
    monkeypatch.setenv("SP_MCP_PORT", "61234")
    monkeypatch.setenv("SP_MCP_TIMEOUT", "2.5")
    assert PainterRemoteConfig.from_env() == PainterRemoteConfig("::1", 61234, 2.5)


def test_request_encodes_script(monkeypatch):
    monkeypatch.setattr("http.client.HTTPConnection", FakeConnection)
    FakeConnection.response = FakeResponse(b'"12.1.1"')
    remote = PainterRemote(PainterRemoteConfig(timeout_seconds=3))
    assert remote.execute_js("alg.version.painter") == "12.1.1"
    args, kwargs = FakeConnection.request_args
    assert args[0] == "POST"
    body = json.loads(kwargs["body"])
    assert set(body) == {"js"}


def test_script_error_is_typed(monkeypatch):
    monkeypatch.setattr("http.client.HTTPConnection", FakeConnection)
    FakeConnection.response = FakeResponse(b'{"error":"bad script"}')
    with pytest.raises(PainterScriptError, match="bad script"):
        PainterRemote().execute_python("broken")


def test_connection_error_is_fast_and_actionable(monkeypatch):
    class RefusingConnection(FakeConnection):
        def request(self, *args, **kwargs):
            raise ConnectionRefusedError

    monkeypatch.setattr("http.client.HTTPConnection", RefusingConnection)
    with pytest.raises(PainterConnectionError, match="enable-remote-scripting"):
        PainterRemote().check_connection()


def test_json_wrapper_does_not_interpolate_params():
    class CapturingRemote(PainterRemote):
        captured = ""

        def execute_python(self, code):
            self.captured = code
            return '{"success": true, "data": "ok"}'

    remote = CapturingRemote()
    dangerous = "name'); raise RuntimeError('injected') #"
    result = remote.execute_python_json("result = params['name']", {"name": dangerous})
    assert result["data"] == "ok"
    assert dangerous not in remote.captured
