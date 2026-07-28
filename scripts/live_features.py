"""Live validation for v0.3 features against a disposable Painter project."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from substance_painter_mcp.client import PainterRemote
from substance_painter_mcp.operations import PainterOperations


def emit(label: str, value) -> None:
    print(label, json.dumps(value, ensure_ascii=False, indent=2))


def flatten(nodes: list[dict]) -> list[dict]:
    result: list[dict] = []
    for node in nodes:
        result.append(node)
        result.extend(flatten(node.get("children", [])))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--project-copy", action="store_true")
    parser.add_argument("--texture-export", action="store_true")
    args = parser.parse_args()

    root = Path(args.output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    operations = PainterOperations(PainterRemote())

    emit("status", operations.status())
    before = operations.snapshot_layer_tree()
    emit("snapshot_before", {"sha256": before["sha256"]})
    emit("profiles", operations.list_export_profiles())
    emit("preset", operations.inspect_export_preset("PBR Metallic Roughness"))
    generators = operations.search_resources(
        "p:starter_assets", limit=3, usage="Generator"
    )
    emit("generators", generators)
    emit("outdated", operations.find_outdated_resources())

    # Confirm that a failed effect insertion does not leave an automatically added mask behind.
    effect_probe = operations.create_paint_layer("__MCP_EFFECT_ROLLBACK__")
    try:
        before_failed_effect = operations.snapshot_layer_tree()
        try:
            operations.insert_mask_effect(
                effect_probe["uid"],
                "generator",
                "resource://starter_assets/__MCP_RESOURCE_THAT_DOES_NOT_EXIST__",
            )
        except Exception as exc:
            emit("expected_effect_error", {"type": type(exc).__name__, "message": str(exc)})
        after_failed_effect = operations.snapshot_layer_tree()
        if after_failed_effect["sha256"] != before_failed_effect["sha256"]:
            raise AssertionError("failed mask effect insertion did not fully roll back")
    finally:
        operations.delete_layer(effect_probe["uid"])

    # Confirm that a runtime failure rolls back every node created by the recipe.
    try:
        operations.create_layer_recipe(
            [
                {
                    "type": "fill",
                    "name": "__MCP_ROLLBACK_FAIL__",
                    "channels": {"DefinitelyNotAChannel": 0.5},
                },
                {"type": "paint", "name": "__MCP_ROLLBACK_PAINT__"},
            ]
        )
    except Exception as exc:
        emit("expected_rollback_error", {"type": type(exc).__name__, "message": str(exc)})
    after_failed_recipe = operations.snapshot_layer_tree()
    if after_failed_recipe["sha256"] != before["sha256"]:
        raise AssertionError("failed recipe did not fully roll back")

    created_group_uid: int | None = None
    try:
        recipe = operations.create_layer_recipe(
            [
                {
                    "type": "group",
                    "name": "__MCP_V03_RECIPE__",
                    "children": [
                        {
                            "type": "fill",
                            "name": "Recipe Fill",
                            "base_color": [0.12, 0.42, 0.72],
                            "channels": {"Roughness": 0.33, "Metallic": 0.08},
                            "mask": {"background": "Black"},
                        },
                        {
                            "type": "paint",
                            "name": "Recipe Paint",
                            "active_channels": ["BaseColor", "Roughness"],
                        },
                    ],
                }
            ]
        )
        emit("recipe", recipe)
        created_group_uid = recipe["nodes"][0]["uid"]
        nodes = flatten(recipe["nodes"])
        fill = next(node for node in nodes if node["type"] == "FillLayerNode")
        paint = next(node for node in nodes if node["type"] == "PaintLayerNode")

        emit(
            "active_channels",
            operations.set_active_channels(
                paint["uid"], ["BaseColor", "Roughness", "Metallic"]
            ),
        )
        emit(
            "mask_levels",
            operations.insert_mask_effect(fill["uid"], "levels", name="MCP Levels"),
        )
        emit(
            "mask_anchor",
            operations.insert_mask_effect(fill["uid"], "anchor", name="MCP Anchor"),
        )
        if generators["resources"]:
            emit(
                "mask_generator",
                operations.insert_mask_effect(
                    fill["uid"],
                    "generator",
                    generators["resources"][0]["url"],
                    "MCP Generator",
                ),
            )

        during = operations.snapshot_layer_tree()
        if during["sha256"] == before["sha256"]:
            raise AssertionError("successful recipe did not change the layer snapshot")
        emit("snapshot_during", {"sha256": during["sha256"]})

        emit(
            "smart_material",
            operations.export_smart_material(
                created_group_uid, "MCP_V03_Material", str(root / "smart")
            ),
        )
        emit(
            "smart_mask",
            operations.export_smart_mask(
                fill["uid"], "MCP_V03_Mask", str(root / "smart")
            ),
        )
        if args.texture_export:
            emit(
                "profile_plan",
                operations.plan_profile_export(
                    str(root / "textures"), "generic-pbr", size_log2=8
                ),
            )
            emit(
                "profile_export",
                operations.export_with_profile(
                    str(root / "textures"), "generic-pbr", size_log2=8
                ),
            )
    finally:
        if created_group_uid is not None:
            emit("cleanup", operations.delete_layer(created_group_uid))

    final = operations.snapshot_layer_tree()
    emit("snapshot_final", {"sha256": final["sha256"]})
    if final["sha256"] != before["sha256"]:
        raise AssertionError("live feature test did not restore the original layer tree")
    if args.project_copy:
        emit(
            "project_copy",
            operations.save_project_copy(str(root / "MCP_V03_Backup.spp")),
        )


if __name__ == "__main__":
    main()
