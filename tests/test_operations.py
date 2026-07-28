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


def test_resource_import_requires_confirmation_and_safe_usage(tmp_path, monkeypatch):
    source = tmp_path / "texture.png"
    source.write_bytes(b"png")
    monkeypatch.setenv("SP_MCP_RESOURCE_ROOTS", str(tmp_path))
    operations = PainterOperations(FakeRemote())
    with pytest.raises(PermissionError, match="confirm=true"):
        operations.import_project_resource(str(source), "TEXTURE")
    with pytest.raises(ValueError, match="safe import usages"):
        operations.import_project_resource(str(source), "SHADER", confirm=True)
    assert operations.remote.calls == []


def test_resource_import_rejects_script_like_files(tmp_path, monkeypatch):
    source = tmp_path / "payload.py"
    source.write_text("pass")
    monkeypatch.setenv("SP_MCP_RESOURCE_ROOTS", str(tmp_path))
    with pytest.raises(ValueError, match="script-like"):
        PainterOperations(FakeRemote()).import_session_resource(
            str(source), "TEXTURE", confirm=True
        )


def test_project_and_session_resource_import_transport(tmp_path, monkeypatch):
    source = tmp_path / "texture.png"
    source.write_bytes(b"png")
    monkeypatch.setenv("SP_MCP_RESOURCE_ROOTS", str(tmp_path))
    response = {"success": True, "data": {"verified": True, "url": "resource://test/item"}}
    for scope in ("project", "session"):
        remote = FakeRemote(response)
        operations = PainterOperations(remote)
        method = getattr(operations, f"import_{scope}_resource")
        assert method(str(source), "texture", "Imported", "MCP", True)["verified"]
        assert remote.calls[0][1] == {
            "scope": scope,
            "file_path": source.resolve().as_posix(),
            "usage": "TEXTURE",
            "name": "Imported",
            "group": "MCP",
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


def test_advanced_projection_validation_is_local():
    operations = PainterOperations(FakeRemote())
    with pytest.raises(ValueError, match="Unknown projection settings"):
        operations.set_fill_projection_advanced(1, "Planar", {"mystery": 1})
    with pytest.raises(ValueError, match="0..1"):
        operations.set_fill_projection_advanced(1, "Triplanar", {"hardness": 2})
    with pytest.raises(ValueError, match="exactly 3"):
        operations.set_fill_projection_advanced(
            1, "Spherical", {"projection_3d": {"offset": [0, 1]}}
        )
    with pytest.raises(ValueError, match="does not support"):
        operations.set_fill_projection_advanced(
            1, "Triplanar", {"transform": {"offset": [0, 0]}}
        )
    with pytest.raises(ValueError, match="Spherical projection does not support"):
        operations.set_fill_projection_advanced(
            1, "Spherical", {"backface_culling": {"enabled": True}}
        )
    assert operations.remote.calls == []


def test_fill_resource_requires_channel_or_material_mode():
    operations = PainterOperations(FakeRemote())
    with pytest.raises(ValueError, match="resource://"):
        operations.set_fill_resource(1, "https://example.com/a.png", "BaseColor")
    with pytest.raises(ValueError, match="channel is required"):
        operations.set_fill_resource(1, "resource://project/a")
    with pytest.raises(ValueError, match="must be omitted"):
        operations.set_fill_resource(
            1, "resource://project/a", "BaseColor", material_mode=True
        )


def test_procedural_input_requires_exactly_one_action():
    operations = PainterOperations(FakeRemote())
    with pytest.raises(ValueError, match="exactly one"):
        operations.set_procedural_input(1, "input")
    with pytest.raises(ValueError, match="exactly one"):
        operations.set_procedural_input(
            1, "input", "resource://project/a", reset=True
        )
    with pytest.raises(ValueError, match="resource://"):
        operations.set_procedural_input(1, "input", "C:/texture.png")
    assert operations.remote.calls == []


def test_procedural_input_tools_transport_source_context():
    remote = FakeRemote()
    operations = PainterOperations(remote)
    operations.get_procedural_inputs(7, "BaseColor")
    operations.set_procedural_input(
        7, "input", "resource://project0/image", "BaseColor"
    )
    operations.set_procedural_input(7, "input", channel="BaseColor", reset=True)
    assert remote.calls[0][1] == {"uid": 7, "channel": "BaseColor"}
    assert remote.calls[1][1] == {
        "uid": 7,
        "input_name": "input",
        "resource_url": "resource://project0/image",
        "channel": "BaseColor",
    }
    assert remote.calls[2][1] == {
        "uid": 7,
        "input_name": "input",
        "resource_url": None,
        "channel": "BaseColor",
    }


def test_async_mutations_require_confirmation():
    operations = PainterOperations(FakeRemote())
    with pytest.raises(PermissionError, match="confirm=true"):
        operations.start_bake("Body")
    with pytest.raises(PermissionError, match="confirm=true"):
        operations.start_mesh_reload("C:/mesh.fbx")
    assert operations.remote.calls == []


def test_mesh_reload_requires_approved_existing_mesh(monkeypatch, tmp_path):
    operations = PainterOperations(FakeRemote())
    monkeypatch.delenv("SP_MCP_MESH_ROOTS", raising=False)
    with pytest.raises(PermissionError, match="disabled"):
        operations.plan_mesh_reload(str(tmp_path / "mesh.fbx"))
    monkeypatch.setenv("SP_MCP_MESH_ROOTS", str(tmp_path))
    with pytest.raises(FileNotFoundError, match="does not exist"):
        operations.plan_mesh_reload(str(tmp_path / "mesh.fbx"))
    unsupported = tmp_path / "mesh.blend"
    unsupported.write_bytes(b"test")
    with pytest.raises(ValueError, match="fbx"):
        operations.plan_mesh_reload(str(unsupported))


def test_auto_unwrap_and_mesh_settings_validation_is_local():
    operations = PainterOperations(FakeRemote())
    with pytest.raises(ValueError, match="power-of-two"):
        operations._normalize_auto_unwrap_settings({
            "uv_tiles": {
                "mode": "texel_density",
                "texel_density": 10,
                "reference_resolution": 1000,
            }
        })
    with pytest.raises(ValueError, match="scope_name"):
        operations._normalize_mesh_settings(
            {"type": "usd", "scope_name": "relative"}, allow_gltf=True
        )
    with pytest.raises(ValueError, match="type must be usd"):
        operations._normalize_mesh_settings(
            {"type": "gltf", "invert_normal_maps": True}, allow_gltf=False
        )


def test_mesh_reload_plan_normalizes_auto_unwrap(monkeypatch, tmp_path):
    mesh = tmp_path / "mesh.fbx"
    mesh.write_bytes(b"mesh")
    monkeypatch.setenv("SP_MCP_MESH_ROOTS", str(tmp_path))
    response = {
        "success": True,
        "data": {"busy": False, "current_mesh": "old.fbx", "texture_sets": []},
    }
    result = PainterOperations(FakeRemote(response)).plan_mesh_reload(
        str(mesh),
        auto_unwrap_settings={
            "recompute_seams": False,
            "uv_tiles": {"mode": "count", "max_count": 8},
        },
    )
    assert result["auto_unwrap_settings"]["recompute_seams"] is False
    assert result["auto_unwrap_settings"]["uv_tiles"] == {
        "mode": "count",
        "max_count": 8,
    }


def test_project_creation_plan_validates_and_normalizes(monkeypatch, tmp_path):
    mesh = tmp_path / "mesh.fbx"
    mesh.write_bytes(b"mesh")
    monkeypatch.setenv("SP_MCP_MESH_ROOTS", str(tmp_path))
    monkeypatch.setenv("SP_MCP_PROJECT_ROOTS", str(tmp_path))
    monkeypatch.setenv("SP_MCP_RESOURCE_ROOTS", str(tmp_path))
    response = {
        "success": True,
        "data": {"open": False, "path": None, "needs_saving": False, "busy": False},
    }
    result = PainterOperations(FakeRemote(response)).plan_project_creation(
        str(mesh),
        str(tmp_path / "new.spp"),
        settings={
            "normal_map_format": "OpenGL",
            "default_texture_resolution": 1024,
            "auto_unwrap_settings": {
                "uv_tiles": {
                    "mode": "texel_density",
                    "texel_density": 20,
                    "reference_resolution": 2048,
                }
            },
        },
    )
    assert result["ready"] is True
    assert result["settings"]["normal_map_format"] == "OpenGL"
    assert result["settings"]["auto_unwrap_settings"]["uv_tiles"]["mode"] == "texel_density"


def test_project_creation_plan_requires_backup_for_open_project(monkeypatch, tmp_path):
    mesh = tmp_path / "mesh.fbx"
    mesh.write_bytes(b"mesh")
    monkeypatch.setenv("SP_MCP_MESH_ROOTS", str(tmp_path))
    monkeypatch.setenv("SP_MCP_PROJECT_ROOTS", str(tmp_path))
    response = {
        "success": True,
        "data": {"open": True, "path": "old.spp", "needs_saving": True, "busy": False},
    }
    result = PainterOperations(FakeRemote(response)).plan_project_creation(
        str(mesh), str(tmp_path / "new.spp"), replace_current=True
    )
    assert result["ready"] is False
    assert result["errors"][0]["code"] == "backup_required"


def test_project_creation_plan_rejects_recovery_path_collisions(monkeypatch, tmp_path):
    mesh = tmp_path / "mesh.fbx"
    mesh.write_bytes(b"mesh")
    current = tmp_path / "current.spp"
    current.write_bytes(b"project")
    monkeypatch.setenv("SP_MCP_MESH_ROOTS", str(tmp_path))
    monkeypatch.setenv("SP_MCP_PROJECT_ROOTS", str(tmp_path))
    response = {
        "success": True,
        "data": {
            "open": True,
            "path": str(current),
            "needs_saving": False,
            "busy": False,
        },
    }
    operations = PainterOperations(FakeRemote(response))
    same_output = operations.plan_project_creation(
        str(mesh),
        str(current),
        overwrite=True,
        replace_current=True,
        backup_current_path=str(tmp_path / "backup.spp"),
    )
    assert "output_is_current_project" in {
        item["code"] for item in same_output["errors"]
    }
    collision = operations.plan_project_creation(
        str(mesh),
        str(tmp_path / "new.spp"),
        replace_current=True,
        backup_current_path=str(tmp_path / "new.spp"),
    )
    assert "output_backup_collision" in {item["code"] for item in collision["errors"]}


def test_project_context_mutations_require_confirmation():
    operations = PainterOperations(FakeRemote())
    with pytest.raises(PermissionError, match="confirm=true"):
        operations.create_project("mesh.fbx", "new.spp")
    with pytest.raises(PermissionError, match="confirm=true"):
        operations.open_project("project.spp")
    with pytest.raises(PermissionError, match="confirm=true"):
        operations.save_project()
    assert operations.remote.calls == []


def test_fill_parameter_values_are_validated_locally():
    operations = PainterOperations(FakeRemote())
    with pytest.raises(ValueError, match="non-empty"):
        operations.set_fill_parameters(1, {})
    with pytest.raises(ValueError, match="finite"):
        operations.set_fill_parameters(1, {"roughness": float("nan")})
    with pytest.raises(ValueError, match="Unsupported value type"):
        operations.set_fill_parameters(1, {"roughness": {"value": 0.5}})
    with pytest.raises(ValueError, match="scalar"):
        operations.set_fill_parameters(1, {"roughness": [[0.5]]})
    assert operations.remote.calls == []


def test_fill_parameter_tools_transport_channel_and_values():
    remote = FakeRemote()
    operations = PainterOperations(remote)
    operations.get_fill_parameters(7, "BaseColor")
    operations.set_fill_parameters(7, {"scale": 0.5}, "BaseColor")
    operations.apply_fill_preset(7, "Soft", "BaseColor")
    assert remote.calls[0][1] == {"uid": 7, "channel": "BaseColor"}
    assert remote.calls[1][1] == {
        "uid": 7,
        "channel": "BaseColor",
        "values": {"scale": 0.5},
    }
    assert remote.calls[2][1] == {
        "uid": 7,
        "preset": "Soft",
        "channel": "BaseColor",
    }


def test_fill_preset_and_anchor_validation_is_local():
    operations = PainterOperations(FakeRemote())
    with pytest.raises(ValueError, match="non-empty"):
        operations.apply_fill_preset(1, "  ")
    with pytest.raises(ValueError, match="required"):
        operations.set_fill_anchor_source(1, 2)
    with pytest.raises(ValueError, match="omitted"):
        operations.set_fill_anchor_source(1, 2, "BaseColor", material_mode=True)
    assert operations.remote.calls == []


def test_baking_configuration_requires_valid_confirmed_change():
    operations = PainterOperations(FakeRemote())
    with pytest.raises(ValueError, match="At least one"):
        operations.configure_baking("Body", confirm=True)
    with pytest.raises(ValueError, match="duplicates"):
        operations.configure_baking(
            "Body", enabled_bakers=["AO", "AO"], confirm=True
        )
    with pytest.raises(ValueError, match="UDIM"):
        operations.configure_baking("Body", enabled_uv_tiles=[1000], confirm=True)
    with pytest.raises(PermissionError, match="confirm=true"):
        operations.configure_baking("Body", enabled=True)
    assert operations.remote.calls == []


def test_baking_configuration_transports_typed_changes():
    remote = FakeRemote()
    PainterOperations(remote).configure_baking(
        "Body",
        enabled=True,
        enabled_bakers=["AO", "Curvature"],
        enabled_uv_tiles=[1001],
        curvature_method="FromMesh",
        common_values={"DilationWidth": 16},
        baker_values={"AO": {"NbSecondary": 32}},
        confirm=True,
    )
    assert remote.calls[0][1] == {
        "texture_set": "Body",
        "enabled": True,
        "enabled_bakers": ["AO", "Curvature"],
        "enabled_uv_tiles": [1001],
        "curvature_method": "FromMesh",
        "common_values": {"DilationWidth": 16},
        "baker_values": {"AO": {"NbSecondary": 32}},
    }


def test_baking_parameter_inspection_transports_baker():
    remote = FakeRemote()
    PainterOperations(remote).inspect_baking_parameters("Body", "AO")
    assert remote.calls[0][1] == {"texture_set": "Body", "baker": "AO"}


def test_baking_mesh_inputs_require_confirmation_and_approved_root(monkeypatch, tmp_path):
    operations = PainterOperations(FakeRemote())
    with pytest.raises(PermissionError, match="confirm=true"):
        operations.set_baking_mesh_inputs("Body", high_poly_files=["C:/high.fbx"])
    monkeypatch.delenv("SP_MCP_BAKE_MESH_ROOTS", raising=False)
    with pytest.raises(PermissionError, match="disabled"):
        operations.set_baking_mesh_inputs(
            "Body", high_poly_files=[str(tmp_path / "high.fbx")], confirm=True
        )


def test_baking_mesh_inputs_transport_file_urls(monkeypatch, tmp_path):
    high = tmp_path / "high.fbx"
    cage = tmp_path / "cage.obj"
    high.write_bytes(b"mesh")
    cage.write_bytes(b"mesh")
    monkeypatch.setenv("SP_MCP_BAKE_MESH_ROOTS", str(tmp_path))
    remote = FakeRemote()
    PainterOperations(remote).set_baking_mesh_inputs(
        "Body",
        high_poly_files=[str(high)],
        cage_file=str(cage),
        low_as_high=False,
        confirm=True,
    )
    assert remote.calls[0][1] == {
        "texture_set": "Body",
        "high_poly_urls": [high.resolve().as_uri()],
        "cage_url": cage.resolve().as_uri(),
        "low_as_high": False,
        "cage_mode": "Custom file",
    }


def test_baking_resource_input_validation_and_transport():
    operations = PainterOperations(FakeRemote())
    with pytest.raises(PermissionError, match="confirm=true"):
        operations.set_baking_resource_input("Body", "OffsetMap", clear=True)
    with pytest.raises(ValueError, match="exactly one"):
        operations.set_baking_resource_input(
            "Body", "OffsetMap", "resource://project0/map", clear=True, confirm=True
        )
    with pytest.raises(ValueError, match="resource://"):
        operations.set_baking_resource_input(
            "Body", "OffsetMap", "C:/map.png", confirm=True
        )
    remote = FakeRemote()
    PainterOperations(remote).set_baking_resource_input(
        "Body", "OffsetMap", "resource://project0/map", confirm=True
    )
    assert remote.calls[0][1] == {
        "texture_set": "Body",
        "parameter": "OffsetMap",
        "resource_url": "resource://project0/map",
        "baker": None,
    }


def test_baking_preset_schema_and_capture_validation_are_local():
    operations = PainterOperations(FakeRemote())
    with pytest.raises(ValueError, match="unique"):
        operations.capture_baking_preset("Body", ["AO", "AO"])
    with pytest.raises(ValueError, match="schema"):
        operations.apply_baking_preset("Body", {"schema": "future"}, confirm=True)
    assert operations.remote.calls == []


def test_apply_baking_preset_routes_through_transactional_configuration():
    remote = FakeRemote()
    preset = {
        "schema": "substance-painter-mcp/baking-preset@1",
        "source_texture_set": "Source",
        "enabled": True,
        "enabled_bakers": ["AO"],
        "enabled_uv_tiles": [1001],
        "curvature_method": "FromMesh",
        "common_values": {"OutputSize": [10, 10]},
        "baker_values": {"AO": {"Distribution": "Cosine"}},
    }
    result = PainterOperations(remote).apply_baking_preset(
        "Target", preset, confirm=True
    )
    assert remote.calls[0][1]["texture_set"] == "Target"
    assert remote.calls[0][1]["common_values"] == {"OutputSize": [10, 10]}
    assert result["preset_schema"] == preset["schema"]
    assert result["source_texture_set"] == "Source"


def test_bake_preflight_validates_selection_and_transports_names():
    remote = FakeRemote()
    operations = PainterOperations(remote)
    with pytest.raises(ValueError, match="at least one"):
        operations.preflight_bake([])
    with pytest.raises(ValueError, match="duplicates"):
        operations.preflight_bake(["Body", "Body"])
    operations.preflight_bake(["Body", "Head"])
    assert remote.calls[0][1] == {"texture_sets": ["Body", "Head"]}


def test_batch_bake_requires_confirmation_before_preflight():
    operations = PainterOperations(FakeRemote())
    with pytest.raises(PermissionError, match="confirm=true"):
        operations.start_batch_bake(["Body"])
    assert operations.remote.calls == []


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
