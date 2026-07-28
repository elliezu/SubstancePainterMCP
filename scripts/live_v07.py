"""Live validation for v0.7 production baking workflows."""

from __future__ import annotations

import argparse
import json
import time

from substance_painter_mcp.client import PainterRemote
from substance_painter_mcp.operations import PainterOperations


def emit(label: str, value) -> None:
    print(label, json.dumps(value, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--high-poly", required=True)
    parser.add_argument("--success", action="store_true")
    args = parser.parse_args()

    operations = PainterOperations(PainterRemote())
    baking_before = operations.inspect_baking()
    enabled_before = {
        item["texture_set"]: item["enabled"] for item in baking_before["texture_sets"]
    }
    target = next(
        item["texture_set"]
        for item in baking_before["texture_sets"]
        if item["enabled"] and item["enabled_uv_tiles"]
    )

    mesh_inputs = operations.set_baking_mesh_inputs(
        target,
        high_poly_files=[args.high_poly],
        low_as_high=False,
        confirm=True,
    )
    emit("mesh_inputs", mesh_inputs)
    if not mesh_inputs["high_poly_files"]:
        raise AssertionError("High-poly mesh assignment was not verified")

    preset = operations.capture_baking_preset(target, ["AO", "ID"])
    emit(
        "preset_captured",
        {
            "schema": preset["schema"],
            "common_count": len(preset["common_values"]),
            "bakers": list(preset["baker_values"]),
        },
    )
    applied = operations.apply_baking_preset(target, preset, confirm=True)
    emit("preset_applied", applied)
    if applied["preset_schema"] != preset["schema"]:
        raise AssertionError("Baking preset schema was not preserved")

    preflight = operations.preflight_bake([target])
    emit("preflight", preflight)
    if not preflight["ready"]:
        raise AssertionError(f"Expected ready bake preflight: {preflight['errors']}")

    job = operations.start_batch_bake([target], confirm=True)
    emit("batch_started", job)
    try:
        cancelled = operations.cancel_bake(job["job_id"])
        emit("batch_cancel", cancelled)
    except Exception as exc:
        emit("batch_cancel_race", str(exc))

    deadline = time.monotonic() + 300
    terminal = None
    while time.monotonic() < deadline:
        status = operations.get_bake_job(job["job_id"])
        emit("batch_status", status)
        if status["job"]["status"] not in {"starting", "running"}:
            terminal = status["job"]
            break
        time.sleep(0.5)
    if terminal is None:
        raise TimeoutError("Batch bake did not finish")
    if terminal["status"] not in {"success", "cancelled"}:
        raise AssertionError(f"Batch bake failed: {terminal}")
    if terminal["results"] is None:
        raise AssertionError("Batch bake did not produce a result manifest")

    if args.success:
        operations.configure_baking(
            target,
            enabled=True,
            enabled_bakers=["AO"],
            enabled_uv_tiles=preset["enabled_uv_tiles"],
            common_values={"OutputSize": [8, 8], "SubSampling": 0},
            baker_values={"AO": {"NbSecondary": 8}},
            confirm=True,
        )
        try:
            success_job = operations.start_batch_bake([target], confirm=True)
            emit("success_batch_started", success_job)
            deadline = time.monotonic() + 300
            success_terminal = None
            while time.monotonic() < deadline:
                status = operations.get_bake_job(success_job["job_id"])
                emit("success_batch_status", status)
                if status["job"]["status"] not in {"starting", "running"}:
                    success_terminal = status["job"]
                    break
                time.sleep(0.5)
            if success_terminal is None or success_terminal["status"] != "success":
                raise AssertionError(f"Low-resolution batch bake failed: {success_terminal}")
            if not success_terminal["results"][target]["all_verified"]:
                raise AssertionError("Successful batch result manifest was not verified")
        finally:
            emit(
                "success_config_restored",
                operations.apply_baking_preset(target, preset, confirm=True),
            )

    baking_after = operations.inspect_baking()
    enabled_after = {
        item["texture_set"]: item["enabled"] for item in baking_after["texture_sets"]
    }
    emit("texture_set_enablement", {"before": enabled_before, "after": enabled_after})
    if enabled_after != enabled_before:
        raise AssertionError("Batch bake did not restore Texture Set enablement")


if __name__ == "__main__":
    main()
