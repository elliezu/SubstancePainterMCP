"""Live Painter smoke test. Use --write for reversible layer round trips."""

from __future__ import annotations

import argparse
import json

from substance_painter_mcp.client import PainterRemote
from substance_painter_mcp.operations import PainterOperations


def emit(label: str, value) -> None:
    print(label, json.dumps(value, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="Create, verify, and delete temporary test layers.",
    )
    parser.add_argument("--export-dir", help="Optional directory for a 256px PNG export test.")
    parser.add_argument("--export-preset", default="PBR Metallic Roughness")
    args = parser.parse_args()
    operations = PainterOperations(PainterRemote())
    emit("status", operations.status())
    emit("project", operations.project_info())
    emit("capabilities", operations.capabilities())
    emit("audit", operations.audit_project())
    emit("find_layers", operations.find_layers(query="Base"))
    emit("resource_search", operations.search_resources("p:starter_assets", limit=3))
    if args.export_dir:
        emit(
            "export_plan",
            operations.plan_texture_export(
                args.export_dir,
                args.export_preset,
                size_log2=8,
                file_format="png",
                bit_depth="8",
            ),
        )
        emit(
            "export_result",
            operations.export_textures(
                args.export_dir,
                args.export_preset,
                size_log2=8,
                file_format="png",
                bit_depth="8",
            ),
        )
    if not args.write:
        return

    created_uids: list[int] = []
    try:
        group = operations.create_group("__MCP_SMOKE_GROUP__")
        created_uids.append(group["uid"])
        fill = operations.create_fill_layer(
            "__MCP_SMOKE_FILL__",
            base_color=[0.15, 0.35, 0.55],
        )
        created_uids.append(fill["uid"])
        paint = operations.create_paint_layer("__MCP_SMOKE_PAINT__")
        created_uids.append(paint["uid"])
        emit("fill_color", operations.set_fill_base_color(fill["uid"], [0.8, 0.2, 0.1]))
        emit(
            "fill_channels",
            operations.set_fill_channels(
                fill["uid"], {"Roughness": 0.42, "BaseMetalness": 0.1}
            ),
        )
        emit("mask_added", operations.set_layer_mask(fill["uid"], True, "Black"))
        emit("mask_removed", operations.set_layer_mask(fill["uid"], False))
        emit(
            "paint_properties",
            operations.set_layer_properties(
                paint["uid"], visible=False, opacity=0.42, blending_mode="Multiply"
            ),
        )
        emit("selection", operations.select_layers([paint["uid"], fill["uid"]]))
    finally:
        for uid in reversed(created_uids):
            try:
                emit("cleanup", operations.delete_layer(uid))
            except Exception as exc:  # cleanup must continue for the remaining test nodes
                print("cleanup_error", uid, repr(exc))


if __name__ == "__main__":
    main()
