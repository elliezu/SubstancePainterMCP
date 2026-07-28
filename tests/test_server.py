import asyncio

from substance_painter_mcp.server import mcp


def test_all_tools_register_with_fastmcp():
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert len(tools) == 36
    assert {
        "create_layer_recipe",
        "snapshot_layer_tree",
        "insert_mask_effect",
        "inspect_baking",
        "save_project_copy",
        "export_smart_material",
        "export_smart_mask",
        "export_with_profile",
    } <= names
