"""Live validation for v0.8 sandboxed resource and image-input workflows."""

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
    parser.add_argument("--image", required=True)
    args = parser.parse_args()

    operations = PainterOperations(PainterRemote())
    stamp = str(int(time.time()))
    project_resource = operations.import_project_resource(
        args.image,
        "TEXTURE",
        name=f"MCP_v08_project_{stamp}",
        group="MCP Validation",
        confirm=True,
    )
    session_resource = operations.import_session_resource(
        args.image,
        "TEXTURE",
        name=f"MCP_v08_session_{stamp}",
        group="MCP Validation",
        confirm=True,
    )
    emit("project_resource", project_resource)
    emit("session_resource", session_resource)
    if not project_resource["verified"] or project_resource["location"] != "PROJECT":
        raise AssertionError("Project resource import was not verified")
    if not session_resource["verified"] or session_resource["location"] != "SESSION":
        raise AssertionError("Session resource import was not verified")

    baking = operations.inspect_baking()
    target = next(
        item["texture_set"]
        for item in baking["texture_sets"]
        if item["enabled"] and item["enabled_uv_tiles"]
    )
    original_offset = operations.inspect_baking_parameters(target)["common"]["OffsetMap"][
        "value"
    ]
    layer_before = operations.snapshot_layer_tree(target)
    temporary_uid = None
    try:
        offset = operations.set_baking_resource_input(
            target,
            "OffsetMap",
            project_resource["url"],
            confirm=True,
        )
        emit("offset_map", offset)
        if offset["resource_url"] != project_resource["url"]:
            raise AssertionError("OffsetMap did not retain the imported resource URL")

        created = operations.create_fill_layer("MCP v0.8 Imported Bitmap", target)
        temporary_uid = created["uid"]
        assigned = operations.set_fill_resource(
            temporary_uid, project_resource["url"], "BaseColor"
        )
        sources = operations.get_fill_sources(temporary_uid)
        emit("fill_assignment", {"assigned": assigned, "sources": sources})
        if sources["channels"]["BaseColor"]["resource_url"] != project_resource["url"]:
            raise AssertionError("Imported bitmap was not connected to the Fill")

        generators = operations.search_resources(
            "Mask Editor", limit=5, usage="GENERATOR"
        )["resources"]
        if not generators:
            raise AssertionError("Starter Mask Editor Generator was not found")
        effect = operations.insert_mask_effect(
            temporary_uid, "generator", generators[0]["url"]
        )["effects"][0]
        inspected = operations.get_procedural_inputs(effect["uid"])
        if not inspected["inputs"]:
            raise AssertionError("Mask Editor exposed no procedural image inputs")
        input_name, original = next(iter(inspected["inputs"].items()))
        updated = operations.set_procedural_input(
            effect["uid"], input_name, project_resource["url"]
        )
        if updated["source"]["resource_url"] != project_resource["url"]:
            raise AssertionError("Procedural image input did not retain the resource URL")
        restored = operations.set_procedural_input(
            effect["uid"], input_name, reset=True
        )
        emit(
            "procedural_image_input",
            {
                "uid": effect["uid"],
                "node_type": inspected["node_type"],
                "input": input_name,
                "before": original,
                "updated": updated["source"],
                "reset": restored["source"],
            },
        )
    finally:
        if temporary_uid is not None:
            operations.delete_layer(temporary_uid)
        if original_offset:
            operations.set_baking_resource_input(
                target, "OffsetMap", original_offset, confirm=True
            )
        else:
            operations.set_baking_resource_input(
                target, "OffsetMap", clear=True, confirm=True
            )

    layer_after = operations.snapshot_layer_tree(target)
    if layer_before["sha256"] != layer_after["sha256"]:
        raise AssertionError("Temporary Fill cleanup did not restore the layer tree")
    restored_offset = operations.inspect_baking_parameters(target)["common"]["OffsetMap"][
        "value"
    ]
    if restored_offset != original_offset:
        raise AssertionError("OffsetMap was not restored")
    emit(
        "restored",
        {
            "layer_digest": layer_after["sha256"],
            "offset_map": restored_offset,
            "project_resource_persisted": project_resource["url"],
            "session_resource": session_resource["url"],
        },
    )


if __name__ == "__main__":
    main()
