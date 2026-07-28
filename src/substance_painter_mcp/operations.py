"""Painter operations used by MCP tools."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

from .client import PainterRemote, PainterScriptError


EXPORT_PROFILES: dict[str, dict[str, Any]] = {
    "generic-pbr": {
        "preset": "PBR Metallic Roughness",
        "file_format": "png",
        "bit_depth": "8",
        "description": "Portable metallic/roughness PBR maps.",
    },
    "vrchat-pbr": {
        "preset": "PBR Metallic Roughness",
        "file_format": "png",
        "bit_depth": "8",
        "description": "Separate PBR maps suitable for manual VRChat shader packing.",
    },
    "blender": {
        "preset": "Blender (Principled BSDF)",
        "file_format": "png",
        "bit_depth": "8",
        "description": "Maps named for Blender's Principled BSDF workflow.",
    },
    "unity-hdrp": {
        "preset": "Unity HD Render Pipeline (Metallic Standard)",
        "file_format": "png",
        "bit_depth": "8",
        "description": "Packed textures for Unity HDRP metallic workflows.",
    },
    "unity-urp": {
        "preset": "Unity Universal Render Pipeline (Metallic Standard)",
        "file_format": "png",
        "bit_depth": "8",
        "description": "Packed textures for Unity URP metallic workflows.",
    },
    "unreal-engine": {
        "preset": "Unreal Engine (Packed)",
        "file_format": "png",
        "bit_depth": "8",
        "description": "Packed textures for Unreal Engine metallic workflows.",
    },
}


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
        "smart_mask_file_export": hasattr(layerstack, "export_as_smart_mask"),
        "mask_effect_insertion": hasattr(layerstack, "insert_generator_effect"),
        "predefined_export_presets": hasattr(export, "list_predefined_export_presets"),
        "async_baking": hasattr(baking, "bake_selected_textures_async"),
        "auto_unwrap_settings": hasattr(project, "AutoUnwrapUVTilesSettings"),
        "save_project_copy": hasattr(project, "save_as_copy"),
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

    def inspect_baking(self, texture_set: str | None = None) -> dict[str, Any]:
        code = '''
import substance_painter.baking as baking
import substance_painter.project as project
import substance_painter.textureset as textureset

sets = ([textureset.TextureSet.from_name(params["texture_set"])]
        if params.get("texture_set") else textureset.all_texture_sets())
entries = []
for item in sets:
    name = item.name() if callable(item.name) else item.name
    settings = baking.BakingParameters.from_texture_set(item)
    mesh_maps = []
    for usage_name, usage in textureset.MeshMapUsage.__members__.items():
        resource_id = item.get_mesh_map_resource(usage)
        mesh_maps.append({
            "usage": usage_name,
            "resource": resource_id.url() if resource_id else None,
            "baker_enabled": settings.is_baker_enabled(usage),
        })
    entries.append({
        "texture_set": name,
        "enabled": settings.is_textureset_enabled(),
        "curvature_method": settings.get_curvature_method().name,
        "enabled_bakers": [usage.name for usage in settings.get_enabled_bakers()],
        "uv_tiles": [str(tile) for tile in item.all_uv_tiles()],
        "enabled_uv_tiles": [str(tile) for tile in settings.get_enabled_uv_tiles()],
        "mesh_maps": mesh_maps,
    })
result = {"busy": project.is_busy(), "texture_sets": entries}
'''
        return _unwrap(
            self.remote.execute_python_json(code, {"texture_set": texture_set})
        )

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

    def snapshot_layer_tree(self, texture_set: str | None = None) -> dict[str, Any]:
        """Return a detailed, deterministic snapshot suitable for before/after comparisons."""
        code = '''
import substance_painter.layerstack as layerstack
import substance_painter.textureset as textureset

stack = (textureset.TextureSet.from_name(params["texture_set"]).get_stack()
         if params.get("texture_set") else textureset.get_active_stack())

def effect_info(effect):
    return {
        "uid": effect.uid(),
        "name": effect.get_name(),
        "type": type(effect).__name__,
        "visible": effect.is_visible(),
    }

def describe(node):
    item = {
        "uid": node.uid(),
        "name": node.get_name(),
        "type": type(node).__name__,
        "visible": node.is_visible(),
        "mask": {
            "present": node.has_mask(),
            "enabled": node.is_mask_enabled() if node.has_mask() else False,
            "background": node.get_mask_background().name if node.has_mask() else None,
            "effects": [effect_info(effect) for effect in node.mask_effects()] if node.has_mask() else [],
        },
        "content_effects": [effect_info(effect) for effect in node.content_effects()],
    }
    if isinstance(node, layerstack.FillLayerNode):
        item["active_channels"] = sorted(channel.name for channel in node.active_channels)
    if isinstance(node, layerstack.GroupLayerNode):
        item["collapsed"] = node.is_collapsed()
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
        snapshot = _unwrap(
            self.remote.execute_python_json(code, {"texture_set": texture_set})
        )
        canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return {
            **snapshot,
            "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        }

    def set_active_channels(self, uid: int, channels: list[str]) -> dict[str, Any]:
        if not channels:
            raise ValueError("channels must contain at least one channel")
        if len(set(channels)) != len(channels):
            raise ValueError("channels must not contain duplicates")
        code = '''
import substance_painter.layerstack as layerstack
import substance_painter.textureset as textureset

node = layerstack.get_node_by_uid(params["uid"])
if not isinstance(node, (layerstack.FillLayerNode, layerstack.PaintLayerNode)):
    raise TypeError(f"Node {params['uid']} does not expose active channels")

aliases = {
    "Roughness": "SpecularRoughness",
    "Metallic": "BaseMetalness",
    "Emission": "Emissive",
}
resolved = []
for requested in params["channels"]:
    name = requested if requested in textureset.ChannelType.__members__ else aliases.get(requested)
    if not name or name not in textureset.ChannelType.__members__:
        raise ValueError(f"Unknown channel: {requested}")
    resolved.append(textureset.ChannelType.__members__[name])
node.active_channels = set(resolved)
result = {
    "uid": node.uid(),
    "name": node.get_name(),
    "active_channels": sorted(channel.name for channel in node.active_channels),
}
'''
        return _unwrap(
            self.remote.execute_python_json(code, {"uid": uid, "channels": channels})
        )

    def create_layer_recipe(
        self,
        recipe: list[dict[str, Any]],
        texture_set: str | None = None,
    ) -> dict[str, Any]:
        self._validate_recipe(recipe)
        code = '''
import substance_painter.colormanagement as colormanagement
import substance_painter.layerstack as layerstack
import substance_painter.textureset as textureset

stack = (textureset.TextureSet.from_name(params["texture_set"]).get_stack()
         if params.get("texture_set") else textureset.get_active_stack())
created_nodes = []

def resolve_channel(name):
    aliases = {
        "Roughness": "SpecularRoughness",
        "Metallic": "BaseMetalness",
        "Emission": "Emissive",
    }
    resolved = name if name in textureset.ChannelType.__members__ else aliases.get(name)
    if not resolved or resolved not in textureset.ChannelType.__members__:
        raise ValueError(f"Unknown channel: {name}")
    return textureset.ChannelType.__members__[resolved]

def create_items(items, parent=None):
    described = []
    for spec in reversed(items):
        position = (layerstack.InsertPosition.inside_node(parent, layerstack.NodeStack.Substack)
                    if parent else layerstack.InsertPosition.from_textureset_stack(stack))
        kind = spec["type"].casefold()
        if kind == "group":
            node = layerstack.insert_group(position)
        elif kind == "fill":
            node = layerstack.insert_fill(position)
        elif kind == "paint":
            node = layerstack.insert_paint(position)
        else:
            raise ValueError(f"Unsupported recipe node type: {spec['type']}")
        created_nodes.append(node)
        node.set_name(spec["name"])
        if "visible" in spec:
            node.set_visible(spec["visible"])
        if isinstance(node, (layerstack.FillLayerNode, layerstack.PaintLayerNode)) and spec.get("active_channels"):
            node.active_channels = {resolve_channel(name) for name in spec["active_channels"]}
        if isinstance(node, layerstack.FillLayerNode):
            values = dict(spec.get("channels") or {})
            if spec.get("base_color") is not None:
                values["BaseColor"] = spec["base_color"]
            if values:
                node.active_channels = set(node.active_channels) | {resolve_channel(name) for name in values}
                for name, color in values.items():
                    node.set_source(resolve_channel(name), colormanagement.Color(*color))
        mask = spec.get("mask")
        if mask:
            background_name = mask.get("background", "Black")
            if background_name not in layerstack.MaskBackground.__members__:
                raise ValueError(f"Unknown mask background: {background_name}")
            node.add_mask(layerstack.MaskBackground.__members__[background_name])
            if mask.get("enabled") is False:
                node.enable_mask(False)
        children = create_items(spec.get("children") or [], node) if kind == "group" else []
        described.append({
            "uid": node.uid(),
            "name": node.get_name(),
            "type": type(node).__name__,
            "children": children,
        })
    described.reverse()
    return described

try:
    nodes = create_items(params["recipe"])
except Exception:
    for node in reversed(created_nodes):
        try:
            layerstack.delete_node(node)
        except Exception:
            pass
    raise
result = {"created_count": len(created_nodes), "nodes": nodes, "rolled_back": False}
'''
        return _unwrap(
            self.remote.execute_python_json(
                code, {"recipe": self._normalize_recipe(recipe), "texture_set": texture_set}
            )
        )

    def insert_mask_effect(
        self,
        uid: int,
        effect_type: str,
        resource_url: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        normalized = effect_type.casefold()
        allowed = {"fill", "paint", "generator", "filter", "levels", "anchor", "smart_mask"}
        if normalized not in allowed:
            raise ValueError(f"effect_type must be one of: {', '.join(sorted(allowed))}")
        if normalized in {"generator", "filter", "smart_mask"} and resource_url is not None:
            if not resource_url.startswith("resource://"):
                raise ValueError("resource_url must start with resource://")
        if normalized == "smart_mask" and not resource_url:
            raise ValueError("smart_mask requires resource_url")
        code = '''
import substance_painter.layerstack as layerstack
import substance_painter.resource as resource

node = layerstack.get_node_by_uid(params["uid"])
if not isinstance(node, layerstack.LayerNode):
    raise TypeError(f"Node {params['uid']} does not support a mask stack")
added_mask = False
if not node.has_mask():
    node.add_mask(layerstack.MaskBackground.Black)
    added_mask = True
inserted = []
try:
    position = layerstack.InsertPosition.inside_node(node, layerstack.NodeStack.Mask)
    resource_id = resource.ResourceID.from_url(params["resource_url"]) if params.get("resource_url") else None
    kind = params["effect_type"]
    if kind == "fill":
        inserted = [layerstack.insert_fill(position)]
    elif kind == "paint":
        inserted = [layerstack.insert_paint(position)]
    elif kind == "generator":
        inserted = [layerstack.insert_generator_effect(position, resource_id)]
    elif kind == "filter":
        inserted = [layerstack.insert_filter_effect(position, resource_id)]
    elif kind == "levels":
        inserted = [layerstack.insert_levels_effect(position)]
    elif kind == "anchor":
        inserted = [layerstack.insert_anchor_point_effect(position, params.get("name") or "MCP Anchor")]
    elif kind == "smart_mask":
        inserted = list(layerstack.insert_smart_mask(position, resource_id))
    else:
        raise ValueError(f"Unsupported mask effect: {kind}")
    if params.get("name") and kind != "anchor" and len(inserted) == 1:
        inserted[0].set_name(params["name"])
except Exception:
    for effect in reversed(inserted):
        try:
            layerstack.delete_node(effect)
        except Exception:
            pass
    if added_mask and node.has_mask():
        node.remove_mask()
    raise
result = {
    "uid": node.uid(),
    "name": node.get_name(),
    "has_mask": node.has_mask(),
    "effects": [
        {"uid": effect.uid(), "name": effect.get_name(), "type": type(effect).__name__}
        for effect in inserted
    ],
}
'''
        return _unwrap(
            self.remote.execute_python_json(
                code,
                {
                    "uid": uid,
                    "effect_type": normalized,
                    "resource_url": resource_url,
                    "name": name,
                },
            )
        )

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
        failed = [
            item for item in result["verification"]
            if not item["exists"] or not item["bytes"]
        ]
        if failed:
            raise IOError(f"Texture export verification failed for {len(failed)} file(s)")
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

    def search_resources(
        self,
        query: str,
        limit: int = 50,
        resource_type: str | None = None,
        usage: str | None = None,
    ) -> dict[str, Any]:
        if not query.strip():
            raise ValueError("query must not be empty")
        if not 1 <= limit <= 200:
            raise ValueError("limit must be in the 1..200 range")
        code = '''
import substance_painter.resource as resource
items = resource.search(params["query"])

def safe_usages(item):
    try:
        return [value.name for value in item.usages()]
    except (ValueError, KeyError):
        return []

if params.get("resource_type"):
    expected_type = params["resource_type"].casefold()
    items = [item for item in items if item.type().name.casefold() == expected_type]
if params.get("usage"):
    expected_usage = params["usage"].casefold()
    items = [item for item in items
             if any(value.casefold() == expected_usage for value in safe_usages(item))]
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
            "usages": safe_usages(item),
        }
        for item in items[:params["limit"]]
    ],
}
'''
        return _unwrap(
            self.remote.execute_python_json(
                code,
                {
                    "query": query,
                    "limit": limit,
                    "resource_type": resource_type,
                    "usage": usage,
                },
            )
        )

    def find_outdated_resources(self) -> dict[str, Any]:
        code = '''
import substance_painter.resource as resource
outdated = resource.list_project_outdated_resources()
result = {
    "count": len(outdated),
    "replacements": [
        {
            "current": old.url(),
            "available": new.url(),
            "same_name": old.name == new.name,
            "same_context": old.context == new.context,
        }
        for old, new in outdated.items()
    ],
}
'''
        return _unwrap(self.remote.execute_python_json(code))

    def inspect_export_preset(
        self,
        preset: str,
        texture_set: str | None = None,
    ) -> dict[str, Any]:
        code = '''
import os
import substance_painter.export as export
import substance_painter.project as project
import substance_painter.textureset as textureset

preset_input = params["preset"]
preset_url = preset_input if "://" in preset_input else None
preset_name = preset_input
preset_kind = "url"
if preset_url is None:
    for item in export.list_predefined_export_presets():
        if item.name.casefold() == preset_input.casefold():
            preset_url, preset_name, preset_kind = item.url, item.name, "predefined"
            break
if preset_url is None:
    for item in export.list_resource_export_presets():
        if item.resource_id.name.casefold() == preset_input.casefold():
            preset_url = item.resource_id.url()
            preset_name = item.resource_id.name
            preset_kind = "shelf"
            break
if preset_url is None:
    raise ValueError(f"Export preset not found: {preset_input}")

selected = [params["texture_set"]] if params.get("texture_set") else [
    item.name() if callable(item.name) else item.name for item in textureset.all_texture_sets()
]
project_path = project.file_path()
preview_path = os.path.dirname(str(project_path)) if project_path else os.getcwd()
config = {
    "exportShaderParams": False,
    "exportPath": preview_path,
    "defaultExportPreset": preset_url,
    "exportList": [{"rootPath": name} for name in selected],
    "exportParameters": [{"parameters": {"paddingAlgorithm": "infinite"}}],
}
listed = export.list_project_textures(config)
groups = []
for (set_name, stack_name), paths in listed.items():
    groups.append({
        "texture_set": set_name,
        "stack": stack_name,
        "maps": [os.path.basename(path) for path in paths],
        "map_count": len(paths),
    })
result = {
    "preset": {"name": preset_name, "url": preset_url, "kind": preset_kind},
    "texture_sets": selected,
    "groups": groups,
    "map_count": sum(group["map_count"] for group in groups),
}
'''
        return _unwrap(
            self.remote.execute_python_json(
                code, {"preset": preset, "texture_set": texture_set}
            )
        )

    def list_export_profiles(self) -> dict[str, Any]:
        presets = self.list_export_presets()
        available = {
            item["name"].casefold()
            for group in (presets["predefined"], presets["shelf"])
            for item in group
        }
        profiles = []
        for profile_id, profile in EXPORT_PROFILES.items():
            profiles.append(
                {
                    "id": profile_id,
                    **profile,
                    "available": profile["preset"].casefold() in available,
                }
            )
        return {"profiles": profiles}

    def plan_profile_export(
        self,
        output_directory: str,
        profile: str,
        texture_sets: list[str] | None = None,
        size_log2: int | None = None,
    ) -> dict[str, Any]:
        settings = self._get_export_profile(profile)
        plan = self.plan_texture_export(
            output_directory=output_directory,
            preset=settings["preset"],
            texture_sets=texture_sets,
            size_log2=size_log2,
            file_format=settings["file_format"],
            bit_depth=settings["bit_depth"],
        )
        plan["profile"] = profile
        return plan

    def export_with_profile(
        self,
        output_directory: str,
        profile: str,
        texture_sets: list[str] | None = None,
        size_log2: int | None = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        settings = self._get_export_profile(profile)
        result = self.export_textures(
            output_directory=output_directory,
            preset=settings["preset"],
            texture_sets=texture_sets,
            size_log2=size_log2,
            file_format=settings["file_format"],
            bit_depth=settings["bit_depth"],
            overwrite=overwrite,
        )
        result["profile"] = profile
        return result

    def replace_outdated_resources(self, confirm: bool = False) -> dict[str, Any]:
        if not confirm:
            raise PermissionError(
                "Resource replacement requires confirm=true after reviewing find_outdated_resources."
            )
        code = '''
import substance_painter.resource as resource
outdated = resource.list_project_outdated_resources()
if not outdated:
    result = {"requested": 0, "status": "nothing_to_update", "message": ""}
else:
    update = resource.replace_project_resources(outdated)
    result = {
        "requested": len(outdated),
        "status": update.status.name,
        "message": update.message,
        "remaining": len(resource.list_project_outdated_resources()),
    }
'''
        return _unwrap(self.remote.execute_python_json(code))

    def save_project_copy(
        self,
        output_path: str,
        mode: str = "Incremental",
        overwrite: bool = False,
    ) -> dict[str, Any]:
        output = self._validate_allowed_path(
            output_path, "SP_MCP_PROJECT_ROOTS", "Project copy"
        )
        if output.suffix.casefold() != ".spp":
            raise ValueError("output_path must use the .spp extension")
        if output.exists() and not overwrite:
            raise FileExistsError(
                f"Project copy already exists; set overwrite=true to replace it: {output}"
            )
        if mode not in {"Incremental", "Full"}:
            raise ValueError("mode must be Incremental or Full")
        code = '''
import substance_painter.project as project
if not project.is_open():
    raise RuntimeError("No project is open")
if project.is_busy():
    raise RuntimeError("Painter is busy and cannot save a project copy")
original = str(project.file_path()) if project.file_path() else None
save_mode = project.ProjectSaveMode.__members__[params["mode"]]
project.save_as_copy(params["output_path"], save_mode)
current = str(project.file_path()) if project.file_path() else None
result = {"original_project": original, "current_project": current}
'''
        result = _unwrap(
            self.remote.execute_python_json(
                code, {"output_path": output.as_posix(), "mode": mode}
            )
        )
        result.update(
            {
                "path": str(output),
                "exists": output.is_file(),
                "bytes": output.stat().st_size if output.is_file() else None,
                "original_unchanged": result["original_project"] == result["current_project"],
            }
        )
        if not result["exists"] or not result["bytes"]:
            raise IOError(f"Project copy verification failed: {output}")
        return result

    def export_smart_material(
        self,
        uid: int,
        name: str,
        output_directory: str,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        return self._export_smart_asset(
            "material", uid, name, output_directory, overwrite
        )

    def export_smart_mask(
        self,
        uid: int,
        name: str,
        output_directory: str,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        return self._export_smart_asset("mask", uid, name, output_directory, overwrite)

    @staticmethod
    def _validate_export_directory(output_directory: str) -> Path:
        return PainterOperations._validate_allowed_path(
            output_directory, "SP_MCP_EXPORT_ROOTS", "Texture export"
        )

    def delete_layer(self, uid: int) -> dict[str, Any]:
        code = '''
import substance_painter.layerstack as layerstack
node = layerstack.get_node_by_uid(params["uid"])
deleted = {"uid": node.uid(), "name": node.get_name(), "type": type(node).__name__}
layerstack.delete_node(node)
result = deleted
'''
        return _unwrap(self.remote.execute_python_json(code, {"uid": uid}))

    def _export_smart_asset(
        self,
        kind: str,
        uid: int,
        name: str,
        output_directory: str,
        overwrite: bool,
    ) -> dict[str, Any]:
        if not name.strip() or name != Path(name).name or re.search(r'[<>:"/\\|?*]', name):
            raise ValueError("name must be a non-empty Windows-safe file name")
        output = self._validate_allowed_path(
            output_directory, "SP_MCP_EXPORT_ROOTS", "Smart asset export"
        )
        extension = ".spsm" if kind == "material" else ".spmsk"
        expected = output / f"{name}{extension}"
        if expected.exists() and not overwrite:
            raise FileExistsError(
                f"Smart asset already exists; set overwrite=true to replace it: {expected}"
            )
        code = '''
import substance_painter.layerstack as layerstack
node = layerstack.get_node_by_uid(params["uid"])
if params["kind"] == "material":
    if not isinstance(node, layerstack.GroupLayerNode):
        raise TypeError("Smart Material export requires a GroupLayerNode")
    layerstack.export_as_smart_material(node, params["name"], params["output_directory"])
else:
    if not isinstance(node, layerstack.LayerNode) or not node.has_mask():
        raise TypeError("Smart Mask export requires a layer with a mask")
    layerstack.export_as_smart_mask(node, params["name"], params["output_directory"])
result = {"uid": node.uid(), "layer": node.get_name(), "kind": params["kind"]}
'''
        result = _unwrap(
            self.remote.execute_python_json(
                code,
                {
                    "uid": uid,
                    "kind": kind,
                    "name": name,
                    "output_directory": output.as_posix(),
                },
            )
        )
        candidates = [expected]
        if not expected.is_file():
            candidates = sorted(output.glob(f"{name}.*"))
        actual = next((path for path in candidates if path.is_file()), expected)
        result.update(
            {
                "path": str(actual),
                "exists": actual.is_file(),
                "bytes": actual.stat().st_size if actual.is_file() else None,
            }
        )
        if not result["exists"] or not result["bytes"]:
            raise IOError(f"Smart asset verification failed: {expected}")
        return result

    @staticmethod
    def _get_export_profile(profile: str) -> dict[str, Any]:
        normalized = profile.casefold()
        if normalized not in EXPORT_PROFILES:
            raise ValueError(
                f"Unknown export profile: {profile}. Available: {', '.join(EXPORT_PROFILES)}"
            )
        return EXPORT_PROFILES[normalized]

    @classmethod
    def _validate_recipe(cls, recipe: list[dict[str, Any]]) -> None:
        if not isinstance(recipe, list) or not recipe:
            raise ValueError("recipe must be a non-empty list")

        def visit(items: list[dict[str, Any]], depth: int = 0) -> None:
            if depth > 20:
                raise ValueError("recipe nesting exceeds 20 levels")
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError("each recipe item must be an object")
                kind = str(item.get("type", "")).casefold()
                if kind not in {"group", "fill", "paint"}:
                    raise ValueError("recipe item type must be group, fill, or paint")
                if not isinstance(item.get("name"), str) or not item["name"].strip():
                    raise ValueError("each recipe item requires a non-empty name")
                if "visible" in item and not isinstance(item["visible"], bool):
                    raise ValueError("visible must be a boolean")
                children = item.get("children") or []
                if children and kind != "group":
                    raise ValueError("only group recipe items may contain children")
                if not isinstance(children, list):
                    raise ValueError("children must be a list")
                if "base_color" in item and item["base_color"] is not None:
                    if kind != "fill":
                        raise ValueError("base_color is only valid for fill recipe items")
                    cls._validate_color(list(item["base_color"]))
                channels = item.get("channels") or {}
                if not isinstance(channels, dict):
                    raise ValueError("channels must be an object")
                if channels and kind != "fill":
                    raise ValueError("channels are only valid for fill recipe items")
                for value in channels.values():
                    color = [float(value)] * 3 if isinstance(value, (int, float)) else list(value)
                    cls._validate_color(color)
                active = item.get("active_channels") or []
                if not isinstance(active, list) or any(not isinstance(value, str) for value in active):
                    raise ValueError("active_channels must be a list of strings")
                if active and kind == "group":
                    raise ValueError("active_channels are only valid for fill or paint items")
                mask = item.get("mask")
                if mask is not None and not isinstance(mask, dict):
                    raise ValueError("mask must be an object")
                if mask is not None:
                    background = mask.get("background", "Black")
                    if background not in {"Black", "White"}:
                        raise ValueError("mask background must be Black or White")
                    if "enabled" in mask and not isinstance(mask["enabled"], bool):
                        raise ValueError("mask enabled must be a boolean")
                visit(children, depth + 1)

        visit(recipe)

    @classmethod
    def _normalize_recipe(cls, recipe: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = json.loads(json.dumps(recipe))

        def visit(items: list[dict[str, Any]]) -> None:
            for item in items:
                channels = item.get("channels") or {}
                item["channels"] = {
                    name: ([float(value)] * 3 if isinstance(value, (int, float)) else list(value))
                    for name, value in channels.items()
                }
                visit(item.get("children") or [])

        visit(normalized)
        return normalized

    @staticmethod
    def _validate_allowed_path(path: str, env_var: str, operation: str) -> Path:
        configured = os.getenv(env_var, "")
        roots = [Path(item).expanduser().resolve() for item in configured.split(os.pathsep) if item]
        if not roots:
            raise PermissionError(
                f"{operation} is disabled. Set {env_var} to one or more allowed roots."
            )
        output = Path(path).expanduser().resolve()
        output_key = os.path.normcase(str(output))
        for root in roots:
            root_key = os.path.normcase(str(root))
            try:
                if os.path.commonpath([output_key, root_key]) == root_key:
                    return output
            except ValueError:
                continue
        raise PermissionError(f"Path is outside {env_var}: {output}")

    @staticmethod
    def _validate_color(color: list[float]) -> None:
        if len(color) != 3 or any(not isinstance(value, (int, float)) for value in color):
            raise ValueError("color must contain exactly three numbers")
        if any(value < 0 or value > 1 for value in color):
            raise ValueError("color components must be in the 0..1 range")
