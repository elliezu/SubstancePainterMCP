"""FastMCP server for Adobe Substance 3D Painter."""

from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import PainterRemote
from .operations import PainterOperations


mcp = FastMCP(
    "Substance Painter",
    instructions=(
        "Control the locally running Adobe Substance 3D Painter instance. "
        "Use UIDs from list_layers for edits because layer names may be duplicated."
    ),
)
operations = PainterOperations(PainterRemote())


@mcp.tool()
def painter_status() -> dict[str, Any]:
    """Check the connection and report Painter, Python API, and project status."""
    return operations.status()


@mcp.tool()
def get_project_info() -> dict[str, Any]:
    """Return the current project path and texture-set names."""
    return operations.project_info()


@mcp.tool()
def get_capabilities() -> dict[str, Any]:
    """Report runtime-supported channels, blend modes, and version-sensitive features."""
    return operations.capabilities()


@mcp.tool()
def audit_project() -> dict[str, Any]:
    """Audit texture sets, channels, layer hygiene, and outdated resources."""
    return operations.audit_project()


@mcp.tool()
def list_layers(texture_set: str | None = None, recursive: bool = True) -> dict[str, Any]:
    """List layers with stable UIDs, types, visibility, and optional group children."""
    return operations.list_layers(texture_set=texture_set, recursive=recursive)


@mcp.tool()
def find_layers(
    query: str = "",
    node_type: str | None = None,
    visible: bool | None = None,
    texture_set: str | None = None,
) -> dict[str, Any]:
    """Search layers by partial name, exact node type, and visibility."""
    return operations.find_layers(query, node_type, visible, texture_set)


@mcp.tool()
def create_fill_layer(
    name: str,
    texture_set: str | None = None,
    base_color: list[float] | None = None,
) -> dict[str, Any]:
    """Create a top-level Fill Layer, optionally setting sRGB base color [r,g,b]."""
    return operations.create_fill_layer(name, texture_set, base_color)


@mcp.tool()
def create_group(name: str, texture_set: str | None = None) -> dict[str, Any]:
    """Create a top-level layer group."""
    return operations.create_group(name, texture_set)


@mcp.tool()
def create_paint_layer(name: str, texture_set: str | None = None) -> dict[str, Any]:
    """Create a top-level Paint Layer."""
    return operations.create_paint_layer(name, texture_set)


@mcp.tool()
def set_fill_base_color(uid: int, color: list[float]) -> dict[str, Any]:
    """Set a Fill Layer's base color using its UID and sRGB [r,g,b] values."""
    return operations.set_fill_base_color(uid, color)


@mcp.tool()
def set_fill_channels(
    uid: int,
    values: dict[str, float | list[float]],
) -> dict[str, Any]:
    """Set and enable multiple uniform Fill channels, such as Roughness or Metallic."""
    return operations.set_fill_channels(uid, values)


@mcp.tool()
def set_layer_mask(uid: int, enabled: bool, background: str = "Black") -> dict[str, Any]:
    """Add/update or remove a layer mask; backgrounds are reported by get_capabilities."""
    return operations.set_layer_mask(uid, enabled, background)


@mcp.tool()
def rename_layer(uid: int, name: str) -> dict[str, Any]:
    """Rename a layer or group by UID."""
    return operations.rename_layer(uid, name)


@mcp.tool()
def set_layer_properties(
    uid: int,
    visible: bool | None = None,
    opacity: float | None = None,
    blending_mode: str | None = None,
    channel: str | None = None,
) -> dict[str, Any]:
    """Set visibility, opacity, or blend mode; channel defaults to BaseColor."""
    return operations.set_layer_properties(uid, visible, opacity, blending_mode, channel)


@mcp.tool()
def select_layers(uids: list[int]) -> dict[str, Any]:
    """Select one or more layers in Painter by UID."""
    return operations.select_layers(uids)


@mcp.tool()
def list_export_presets() -> dict[str, Any]:
    """List built-in and shelf export presets without exporting files."""
    return operations.list_export_presets()


@mcp.tool()
def plan_texture_export(
    output_directory: str,
    preset: str,
    texture_sets: list[str] | None = None,
    size_log2: int | None = None,
    file_format: str | None = None,
    bit_depth: str | None = None,
) -> dict[str, Any]:
    """Validate an export and list exact output files without writing them."""
    return operations.plan_texture_export(
        output_directory, preset, texture_sets, size_log2, file_format, bit_depth
    )


@mcp.tool()
def export_textures(
    output_directory: str,
    preset: str,
    texture_sets: list[str] | None = None,
    size_log2: int | None = None,
    file_format: str | None = None,
    bit_depth: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Export textures inside SP_MCP_EXPORT_ROOTS and verify every output file."""
    return operations.export_textures(
        output_directory,
        preset,
        texture_sets,
        size_log2,
        file_format,
        bit_depth,
        overwrite,
    )


@mcp.tool()
def list_project_resources() -> dict[str, Any]:
    """List resources referenced by the open project."""
    return operations.list_project_resources()


@mcp.tool()
def search_resources(query: str, limit: int = 50) -> dict[str, Any]:
    """Search Painter resources and return identifiers, type, category, and usages."""
    return operations.search_resources(query, limit)


@mcp.tool()
def delete_layer(uid: int) -> dict[str, Any]:
    """Delete a layer or group by UID. This modifies the open project."""
    return operations.delete_layer(uid)


@mcp.tool()
def execute_python(code: str) -> dict[str, Any]:
    """Execute raw Painter Python only when SP_MCP_ALLOW_EXECUTE_PYTHON=1."""
    if os.getenv("SP_MCP_ALLOW_EXECUTE_PYTHON") != "1":
        raise PermissionError(
            "Raw Python execution is disabled. Set SP_MCP_ALLOW_EXECUTE_PYTHON=1 "
            "in the MCP server environment to opt in."
        )
    return operations.remote.execute_python_json(code)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
