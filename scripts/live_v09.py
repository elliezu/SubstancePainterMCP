"""Live validation for v0.9 project lifecycle and typed mesh settings."""

from __future__ import annotations

import argparse
import json
import time

from substance_painter_mcp.client import PainterRemote
from substance_painter_mcp.operations import PainterOperations


def emit(label: str, value) -> None:
    print(label, json.dumps(value, ensure_ascii=False, indent=2))


def current_mesh(remote: PainterRemote) -> str:
    envelope = remote.execute_python_json(
        """
import substance_painter.project as project
result = project.last_imported_mesh_path()
"""
    )
    if not envelope.get("success"):
        raise RuntimeError(envelope)
    return envelope["data"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--backup", required=True)
    args = parser.parse_args()

    remote = PainterRemote()
    operations = PainterOperations(remote)
    original = operations.project_info()
    if not original["open"] or not original["path"]:
        raise RuntimeError("A saved disposable project must be open")
    mesh = current_mesh(remote)
    original_sets = original["texture_sets"]
    operations.save_project(confirm=True)

    settings = {
        "normal_map_format": "OpenGL",
        "tangent_space_mode": "PerFragment",
        "project_workflow": "Default",
        "default_texture_resolution": 256,
        "import_cameras": False,
        "auto_unwrap_settings": {
            "recompute_seams": False,
            "recompute_uv_islands": False,
            "recompute_packing": False,
            "margin_size": 2,
            "island_orientation": "RotateFreely",
            "uv_tiles": {"mode": "count", "max_count": 4},
            "avoid_elongated_uv_islands": False,
            "create_fewer_seams": True,
        },
    }
    try:
        plan = operations.plan_project_creation(
            mesh,
            args.output,
            settings=settings,
            overwrite=True,
            replace_current=True,
            backup_current_path=args.backup,
            overwrite_backup=True,
        )
        emit("creation_plan", plan)
        if not plan["ready"]:
            raise AssertionError(f"Project creation plan is not ready: {plan['errors']}")
        created = operations.create_project(
            mesh,
            args.output,
            settings=settings,
            overwrite=True,
            replace_current=True,
            backup_current_path=args.backup,
            overwrite_backup=True,
            confirm=True,
        )
        emit("creation_started", created)
        deadline = time.time() + 180
        while time.time() < deadline:
            creation_job = operations.get_project_creation_job(created["job_id"])
            if creation_job["found"] and creation_job["job"]["status"] in {
                "success", "failed"
            }:
                break
            time.sleep(0.25)
        else:
            raise TimeoutError("Project creation did not finish within 180 seconds")
        emit("creation_terminal", creation_job)
        if creation_job["job"]["status"] != "success":
            raise AssertionError(f"Project creation failed: {creation_job['job']['error']}")
        if not creation_job["verification"]["verified"]:
            raise AssertionError("Created project was not saved and verified")
        saved = operations.save_project(mode="Full", confirm=True)
        emit("saved_created_project", saved)
    finally:
        current = operations.project_info()
        if not current["open"] or current["path"].casefold() != original["path"].casefold():
            reopened = operations.open_project(original["path"], confirm=True)
            emit("reopened_original", reopened)

    restored = operations.project_info()
    if restored["path"].casefold() != original["path"].casefold():
        raise AssertionError("Original project was not restored")
    if restored["texture_sets"] != original_sets:
        raise AssertionError("Original Texture Sets changed during project switching")

    unwrap = {
        "recompute_seams": False,
        "recompute_uv_islands": False,
        "recompute_packing": False,
        "uv_tiles": {"mode": "count", "max_count": 4},
    }
    reload_plan = operations.plan_mesh_reload(mesh, auto_unwrap_settings=unwrap)
    emit("reload_plan", reload_plan)
    started = operations.start_mesh_reload(
        mesh,
        confirm=True,
        preserve_strokes=True,
        import_cameras=False,
        auto_unwrap_settings=unwrap,
    )
    emit("reload_started", started)
    deadline = time.time() + 120
    while time.time() < deadline:
        job = operations.get_mesh_reload_job(started["job_id"])
        if job["found"] and job["job"]["status"] in {"success", "failed"}:
            break
        time.sleep(0.25)
    else:
        raise TimeoutError("Mesh reload did not finish within 120 seconds")
    emit("reload_terminal", job)
    if job["job"]["status"] != "success":
        raise AssertionError(f"Mesh reload failed: {job['job']['error']}")
    if job["job"]["added_texture_sets"] or job["job"]["removed_texture_sets"]:
        raise AssertionError("Same-mesh reload changed Texture Set names")
    final_save = operations.save_project(confirm=True)
    emit("final_save", final_save)


if __name__ == "__main__":
    main()
