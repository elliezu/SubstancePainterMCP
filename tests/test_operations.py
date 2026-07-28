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


def test_resource_search_transports_server_side_filters():
    remote = FakeRemote()
    PainterOperations(remote).search_resources(
        "wood", limit=12, resource_type="Substance", usage="Generator"
    )
    assert remote.calls[0][1] == {
        "query": "wood",
        "limit": 12,
        "resource_type": "Substance",
        "usage": "Generator",
    }


def test_active_channels_rejects_empty_or_duplicate_values():
    operations = PainterOperations(FakeRemote())
    with pytest.raises(ValueError, match="at least one"):
        operations.set_active_channels(1, [])
    with pytest.raises(ValueError, match="duplicates"):
        operations.set_active_channels(1, ["BaseColor", "BaseColor"])


def test_active_channels_transports_uid_and_names():
    remote = FakeRemote()
    PainterOperations(remote).set_active_channels(4, ["BaseColor", "Roughness"])
    assert remote.calls[0][1] == {
        "uid": 4,
        "channels": ["BaseColor", "Roughness"],
    }


def test_layer_recipe_normalizes_scalar_channels():
    remote = FakeRemote()
    recipe = [
        {
            "type": "group",
            "name": "Look",
            "children": [
                {"type": "fill", "name": "Rough", "channels": {"Roughness": 0.25}}
            ],
        }
    ]
    PainterOperations(remote).create_layer_recipe(recipe)
    assert remote.calls[0][1]["recipe"][0]["children"][0]["channels"] == {
        "Roughness": [0.25, 0.25, 0.25]
    }


def test_layer_recipe_rejects_children_on_non_group():
    recipe = [
        {"type": "fill", "name": "Invalid", "children": [{"type": "paint", "name": "P"}]}
    ]
    with pytest.raises(ValueError, match="only group"):
        PainterOperations(FakeRemote()).create_layer_recipe(recipe)


def test_snapshot_adds_deterministic_digest():
    payload = {"texture_set": "Body", "stack": "Body", "layers": []}
    result = PainterOperations(FakeRemote({"success": True, "data": payload})).snapshot_layer_tree()
    assert result["texture_set"] == "Body"
    assert len(result["sha256"]) == 64


def test_save_project_copy_requires_configured_root(monkeypatch, tmp_path):
    monkeypatch.delenv("SP_MCP_PROJECT_ROOTS", raising=False)
    with pytest.raises(PermissionError, match="disabled"):
        PainterOperations(FakeRemote()).save_project_copy(str(tmp_path / "copy.spp"))


def test_save_project_copy_requires_spp_extension(monkeypatch, tmp_path):
    monkeypatch.setenv("SP_MCP_PROJECT_ROOTS", str(tmp_path))
    with pytest.raises(ValueError, match=".spp"):
        PainterOperations(FakeRemote()).save_project_copy(str(tmp_path / "copy.zip"))


def test_smart_asset_rejects_unsafe_name(monkeypatch, tmp_path):
    monkeypatch.setenv("SP_MCP_EXPORT_ROOTS", str(tmp_path))
    with pytest.raises(ValueError, match="file name"):
        PainterOperations(FakeRemote()).export_smart_material(
            1, "../escape", str(tmp_path)
        )


def test_unknown_export_profile_is_rejected():
    with pytest.raises(ValueError, match="Unknown export profile"):
        PainterOperations(FakeRemote()).plan_profile_export("C:/exports", "missing")


def test_export_requires_configured_root(monkeypatch, tmp_path):
    monkeypatch.delenv("SP_MCP_EXPORT_ROOTS", raising=False)
    with pytest.raises(PermissionError, match="disabled"):
        PainterOperations(FakeRemote()).plan_texture_export(str(tmp_path), "preset")


def test_export_rejects_path_outside_root(monkeypatch, tmp_path):
    allowed = tmp_path / "allowed"
    monkeypatch.setenv("SP_MCP_EXPORT_ROOTS", str(allowed))
    with pytest.raises(PermissionError, match="outside"):
        PainterOperations(FakeRemote()).plan_texture_export(str(tmp_path / "elsewhere"), "preset")
