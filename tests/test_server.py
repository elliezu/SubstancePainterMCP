import asyncio

from substance_painter_mcp.server import mcp


def test_all_tools_register_with_fastmcp():
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert len(tools) == 75
    assert {
        "create_layer_recipe",
        "snapshot_layer_tree",
        "insert_mask_effect",
        "inspect_baking",
        "save_project_copy",
        "export_smart_material",
        "export_smart_mask",
        "export_with_profile",
        "get_geometry_mask",
        "set_geometry_mask",
        "plan_layer_recipe",
        "diff_layer_snapshots",
        "insert_smart_material",
        "apply_smart_mask",
        "get_fill_projection",
        "set_fill_projection",
        "get_fill_sources",
        "set_fill_resource",
        "set_fill_projection_advanced",
        "start_bake",
        "get_bake_job",
        "cancel_bake",
        "plan_mesh_reload",
        "start_mesh_reload",
        "get_mesh_reload_job",
        "get_fill_parameters",
        "set_fill_parameters",
        "apply_fill_preset",
        "list_anchor_points",
        "set_fill_anchor_source",
        "inspect_baking_parameters",
        "configure_baking",
        "set_baking_mesh_inputs",
        "capture_baking_preset",
        "apply_baking_preset",
        "preflight_bake",
        "start_batch_bake",
        "set_baking_resource_input",
        "import_project_resource",
        "import_session_resource",
        "get_procedural_inputs",
        "set_procedural_input",
        "plan_project_creation",
        "create_project",
        "get_project_creation_job",
        "save_project",
        "open_project",
    } <= names
