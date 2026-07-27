"""Painter operations used by MCP tools."""

from __future__ import annotations

from collections import Counter
import os
from pathlib import Path
from typing import Any

from .client import PainterRemote, PainterScriptError


def _unwrap(envelope: dict[str, Any]) -> Any:
    if envelope.get("success"):
        return envelope.get("data")
    error_type = envelope.get("error_type", "PainterError")
    message = envelope.get("error", "Unknown Painter error")
    raise PainterScriptError(f"{error_type}: {message}")


class PainterOperations:
    def __init__(self, remote: PainterRemote):
        self.remote = remote

    def status(self) -> dict[str, Any]:
        app_version = self.remote.check_connection()
        api = self.remote.execute_python("__import__('substance_painter').__version__")
        project_open = bool(self.remote.execute_js("alg.project.isOpen()"))
        return {
            "connected": True,
            "painter_version": app_version,
            "python_api_version": str(api),
            "project_open": project_open,
            "host": self.remote.config.host,
            "port": self.remote.config.port,
        }

    def project_info(self) -> dict[str, Any]:
        code = '''
import substance_painter.project as project
import substance_painter.textureset as textureset

if not project.is_open():
    result = {"open": False, "name": None, "path": None, "texture_sets": []}
else:
    texture_sets = []
    for item in textureset.all_texture_sets():
        name_attr = item.name
        texture_sets.append(name_attr() if callable(name_attr) else name_attr)
    result = {
        "open": True,
        "name": project.name(),
        "path": str(project.file_path()) if project.file_path() else None,
        "texture_sets": texture_sets,
    }
'''
        return _unwrap(self.remote.execute_python_json(code))

    def capabilities(self) -> dict[str, Any]:
        code = '''
import substance_painter.baking as baking
import substance_painter.export as export
import substance_painter.layerstack as layerstack
import substance_painter.project as project
import substance_painter.textureset as textureset

result = {
    "blending_modes": list(layerstack.BlendingMode.__members__),
    "channel_types": list(textureset.ChannelType.__members__),
    "mask_backgrounds": list(layerstack.MaskBackground.__members__),
    "insert_positions": [name for name in ("above_node", "below_node", "inside_node")
                         if hasattr(layerstack.InsertPosition, name)],
    "features": {
        "geometry_mask_v2": hasattr(layerstack.LayerNode, "set_geometry_mask"),
        "smart_material_file_export": hasattr(layerstack, "export_as_smart_material"),
        "predefined_export_presets": hasattr(export, "list_predefined_export_presets"),
        "async_baking": hasattr(baking, "bake_selected_textures_async"),
        "auto_unwrap_settings": hasattr(project, "AutoUnwrapUVTilesSettings"),
    },
}
'''
        return _unwrap(self.remote.execute_python_json(code))

    def audit_project(self) -> dict[str, Any]:
        project = self.project_info()
        if not project["open"]:
            return {"project": project, "issues": [{"severity": "error", "code": "no_project"}]}
        tree = self.list_layers(recursive=True)
        code = '''
import substance_painter.project as project
import substance_painter.resource as resource
import substance_painter.textureset as textureset

texture_sets = []
for item in textureset.all_texture_sets():
    name = item.name() if callable(item.name) else item.name
    resolution = item.get_resolution()
    stacks = []
    for stack in item.all_stacks():
        stacks.append({
            "name": stack.name(),
            "channels": [channel.name for channel in stack.all_channels()],
        })
    texture_sets.append({
        "name": name,
        "resolution": [resolution.width, resolution.height],
        "stacks": stacks,
    })
outdated = []
if hasattr(resource, "list_project_outdated_resources"):
    for old, new in resource.list_project_outdated_resources().items():
        outdated.append({"current": old.url(), "available": new.url()})
result = {"busy": project.is_busy(), "texture_sets": texture_sets, "outdated_resources": outdated}
'''
        technical = _unwrap(self.remote.execute_python_json(code))
        flat: list[dict[str, Any]] = []

        def visit(nodes: list[dict[str, Any]]) -> None:
            for node in nodes:
                flat.append(node)
                visit(node.get("children", []))

        visit(tree["layers"])
        duplicate_names = sorted(
            name for name, count in Counter(node["name"] for node in flat).items() if count > 1
        )
        empty_groups = [
            {"uid": node["uid"], "name": node["name"]}
            for node in flat
            if node["type"] == "GroupLayerNode" and not node.get("children")
        ]
        hidden = [
            {"uid": node["uid"], "name": node["name"]}
            for node in flat
            if not node["visible"]
        ]
        issues = []
        if duplicate_names:
            issues.append({"severity": "info", "code": "duplicate_layer_names", "names": duplicate_names})
        if empty_groups:
            issues.append({"severity": "warning", "code": "empty_groups", "layers": empty_groups})
        if technical["outdated_resources"]:
            issues.append(
                {
                    "severity": "warning",
                    "code": "outdated_resources",
                    "count": len(technical["outdated_resources"]),
                }
            )
        return {
            "project": project,
            "texture_sets": technical["texture_sets"],
            "layer_count": len(flat),
            "hidden_layers": hidden,
            "outdated_resources": technical["outdated_resources"],
            "busy": technical["busy"],
            "issues": issues,
        }

    def list_layers(
        self,
        texture_set: str | None = None,
        recursive: bool = True,
    ) -> dict[str, Any]:
        code = '''
import substance_painter.layerstack as layerstack
import substance_painter.textureset as textureset

stack = (textureset.TextureSet.from_name(params["texture_set"]).get_stack()
         if params.get("texture_set") else textureset.get_active_stack())

def describe(node):
    item = {
        "uid": node.uid(),
        "name": node.get_name(),
        "type": type(node).__name__,
        "visible": node.is_visible(),
    }
    if params["recursive"] and isinstance(node, layerstack.GroupLayerNode):
        item["children"] = [describe(child) for child in node.sub_layers()]
    return item

material = stack.material()
material_name = material.name() if callable(material.name) else material.name
result = {
    "texture_set": material_name,
    "stack": stack.name(),
    "layers": [describe(node) for node in layerstack.get_root_layer_nodes(stack)],
}
'''
        return _unwrap(
            self.remote.execute_python_json(
                code,
                {"texture_set": texture_set, "recursive": recursive},
            )
        )

    def find_layers(
        self,
        query: str = "",
        node_type: str | None = None,
        visible: bool | None = None,
        texture_set: str | None = None,
    ) -> dict[str, Any]:
        tree = self.list_layers(texture_set=texture_set, recursive=True)
        matches: list[dict[str, Any]] = []
        normalized_query = query.casefold()

        def visit(nodes: list[dict[str, Any]], parents: list[str]) -> None:
            for node in nodes:
                name_matches = not normalized_query or normalized_query in node["name"].casefold()
                type_matches = node_type is None or node["type"] == node_type
                visibility_matches = visible is None or node["visible"] is visible
                if name_matches and type_matches and visibility_matches:
                    matches.append({**{k: v for k, v in node.items() if k != "children"}, "parents": parents})
                visit(node.get("children", []), [*parents, node["name"]])

        visit(tree["layers"], [])
        return {"texture_set": tree["texture_set"], "count": len(matches), "layers": matches}

    def create_fill_layer(
        self,
        name: str,
        texture_set: str | None = None,
        base_color: list[float] | None = None,
    ) -> dict[str, Any]:
        if base_color is not None:
            self._validate_color(base_color)
        code = '''
import substance_painter.colormanagement as colormanagement
import substance_painter.layerstack as layerstack
import substance_painter.textureset as textureset

stack = (textureset.TextureSet.from_name(params["texture_set"]).get_stack()
         if params.get("texture_set") else textureset.get_active_stack())
position = layerstack.InsertPosition.from_textureset_stack(stack)
node = layerstack.insert_fill(position)
node.set_name(params["name"])
if params.get("base_color") is not None:
    node.set_source(
        textureset.ChannelType.BaseColor,
        colormanagement.Color(*params["base_color"]),
    )
result = {"uid": node.uid(), "name": node.get_name(), "type": type(node).__name__}
'''
        return _unwrap(
            self.remote.execute_python_json(
                code,
                {"name": name, "texture_set": texture_set, "base_color": base_color},
            )
        )

    def create_group(self, name: str, texture_set: str | None = None) -> dict[str, Any]:
        code = '''
import substance_painter.layerstack as layerstack
import substance_painter.textureset as textureset

stack = (textureset.TextureSet.from_name(params["texture_set"]).get_stack()
         if params.get("texture_set") else textureset.get_active_stack())
node = layerstack.insert_group(layerstack.InsertPosition.from_textureset_stack(stack))
node.set_name(params["name"])
result = {"uid": node.uid(), "name": node.get_name(), "type": type(node).__name__}
'''
        return _unwrap(
            self.remote.execute_python_json(code, {"name": name, "texture_set": texture_set})
        )

    def create_paint_layer(self, name: str, texture_set: str | None = None) -> dict[str, Any]:
        code = '''
import substance_painter.layerstack as layerstack
import substance_painter.textureset as textureset

stack = (textureset.TextureSet.from_name(params["texture_set"]).get_stack()
         if params.get("texture_set") else textureset.get_active_stack())
node = layerstack.insert_paint(layerstack.InsertPosition.from_textureset_stack(stack))
node.set_name(params["name"])
result = {"uid": node.uid(), "name": node.get_name(), "type": type(node).__name__}
'''
        return _unwrap(
            self.remote.execute_python_json(code, {"name": name, "texture_set": texture_set})
        )

    def set_fill_base_color(self, uid: int, color: list[float]) -> dict[str, Any]:
        self._validate_color(color)
        code = '''
import substance_painter.colormanagement as colormanagement
import substance_painter.layerstack as layerstack
import substance_painter.textureset as textureset

node = layerstack.get_node_by_uid(params["uid"])
if not isinstance(node, layerstack.FillLayerNode):
    raise TypeError(f"Node {params['uid']} is not a FillLayerNode")
source = node.set_source(
    textureset.ChannelType.BaseColor,
    colormanagement.Color(*params["color"]),
)
verified = source.get_color()
result = {
    "uid": node.uid(),
    "name": node.get_name(),
    "requested_srgb": params["color"],
    "stored_working_color": list(verified.value_raw),
    "color_space": str(verified.color_space),
}
'''
        return _unwrap(self.remote.execute_python_json(code, {"uid": uid, "color": color}))

    def set_fill_channels(
        self,
        uid: int,
        values: dict[str, float | list[float]],
    ) -> dict[str, Any]:
        if not values:
            raise ValueError("values must contain at least one channel")
        normalized: dict[str, list[float]] = {}
        for channel, value in values.items():
            color = [float(value)] * 3 if isinstance(value, (int, float)) else list(value)
            self._validate_color(color)
            normalized[channel] = color
        code = '''
import substance_painter.colormanagement as colormanagement
import substance_painter.layerstack as layerstack
import substance_painter.textureset as textureset

node = layerstack.get_node_by_uid(params["uid"])
if not isinstance(node, layerstack.FillLayerNode):
    raise TypeError(f"Node {params['uid']} is not a FillLayerNode")
resolved = {}
for name, color in params["values"].items():
    if name not in textureset.ChannelType.__members__:
        raise ValueError(f"Unknown channel: {name}")
    resolved[textureset.ChannelType.__members__[name]] = color
node.active_channels = set(node.active_channels) | set(resolved)
verified = {}
for channel, color in resolved.items():
    source = node.set_source(channel, colormanagement.Color(*color))
    verified[channel.name] = {
        "requested": color,
        "stored": list(source.get_color().value_raw),
        "color_space": str(source.get_color().color_space),
    }
result = {
    "uid": node.uid(),
    "name": node.get_name(),
    "active_channels": sorted(channel.name for channel in node.active_channels),
    "values": verified,
}
'''
        return _unwrap(
            self.remote.execute_python_json(code, {"uid": uid, "values": normalized})
        )

    def set_layer_mask(
        self,
        uid: int,
        enabled: bool,
        background: str = "Black",
    ) -> dict[str, Any]:
        code = '''
import substance_painter.layerstack as layerstack

node = layerstack.get_node_by_uid(params["uid"])
if not isinstance(node, layerstack.LayerNode):
    raise TypeError(f"Node {params['uid']} does not support a mask")
if params["background"] not in layerstack.MaskBackground.__members__:
    raise ValueError(f"Unknown mask background: {params['background']}")
background = layerstack.MaskBackground.__members__[params["background"]]
if params["enabled"]:
    if node.has_mask():
        node.set_mask_background(background)
    else:
        node.add_mask(background)
elif node.has_mask():
    node.remove_mask()
result = {
    "uid": node.uid(),
    "name": node.get_name(),
    "has_mask": node.has_mask(),
    "background": node.get_mask_background().name if node.has_mask() else None,
}
'''
        return _unwrap(
            self.remote.execute_python_json(
                code,
                {"uid": uid, "enabled": enabled, "background": background},
            )
        )

    def rename_layer(self, uid: int, name: str) -> dict[str, Any]:
        code = '''
import substance_painter.layerstack as layerstack
node = layerstack.get_node_by_uid(params["uid"])
old_name = node.get_name()
node.set_name(params["name"])
result = {"uid": node.uid(), "old_name": old_name, "name": node.get_name()}
'''
        return _unwrap(self.remote.execute_python_json(code, {"uid": uid, "name": name}))

    def set_layer_properties(
        self,
        uid: int,
        visible: bool | None = None,
        opacity: float | None = None,
        blending_mode: str | None = None,
        channel: str | None = None,
    ) -> dict[str, Any]:
        if opacity is not None and not 0 <= opacity <= 1:
            raise ValueError("opacity must be in the 0..1 range")
        code = '''
import substance_painter.layerstack as layerstack
import substance_painter.textureset as textureset

node = layerstack.get_node_by_uid(params["uid"])
channel_name = params.get("channel") or "BaseColor"
if channel_name not in textureset.ChannelType.__members__:
    raise ValueError(f"Unknown channel: {channel_name}")
channel = textureset.ChannelType.__members__[channel_name]
if params.get("visible") is not None:
    node.set_visible(params["visible"])
if params.get("opacity") is not None:
    node.set_opacity(params["opacity"], channel)
if params.get("blending_mode"):
    if params["blending_mode"] not in layerstack.BlendingMode.__members__:
        raise ValueError(f"Unknown blending mode: {params['blending_mode']}")
    node.set_blending_mode(layerstack.BlendingMode.__members__[params["blending_mode"]], channel)
result = {
    "uid": node.uid(),
    "name": node.get_name(),
    "visible": node.is_visible(),
    "opacity": node.get_opacity(channel),
    "blending_mode": node.get_blending_mode(channel).name,
    "channel": channel_name,
}
'''
        return _unwrap(
            self.remote.execute_python_json(
                code,
                {
                    "uid": uid,
                    "visible": visible,
                    "opacity": opacity,
                    "blending_mode": blending_mode,
                    "channel": channel,
                },
            )
        )

    def select_layers(self, uids: list[int]) -> dict[str, Any]:
        if not uids:
            raise ValueError("uids must contain at least one layer UID")
        code = '''
import substance_painter.layerstack as layerstack
nodes = [layerstack.get_node_by_uid(uid) for uid in params["uids"]]
layerstack.set_selected_nodes(nodes)
result = [{"uid": node.uid(), "name": node.get_name(), "type": type(node).__name__}
          for node in nodes]
'''
        return {"selected": _unwrap(self.remote.execute_python_json(code, {"uids": uids}))}

    def list_export_presets(self) -> dict[str, Any]:
        code = '''
import substance_painter.export as export

predefined = [
    {"kind": "predefined", "name": preset.name, "url": preset.url}
    for preset in export.list_predefined_export_presets()
]
shelf = []
for preset in export.list_resource_export_presets():
    resource_id = preset.resource_id
    shelf.append({
        "kind": "shelf",
        "name": resource_id.name,
        "context": resource_id.context,
        "url": resource_id.url(),
    })
result = {"predefined": predefined, "shelf": shelf}
'''
        return _unwrap(self.remote.execute_python_json(code))

    def plan_texture_export(
        self,
        output_directory: str,
        preset: str,
        texture_sets: list[str] | None = None,
        size_log2: int | None = None,
        file_format: str | None = None,
        bit_depth: str | None = None,
    ) -> dict[str, Any]:
        output = self._validate_export_directory(output_directory)
        if size_log2 is not None and not 5 <= size_log2 <= 14:
            raise ValueError("size_log2 must be in the 5..14 range")
        if file_format is not None and file_format.lower() not in {
            "png", "tga", "jpg", "jpeg", "tif", "tiff", "exr", "bmp"
        }:
            raise ValueError("unsupported file_format")
        if bit_depth is not None and bit_depth not in {"8", "16", "32"}:
            raise ValueError("bit_depth must be 8, 16, or 32")
        selected_sets = texture_sets or self.project_info()["texture_sets"]
        if not selected_sets:
            raise ValueError("no texture sets selected")
        parameters: dict[str, Any] = {
            "dithering": True,
            "paddingAlgorithm": "infinite",
        }
        if size_log2 is not None:
            parameters["sizeLog2"] = size_log2
        if file_format is not None:
            parameters["fileFormat"] = file_format.lower()
        if bit_depth is not None:
            parameters["bitDepth"] = bit_depth
        code = '''
import os
import substance_painter.export as export

preset_input = params["preset"]
preset_url = preset_input if "://" in preset_input else None
preset_name = preset_input
if preset_url is None:
    for item in export.list_predefined_export_presets():
        if item.name.casefold() == preset_input.casefold():
            preset_url, preset_name = item.url, item.name
            break
if preset_url is None:
    for item in export.list_resource_export_presets():
        if item.resource_id.name.casefold() == preset_input.casefold():
            preset_url, preset_name = item.resource_id.url(), item.resource_id.name
            break
if preset_url is None:
    raise ValueError(f"Export preset not found: {preset_input}")

config = {
    "exportShaderParams": False,
    "exportPath": params["output_directory"],
    "defaultExportPreset": preset_url,
    "exportList": [{"rootPath": name} for name in params["texture_sets"]],
}
if params["parameters"]:
    config["exportParameters"] = [{"parameters": params["parameters"]}]
listed = export.list_project_textures(config)
groups = []
files = []
for (texture_set, stack), paths in listed.items():
    groups.append({"texture_set": texture_set, "stack": stack, "files": paths})
    files.extend(paths)
result = {
    "preset": {"name": preset_name, "url": preset_url},
    "config": config,
    "groups": groups,
    "files": files,
    "conflicts": [path for path in files if os.path.exists(path)],
}
'''
        return _unwrap(
            self.remote.execute_python_json(
                code,
                {
                    "output_directory": output.as_posix(),
                    "preset": preset,
                    "texture_sets": selected_sets,
                    "parameters": parameters,
                },
            )
        )

    def export_textures(
        self,
        output_directory: str,
        preset: str,
        texture_sets: list[str] | None = None,
        size_log2: int | None = None,
        file_format: str | None = None,
        bit_depth: str | None = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        plan = self.plan_texture_export(
            output_directory,
            preset,
            texture_sets,
            size_log2,
            file_format,
            bit_depth,
        )
        if plan["conflicts"] and not overwrite:
            raise FileExistsError(
                f"{len(plan['conflicts'])} export files already exist; set overwrite=true to replace them"
            )
        code = '''
import substance_painter.export as export
exported = export.export_project_textures(params["config"])
groups = []
files = []
for (texture_set, stack), paths in exported.textures.items():
    groups.append({"texture_set": texture_set, "stack": stack, "files": paths})
    files.extend(paths)
result = {
    "status": exported.status.name,
    "message": exported.message,
    "groups": groups,
    "files": files,
}
'''
        result = _unwrap(self.remote.execute_python_json(code, {"config": plan["config"]}))
        result["preset"] = plan["preset"]
        result["verification"] = [
            {
                "path": path,
                "exists": Path(path).is_file(),
                "bytes": Path(path).stat().st_size if Path(path).is_file() else None,
            }
            for path in result["files"]
        ]
        return result

    def list_project_resources(self) -> dict[str, Any]:
        code = '''
import substance_painter.resource as resource
resources = resource.list_project_resources()
result = {
    "count": len(resources),
    "resources": [
        {
            "name": item.name,
            "context": item.context,
            "version": item.version,
            "url": item.url(),
        }
        for item in resources
    ],
}
'''
        return _unwrap(self.remote.execute_python_json(code))

    def search_resources(self, query: str, limit: int = 50) -> dict[str, Any]:
        if not query.strip():
            raise ValueError("query must not be empty")
        if not 1 <= limit <= 200:
            raise ValueError("limit must be in the 1..200 range")
        code = '''
import substance_painter.resource as resource
items = resource.search(params["query"])
result = {
    "total": len(items),
    "truncated": len(items) > params["limit"],
    "resources": [
        {
            "name": item.identifier().name,
            "context": item.identifier().context,
            "url": item.identifier().url(),
            "type": item.type().name,
            "category": item.category(),
            "usages": [usage.name for usage in item.usages()],
        }
        for item in items[:params["limit"]]
    ],
}
'''
        return _unwrap(
            self.remote.execute_python_json(code, {"query": query, "limit": limit})
        )

    @staticmethod
    def _validate_export_directory(output_directory: str) -> Path:
        configured = os.getenv("SP_MCP_EXPORT_ROOTS", "")
        roots = [Path(item).expanduser().resolve() for item in configured.split(os.pathsep) if item]
        if not roots:
            raise PermissionError(
                "Texture export is disabled. Set SP_MCP_EXPORT_ROOTS to one or more allowed roots."
            )
        output = Path(output_directory).expanduser().resolve()
        output_key = os.path.normcase(str(output))
        for root in roots:
            root_key = os.path.normcase(str(root))
            try:
                if os.path.commonpath([output_key, root_key]) == root_key:
                    return output
            except ValueError:
                continue
        raise PermissionError(f"Export path is outside SP_MCP_EXPORT_ROOTS: {output}")

    def delete_layer(self, uid: int) -> dict[str, Any]:
        code = '''
import substance_painter.layerstack as layerstack
node = layerstack.get_node_by_uid(params["uid"])
deleted = {"uid": node.uid(), "name": node.get_name(), "type": type(node).__name__}
layerstack.delete_node(node)
result = deleted
'''
        return _unwrap(self.remote.execute_python_json(code, {"uid": uid}))

    @staticmethod
    def _validate_color(color: list[float]) -> None:
        if len(color) != 3 or any(not isinstance(value, (int, float)) for value in color):
            raise ValueError("color must contain exactly three numbers")
        if any(value < 0 or value > 1 for value in color):
            raise ValueError("color components must be in the 0..1 range")
