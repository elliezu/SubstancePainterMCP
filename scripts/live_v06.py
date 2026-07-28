"""Live validation for v0.6 procedural sources, anchors, and baker configuration."""

from __future__ import annotations

import json

from substance_painter_mcp.client import PainterRemote
from substance_painter_mcp.operations import PainterOperations


def emit(label: str, value) -> None:
    print(label, json.dumps(value, ensure_ascii=False, indent=2))


def main() -> None:
    operations = PainterOperations(PainterRemote())
    texture_sets = operations.project_info()["texture_sets"]
    layer_set = texture_sets[0]
    before = operations.snapshot_layer_tree(layer_set)
    source_uid: int | None = None
    target_uid: int | None = None

    try:
        source_layer = operations.create_fill_layer("__MCP_V06_SOURCE__", layer_set)
        target_layer = operations.create_fill_layer("__MCP_V06_TARGET__", layer_set)
        source_uid = source_layer["uid"]
        target_uid = target_layer["uid"]

        materials = operations.search_resources(
            "p:starter_assets", limit=20, usage="BASE_MATERIAL"
        )
        chosen = None
        for candidate in materials["resources"]:
            operations.set_fill_resource(source_uid, candidate["url"], material_mode=True)
            try:
                details = operations.get_fill_parameters(source_uid)
            except Exception:
                continue
            if details["parameters"] and details["presets"]:
                chosen = (candidate, details)
                break
        if chosen is None:
            raise AssertionError("No starter Base Material exposed parameters and presets")
        emit("procedural_source", chosen[0])
        details = chosen[1]
        emit(
            "procedural_summary",
            {
                "count": len(details["parameters"]),
                "presets": details["presets"],
            },
        )

        updates = {}
        for name, parameter in details["parameters"].items():
            value = parameter["value"]
            if parameter["widget"] == "Slider" and isinstance(value, float):
                metadata = parameter["metadata"]
                minimum = metadata.get("min")
                maximum = metadata.get("max")
                if isinstance(minimum, (int, float)) and isinstance(maximum, (int, float)):
                    updates[name] = minimum + (maximum - minimum) * 0.37
                    break
        color_name = next(
            (name for name, item in details["parameters"].items() if item["widget"] == "Color"),
            None,
        )
        if color_name:
            updates[color_name] = [0.2, 0.45, 0.75]
        if not updates:
            raise AssertionError("No safely editable procedural parameters were found")
        changed = operations.set_fill_parameters(source_uid, updates)
        emit("procedural_updated", changed)
        if set(changed["updated"]) != set(updates):
            raise AssertionError("Procedural parameter verification was incomplete")
        slider_name = next(iter(updates))
        slider_max = details["parameters"][slider_name]["metadata"].get("max")
        if isinstance(slider_max, (int, float)):
            try:
                operations.set_fill_parameters(source_uid, {slider_name: slider_max + 1})
            except Exception as exc:
                emit("procedural_invalid_rejected", str(exc))
            else:
                raise AssertionError("Out-of-range procedural value was accepted")
            unchanged = operations.get_fill_parameters(source_uid)["parameters"][slider_name]["value"]
            if abs(unchanged - changed["updated"][slider_name]) > 1e-5:
                raise AssertionError("Rejected procedural update changed the source")

        preset = details["presets"][0]
        emit("preset_applied", operations.apply_fill_preset(source_uid, preset))

        anchor_result = operations.insert_mask_effect(
            source_uid, "anchor", name="__MCP_V06_ANCHOR__"
        )
        anchor_uid = anchor_result["effects"][0]["uid"]
        anchors = operations.list_anchor_points(layer_set)
        emit("anchors", anchors)
        if anchor_uid not in {item["uid"] for item in anchors["anchors"]}:
            raise AssertionError("Created Anchor Point was not discovered")
        linked = operations.set_fill_anchor_source(
            target_uid, anchor_uid, channel="BaseColor"
        )
        emit("anchor_linked", linked)
        if linked["source_type"] != "SourceReference":
            raise AssertionError("Fill did not create a SourceReference")
    finally:
        if target_uid is not None:
            emit("cleanup_target", operations.delete_layer(target_uid))
        if source_uid is not None:
            emit("cleanup_source", operations.delete_layer(source_uid))

    after = operations.snapshot_layer_tree(layer_set)
    if after["sha256"] != before["sha256"]:
        raise AssertionError("v0.6 layer test did not restore the original digest")

    bake_set = next(
        item["texture_set"]
        for item in operations.inspect_baking()["texture_sets"]
        if item["enabled"] and item["enabled_uv_tiles"]
    )
    common_before = operations.inspect_baking_parameters(bake_set)
    ao_before = operations.inspect_baking_parameters(bake_set, "AO")
    dilation = common_before["common"]["DilationWidth"]["value"]
    rays = ao_before["baker_parameters"]["NbSecondary"]["value"]
    changed_dilation = dilation + 1 if dilation < 128 else dilation - 1
    changed_rays = rays + 1 if rays < 256 else rays - 1
    try:
        operations.configure_baking(
            bake_set,
            baker_values={"AO": {"NbSecondary": 999}},
            confirm=True,
        )
    except Exception as exc:
        emit("baking_invalid_rejected", str(exc))
    else:
        raise AssertionError("Out-of-range baker value was accepted")
    if (
        operations.inspect_baking_parameters(bake_set, "AO")["baker_parameters"]["NbSecondary"]["value"]
        != rays
    ):
        raise AssertionError("Rejected baking update changed the AO settings")
    try:
        configured = operations.configure_baking(
            bake_set,
            enabled=common_before["enabled"],
            enabled_bakers=common_before["enabled_bakers"],
            enabled_uv_tiles=common_before["enabled_uv_tiles"],
            curvature_method=common_before["curvature_method"],
            common_values={"DilationWidth": changed_dilation},
            baker_values={"AO": {"NbSecondary": changed_rays}},
            confirm=True,
        )
        emit("baking_configured", configured)
        if configured["common_values"]["DilationWidth"] != changed_dilation:
            raise AssertionError("Common baking parameter did not update")
        if configured["baker_values"]["AO"]["NbSecondary"] != changed_rays:
            raise AssertionError("AO baking parameter did not update")
    finally:
        restored = operations.configure_baking(
            bake_set,
            enabled=common_before["enabled"],
            enabled_bakers=common_before["enabled_bakers"],
            enabled_uv_tiles=common_before["enabled_uv_tiles"],
            curvature_method=common_before["curvature_method"],
            common_values={"DilationWidth": dilation},
            baker_values={"AO": {"NbSecondary": rays}},
            confirm=True,
        )
        emit("baking_restored", restored)

    common_after = operations.inspect_baking_parameters(bake_set)
    ao_after = operations.inspect_baking_parameters(bake_set, "AO")
    if common_after["common"]["DilationWidth"]["value"] != dilation:
        raise AssertionError("Common baking configuration was not restored")
    if ao_after["baker_parameters"]["NbSecondary"]["value"] != rays:
        raise AssertionError("AO baking configuration was not restored")


if __name__ == "__main__":
    main()
