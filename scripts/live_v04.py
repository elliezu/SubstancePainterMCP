"""Live validation for v0.4 geometry, recipes, Smart assets, and projections."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from substance_painter_mcp.client import PainterRemote
from substance_painter_mcp.operations import PainterOperations


def emit(label: str, value) -> None:
    print(label, json.dumps(value, ensure_ascii=False, indent=2))


def flatten(nodes: list[dict]) -> list[dict]:
    output: list[dict] = []
    for node in nodes:
        output.append(node)
        output.extend(flatten(node.get("children", [])))
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--project-copy", action="store_true")
    args = parser.parse_args()

    root = Path(args.output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    backup_path = str(root / "MCP_V04_PreRecipe.spp") if args.project_copy else None
    operations = PainterOperations(PainterRemote())

    before = operations.snapshot_layer_tree()
    recipe = [
        {
            "type": "group",
            "name": "__MCP_V04_RECIPE__",
            "children": [
                {
                    "type": "fill",
                    "name": "Geometry and Projection Test",
                    "base_color": [0.18, 0.38, 0.68],
                    "channels": {"Roughness": 0.4},
                }
            ],
        }
    ]
    plan = operations.plan_layer_recipe(recipe, backup_path=backup_path)
    emit("recipe_plan", plan)
    after_plan = operations.snapshot_layer_tree()
    if after_plan["sha256"] != before["sha256"]:
        raise AssertionError("recipe plan mutated the layer stack")

    recipe_group_uid: int | None = None
    smart_material_uid: int | None = None
    try:
        created = operations.create_layer_recipe(recipe, backup_path=backup_path)
        emit("recipe_created", created)
        recipe_group_uid = created["nodes"][0]["uid"]
        fill = next(
            node for node in flatten(created["nodes"])
            if node["type"] == "FillLayerNode"
        )

        geometry = operations.get_geometry_mask(fill["uid"])
        emit("geometry_initial", geometry)
        if geometry["available_meshes"]:
            emit(
                "geometry_mesh",
                operations.set_geometry_mask(
                    fill["uid"], "Mesh", [geometry["available_meshes"][0]], True
                ),
            )
        if geometry["available_uv_tiles"]:
            emit(
                "geometry_udim",
                operations.set_geometry_mask(
                    fill["uid"], "UVTile", [geometry["available_uv_tiles"][0]], True
                ),
            )

        emit("projection_initial", operations.get_fill_projection(fill["uid"]))
        emit(
            "projection_uv",
            operations.set_fill_projection(
                fill["uid"], "UV", scale=[2.0, 3.0], rotation=15.0, offset=[0.1, -0.2]
            ),
        )
        emit(
            "projection_triplanar",
            operations.set_fill_projection(
                fill["uid"], "Triplanar", scale=[1.5, 1.5], rotation=22.5
            ),
        )

        smart_materials = operations.search_resources(
            "p:starter_assets", limit=1, usage="SMART_MATERIAL"
        )
        smart_masks = operations.search_resources(
            "p:starter_assets", limit=1, usage="SMART_MASK"
        )
        if not smart_materials["resources"] or not smart_masks["resources"]:
            raise AssertionError("starter assets do not contain Smart Material/Mask resources")

        smart_material = operations.insert_smart_material(
            smart_materials["resources"][0]["url"], name="__MCP_V04_SMART_MATERIAL__"
        )
        smart_material_uid = smart_material["uid"]
        emit("smart_material_applied", smart_material)
        emit(
            "smart_mask_applied",
            operations.apply_smart_mask(fill["uid"], smart_masks["resources"][0]["url"]),
        )

        during = operations.snapshot_layer_tree()
        diff = operations.diff_layer_snapshots(before, during)
        emit("snapshot_diff", diff)
        if diff["equal"] or diff["counts"]["added"] < 2:
            raise AssertionError("snapshot diff did not report v0.4 inserted content")
    finally:
        if smart_material_uid is not None:
            emit("cleanup_smart_material", operations.delete_layer(smart_material_uid))
        if recipe_group_uid is not None:
            emit("cleanup_recipe", operations.delete_layer(recipe_group_uid))

    final = operations.snapshot_layer_tree()
    emit("snapshot_final", {"sha256": final["sha256"]})
    if final["sha256"] != before["sha256"]:
        raise AssertionError("v0.4 live test did not restore the original layer tree")


if __name__ == "__main__":
    main()
