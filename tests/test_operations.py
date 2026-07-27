import pytest

from substance_painter_mcp.operations import PainterOperations


class FakeRemote:
    def __init__(self, response=None):
        self.response = response or {"success": True, "data": {"uid": 7}}
        self.calls = []

    def execute_python_json(self, code, params=None):
        self.calls.append((code, params))
        return self.response


def test_create_fill_transports_values_as_params():
    remote = FakeRemote()
    result = PainterOperations(remote).create_fill_layer(
        "quoted ' layer", texture_set="Body", base_color=[0.1, 0.2, 0.3]
    )
    assert result == {"uid": 7}
    _, params = remote.calls[0]
    assert params == {
        "name": "quoted ' layer",
        "texture_set": "Body",
        "base_color": [0.1, 0.2, 0.3],
    }


@pytest.mark.parametrize(
    "color",
    ([0, 0], [0, 0, 2], [0, "bad", 1]),
)
def test_color_validation_rejects_invalid_values(color):
    with pytest.raises(ValueError):
        PainterOperations(FakeRemote()).set_fill_base_color(1, color)


def test_painter_error_envelope_is_raised():
    remote = FakeRemote({"success": False, "error_type": "ValueError", "error": "missing"})
    with pytest.raises(RuntimeError, match="ValueError: missing"):
        PainterOperations(remote).delete_layer(99)


def test_layer_property_validation_is_local():
    remote = FakeRemote()
    with pytest.raises(ValueError, match="opacity"):
        PainterOperations(remote).set_layer_properties(1, opacity=1.1)
    assert remote.calls == []


def test_selection_requires_at_least_one_uid():
    with pytest.raises(ValueError, match="at least one"):
        PainterOperations(FakeRemote()).select_layers([])


def test_fill_channels_normalizes_scalar_values():
    remote = FakeRemote()
    PainterOperations(remote).set_fill_channels(3, {"Roughness": 0.4})
    assert remote.calls[0][1] == {"uid": 3, "values": {"Roughness": [0.4, 0.4, 0.4]}}


def test_resource_search_validates_query_and_limit():
    operations = PainterOperations(FakeRemote())
    with pytest.raises(ValueError, match="empty"):
        operations.search_resources("   ")
    with pytest.raises(ValueError, match="1..200"):
        operations.search_resources("wood", 0)


def test_export_requires_configured_root(monkeypatch, tmp_path):
    monkeypatch.delenv("SP_MCP_EXPORT_ROOTS", raising=False)
    with pytest.raises(PermissionError, match="disabled"):
        PainterOperations(FakeRemote()).plan_texture_export(str(tmp_path), "preset")


def test_export_rejects_path_outside_root(monkeypatch, tmp_path):
    allowed = tmp_path / "allowed"
    monkeypatch.setenv("SP_MCP_EXPORT_ROOTS", str(allowed))
    with pytest.raises(PermissionError, match="outside"):
        PainterOperations(FakeRemote()).plan_texture_export(str(tmp_path / "elsewhere"), "preset")
