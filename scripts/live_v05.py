"""Live validation for v0.5 Fill resources, projections, bake jobs, and mesh reload."""

from __future__ import annotations

import argparse
import json
import time

from substance_painter_mcp.client import PainterRemote
from substance_painter_mcp.operations import PainterOperations


def emit(label: str, value) -> None:
    print(label, json.dumps(value, ensure_ascii=False, indent=2))


def wait_for_job(fetch, job_id: str, timeout: float = 300) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = fetch(job_id)
        emit("job", response)
        job = response.get("job") or {}
        if job.get("status") not in {"starting", "running"}:
            return response
        time.sleep(0.5)
    raise TimeoutError(f"Job did not finish in {timeout} seconds: {job_id}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh", required=True)
    parser.add_argument("--run-bake", action="store_true")
    parser.add_argument("--run-mesh-reload", action="store_true")
    args = parser.parse_args()

    operations = PainterOperations(PainterRemote())
    validation_set = operations.project_info()["texture_sets"][0]
    before = operations.snapshot_layer_tree(validation_set)
    created_uid: int | None = None
    try:
        created = operations.create_fill_layer("__MCP_V05_FILL__", validation_set)
        created_uid = created["uid"]
        sources_before = operations.get_fill_sources(created_uid)
        emit("sources_before", sources_before)

        textures = operations.search_resources(
            "p:starter_assets", limit=1, usage="TEXTURE"
        )
        if not textures["resources"]:
            raise AssertionError("No starter Texture resource was found")
        emit(
            "resource_assigned",
            operations.set_fill_resource(
                created_uid, textures["resources"][0]["url"], "BaseColor"
            ),
        )
        emit("sources_after", operations.get_fill_sources(created_uid))

        materials = operations.search_resources(
            "p:starter_assets", limit=1, usage="BASE_MATERIAL"
        )
        if not materials["resources"]:
            raise AssertionError("No starter Base Material resource was found")
        emit(
            "material_assigned",
            operations.set_fill_resource(
                created_uid, materials["resources"][0]["url"], material_mode=True
            ),
        )
        material_sources = operations.get_fill_sources(created_uid)
        emit("material_verified", material_sources)
        if material_sources["source_mode"] != "Material":
            raise AssertionError("Base Material did not switch the Fill to Material mode")

        emit(
            "projection_planar",
            operations.set_fill_projection_advanced(
                created_uid,
                "Planar",
                {
                    "filtering_mode": "BilinearSharp",
                    "uv_wrapping_mode": "Repeat",
                    "shape_crop_mode": "CroppedToShape",
                    "backface_culling_angle": 90,
                    "transform": {"scale": [1.25, 1.5], "rotation": 12.5},
                    "projection_3d": {
                        "offset": [0.01, -0.02, 0.03],
                        "rotation": [5, 10, 15],
                        "scale": [1, 1, 1],
                    },
                    "depth_culling": {"enabled": True, "hardness": 0.25},
                    "backface_culling": {"enabled": True, "hardness": 0.5},
                },
            ),
        )
        projection = operations.get_fill_projection(created_uid)
        emit("projection_verified", projection)
        if projection["mode"] != "Planar":
            raise AssertionError("Advanced Planar projection was not applied")
        for mode, settings in (
            (
                "Spherical",
                {
                    "shape_crop_mode": "ExtendsOutsideShape",
                    "projection_3d": {"rotation": [0, 30, 0]},
                },
            ),
            (
                "Cylindrical",
                {
                    "angle": 240,
                    "backface_culling": {"enabled": True, "hardness": 0.4},
                },
            ),
            (
                "Triplanar",
                {
                    "hardness": 0.35,
                    "projection_3d": {"scale": [1.1, 1.1, 1.1]},
                },
            ),
        ):
            changed = operations.set_fill_projection_advanced(
                created_uid, mode, settings
            )
            emit(f"projection_{mode.casefold()}", changed)
            if operations.get_fill_projection(created_uid)["mode"] != mode:
                raise AssertionError(f"Advanced {mode} projection was not applied")
    finally:
        if created_uid is not None:
            emit("cleanup_fill", operations.delete_layer(created_uid))

    after = operations.snapshot_layer_tree(validation_set)
    if after["sha256"] != before["sha256"]:
        raise AssertionError("Fill validation did not restore the original layer tree")

    if args.run_bake:
        bake_plan = operations.inspect_baking()
        texture_set = next(
            item["texture_set"]
            for item in bake_plan["texture_sets"]
            if item["enabled"] and item["enabled_uv_tiles"]
        )
        bake = operations.start_bake(texture_set, confirm=True)
        emit("bake_started", bake)
        cancel = operations.cancel_bake(bake["job_id"])
        emit("bake_cancel_requested", cancel)
        terminal = wait_for_job(operations.get_bake_job, bake["job_id"])
        if terminal["job"]["status"] not in {"success", "cancelled"}:
            raise AssertionError(f"Bake failed: {terminal}")

    plan = operations.plan_mesh_reload(args.mesh)
    emit("mesh_reload_plan", plan)
    if args.run_mesh_reload:
        reload_job = operations.start_mesh_reload(args.mesh, confirm=True)
        emit("mesh_reload_started", reload_job)
        terminal = wait_for_job(
            operations.get_mesh_reload_job, reload_job["job_id"]
        )
        if terminal["job"]["status"] != "success":
            raise AssertionError(f"Mesh reload failed: {terminal}")


if __name__ == "__main__":
    main()
