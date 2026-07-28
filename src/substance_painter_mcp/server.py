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
def inspect_baking(texture_set: str | None = None) -> dict[str, Any]:
    """Inspect enabled bakers, UV tiles, and mesh-map assignments without starting a bake."""
    return operations.inspect_baking(texture_set)


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
def snapshot_layer_tree(texture_set: str | None = None) -> dict[str, Any]:
    """Capture a detailed layer/effect snapshot with a deterministic SHA-256 digest."""
    return operations.snapshot_layer_tree(texture_set)


@mcp.tool()
def diff_layer_snapshots(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    """Compare two layer snapshots by UID and report added, removed, and changed nodes."""
    return operations.diff_layer_snapshots(before, after)


@mcp.tool()
def get_geometry_mask(uid: int) -> dict[str, Any]:
    """Inspect a layer's Mesh/UVTile geometry mask and available elements."""
    return operations.get_geometry_mask(uid)


@mcp.tool()
def set_geometry_mask(
    uid: int,
    mask_type: str,
    elements: list[str | int],
    inclusion_list: bool = True,
) -> dict[str, Any]:
    """Set a geometry mask using mesh names or standard UDIM numbers."""
    return operations.set_geometry_mask(uid, mask_type, elements, inclusion_list)


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
def plan_layer_recipe(
    recipe: list[dict[str, Any]],
    texture_set: str | None = None,
    backup_path: str | None = None,
    backup_mode: str = "Incremental",
    overwrite_backup: bool = False,
) -> dict[str, Any]:
    """Validate a recipe, resolve channels, and preview backup/mutation scope without editing."""
    return operations.plan_layer_recipe(
        recipe, texture_set, backup_path, backup_mode, overwrite_backup
    )


@mcp.tool()
def create_layer_recipe(
    recipe: list[dict[str, Any]],
    texture_set: str | None = None,
    backup_path: str | None = None,
    backup_mode: str = "Incremental",
    overwrite_backup: bool = False,
) -> dict[str, Any]:
    """Create a nested recipe atomically, optionally saving an approved .spp backup first."""
    return operations.create_layer_recipe(
        recipe, texture_set, backup_path, backup_mode, overwrite_backup
    )


@mcp.tool()
def insert_smart_material(
    resource_url: str,
    texture_set: str | None = None,
    parent_uid: int | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """Insert a Smart Material resource at stack top or inside a group."""
    return operations.insert_smart_material(resource_url, texture_set, parent_uid, name)


@mcp.tool()
def apply_smart_mask(uid: int, resource_url: str) -> dict[str, Any]:
    """Apply a Smart Mask resource to a layer using transactional mask insertion."""
    return operations.apply_smart_mask(uid, resource_url)


@mcp.tool()
def set_fill_base_color(uid: int, color: list[float]) -> dict[str, Any]:
    """Set a Fill Layer's base color using its UID and sRGB [r,g,b] values."""
    return operations.set_fill_base_color(uid, color)


@mcp.tool()
def get_fill_projection(uid: int) -> dict[str, Any]:
    """Inspect a Fill layer's projection mode and common UV transformation."""
    return operations.get_fill_projection(uid)


@mcp.tool()
def set_fill_projection(
    uid: int,
    mode: str,
    scale: list[float] | None = None,
    rotation: float | None = None,
    offset: list[float] | None = None,
) -> dict[str, Any]:
    """Set Fill, UV, or Triplanar projection with transactional transform updates."""
    return operations.set_fill_projection(uid, mode, scale, rotation, offset)


@mcp.tool()
def set_fill_channels(
    uid: int,
    values: dict[str, float | list[float]],
) -> dict[str, Any]:
    """Set and enable multiple uniform Fill channels, such as Roughness or Metallic."""
    return operations.set_fill_channels(uid, values)


@mcp.tool()
def set_active_channels(uid: int, channels: list[str]) -> dict[str, Any]:
    """Replace a Fill or Paint layer's active channel set by UID."""
    return operations.set_active_channels(uid, channels)


@mcp.tool()
def set_layer_mask(uid: int, enabled: bool, background: str = "Black") -> dict[str, Any]:
    """Add/update or remove a layer mask; backgrounds are reported by get_capabilities."""
    return operations.set_layer_mask(uid, enabled, background)


@mcp.tool()
def insert_mask_effect(
    uid: int,
    effect_type: str,
    resource_url: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """Insert Fill, Paint, Generator, Filter, Levels, Anchor, or Smart Mask content."""
    return operations.insert_mask_effect(uid, effect_type, resource_url, name)


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
def inspect_export_preset(
    preset: str,
    texture_set: str | None = None,
) -> dict[str, Any]:
    """Resolve an export preset and preview its map names without writing files."""
    return operations.inspect_export_preset(preset, texture_set)


@mcp.tool()
def list_export_profiles() -> dict[str, Any]:
    """List curated engine export profiles and whether their Painter presets are available."""
    return operations.list_export_profiles()


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
def plan_profile_export(
    output_directory: str,
    profile: str,
    texture_sets: list[str] | None = None,
    size_log2: int | None = None,
) -> dict[str, Any]:
    """Preview an engine-profile texture export without writing files."""
    return operations.plan_profile_export(output_directory, profile, texture_sets, size_log2)


@mcp.tool()
def export_with_profile(
    output_directory: str,
    profile: str,
    texture_sets: list[str] | None = None,
    size_log2: int | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Run a curated export profile inside SP_MCP_EXPORT_ROOTS and verify outputs."""
    return operations.export_with_profile(
        output_directory, profile, texture_sets, size_log2, overwrite
    )


@mcp.tool()
def list_project_resources() -> dict[str, Any]:
    """List resources referenced by the open project."""
    return operations.list_project_resources()


@mcp.tool()
def search_resources(
    query: str,
    limit: int = 50,
    resource_type: str | None = None,
    usage: str | None = None,
) -> dict[str, Any]:
    """Search Painter resources and return identifiers, type, category, and usages."""
    return operations.search_resources(query, limit, resource_type, usage)


@mcp.tool()
def find_outdated_resources() -> dict[str, Any]:
    """Plan project-resource replacements without modifying the project."""
    return operations.find_outdated_resources()


@mcp.tool()
def replace_outdated_resources(confirm: bool = False) -> dict[str, Any]:
    """Atomically replace all outdated resources after explicit confirm=true."""
    return operations.replace_outdated_resources(confirm)


@mcp.tool()
def save_project_copy(
    output_path: str,
    mode: str = "Incremental",
    overwrite: bool = False,
) -> dict[str, Any]:
    """Save a verified .spp copy inside SP_MCP_PROJECT_ROOTS without relocating the project."""
    return operations.save_project_copy(output_path, mode, overwrite)


@mcp.tool()
def export_smart_material(
    uid: int,
    name: str,
    output_directory: str,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Export a group as a verified Smart Material inside SP_MCP_EXPORT_ROOTS."""
    return operations.export_smart_material(uid, name, output_directory, overwrite)


@mcp.tool()
def export_smart_mask(
    uid: int,
    name: str,
    output_directory: str,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Export a layer mask as a verified Smart Mask inside SP_MCP_EXPORT_ROOTS."""
    return operations.export_smart_mask(uid, name, output_directory, overwrite)


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
