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
    class RecipeRemote(FakeRemote):
        def execute_python_json(self, code, params=None):
            self.calls.append((code, params))
            if "resolved_channels" in code:
                return {
                    "success": True,
                    "data": {
                        "texture_set": "Body",
                        "stack": "Body",
                        "resolved_channels": {"Roughness": "SpecularRoughness"},
                    },
                }
            if "geometry_mask" in code:
                return {
                    "success": True,
                    "data": {"texture_set": "Body", "stack": "Body", "layers": []},
                }
            return {"success": True, "data": {"created_count": 2, "nodes": []}}

    remote = RecipeRemote()
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
    create_call = next(call for call in remote.calls if "created_nodes" in call[0])
    assert create_call[1]["recipe"][0]["children"][0]["channels"] == {
        "Roughness": [0.25, 0.25, 0.25]
    }


def test_geometry_mask_validates_element_types_locally():
    operations = PainterOperations(FakeRemote())
    with pytest.raises(ValueError, match="mesh-name"):
        operations.set_geometry_mask(1, "Mesh", [1001])
    with pytest.raises(ValueError, match="UDIM"):
        operations.set_geometry_mask(1, "UVTile", ["1001"])
    with pytest.raises(ValueError, match="Mesh or UVTile"):
        operations.set_geometry_mask(1, "Polygon", [])


def test_fill_projection_validates_supported_transforms_locally():
    operations = PainterOperations(FakeRemote())
    with pytest.raises(ValueError, match="mode"):
        operations.set_fill_projection(1, "Spherical")
    with pytest.raises(ValueError, match="greater than zero"):
        operations.set_fill_projection(1, "UV", scale=[1, 0])
    with pytest.raises(ValueError, match="does not support offset"):
        operations.set_fill_projection(1, "Triplanar", offset=[0, 0])
    with pytest.raises(ValueError, match="does not accept"):
        operations.set_fill_projection(1, "Fill", rotation=10)


def test_smart_material_requires_resource_url():
    with pytest.raises(ValueError, match="resource://"):
        PainterOperations(FakeRemote()).insert_smart_material("https://example.com/material")


def test_snapshot_diff_reports_added_removed_and_changed_nodes():
    operations = PainterOperations(FakeRemote())
    before = {
        "sha256": "before",
        "layers": [
            {"uid": 1, "name": "Keep", "type": "FillLayerNode", "visible": True},
            {"uid": 2, "name": "Remove", "type": "PaintLayerNode", "visible": True},
        ],
    }
    after = {
        "sha256": "after",
        "layers": [
            {"uid": 1, "name": "Keep", "type": "FillLayerNode", "visible": False},
            {"uid": 3, "name": "Add", "type": "GroupLayerNode", "visible": True},
        ],
    }
    result = operations.diff_layer_snapshots(before, after)
    assert result["counts"] == {"added": 1, "removed": 1, "changed": 1}
    assert result["changed"][0]["fields"]["visible"] == {
        "before": True,
        "after": False,
    }


def test_layer_recipe_rejects_children_on_non_group():
    recipe = [
        {"type": "fill", "name": "Invalid", "children": [{"type": "paint", "name": "P"}]}
    ]
    with pytest.raises(ValueError, match="only group"):
        PainterOperations(FakeRemote()).create_layer_recipe(recipe)


def test_recipe_rolls_back_root_when_post_verification_fails():
    class FailingVerificationRemote(FakeRemote):
        def execute_python_json(self, code, params=None):
            self.calls.append((code, params))
            if "resolved_channels" in code:
                return {
                    "success": True,
                    "data": {
                        "texture_set": "Body",
                        "stack": "Body",
                        "resolved_channels": {},
                    },
                }
            snapshot_calls = sum("geometry_mask" in call[0] for call in self.calls)
            if "geometry_mask" in code and snapshot_calls == 1:
                return {
                    "success": True,
                    "data": {"texture_set": "Body", "stack": "Body", "layers": []},
                }
            if "geometry_mask" in code:
                raise RuntimeError("snapshot failed")
            if "created_nodes" in code:
                return {
                    "success": True,
                    "data": {
                        "created_count": 1,
                        "nodes": [{"uid": 99, "name": "Temporary", "type": "GroupLayerNode"}],
                    },
                }
            return {"success": True, "data": {"uid": 99}}

    remote = FailingVerificationRemote()
    with pytest.raises(RuntimeError, match="snapshot failed"):
        PainterOperations(remote).create_layer_recipe(
            [{"type": "group", "name": "Temporary"}]
        )
    assert any("delete_node" in code and params == {"uid": 99} for code, params in remote.calls)


def test_recipe_backup_requires_configured_project_root(monkeypatch, tmp_path):
    monkeypatch.delenv("SP_MCP_PROJECT_ROOTS", raising=False)
    with pytest.raises(PermissionError, match="disabled"):
        PainterOperations(FakeRemote()).plan_layer_recipe(
            [{"type": "group", "name": "Safe"}],
            backup_path=str(tmp_path / "safe.spp"),
        )


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
