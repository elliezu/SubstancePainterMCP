"""Painter operations used by MCP tools."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
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

SAFE_RESOURCE_IMPORT_USAGES = {
    "ALPHA",
    "BASE_MATERIAL",
    "BRUSH",
    "COLOR_LUT",
    "ENVIRONMENT",
    "EXPORT",
    "FILTER",
    "FONT",
    "GENERATOR",
    "PROCEDURAL",
    "SMART_MASK",
    "SMART_MATERIAL",
    "TEXTURE",
}

BLOCKED_RESOURCE_EXTENSIONS = {
    ".bat", ".cmd", ".com", ".dll", ".exe", ".js", ".jsx", ".ps1",
    ".py", ".pyc", ".pyd", ".qml", ".vbs",
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
import substance_painter.resource as resource
import substance_painter.source as source
import substance_painter.textureset as textureset

result = {
    "blending_modes": list(layerstack.BlendingMode.__members__),
    "channel_types": list(textureset.ChannelType.__members__),
    "mask_backgrounds": list(layerstack.MaskBackground.__members__),
    "geometry_mask_types": list(layerstack.GeometryMaskType.__members__),
    "projection_modes": list(layerstack.ProjectionMode.__members__),
    "insert_positions": [name for name in ("above_node", "below_node", "inside_node")
                         if hasattr(layerstack.InsertPosition, name)],
    "features": {
        "geometry_mask_v2": hasattr(layerstack.LayerNode, "set_geometry_mask"),
        "smart_material_file_export": hasattr(layerstack, "export_as_smart_material"),
        "smart_mask_file_export": hasattr(layerstack, "export_as_smart_mask"),
        "mask_effect_insertion": hasattr(layerstack, "insert_generator_effect"),
        "smart_material_insertion": hasattr(layerstack, "insert_smart_material"),
        "smart_mask_insertion": hasattr(layerstack, "insert_smart_mask"),
        "predefined_export_presets": hasattr(export, "list_predefined_export_presets"),
        "async_baking": hasattr(baking, "bake_selected_textures_async"),
        "bake_cancellation": hasattr(baking, "StopSource"),
        "auto_unwrap_settings": hasattr(project, "AutoUnwrapUVTilesSettings"),
        "mesh_reload": hasattr(project, "reload_mesh"),
        "save_project_copy": hasattr(project, "save_as_copy"),
        "advanced_fill_projection": hasattr(layerstack, "Projection3DParams"),
        "procedural_source_parameters": hasattr(source.SourceSubstance, "set_parameters"),
        "anchor_source_binding": hasattr(layerstack, "AnchorPointEffectNode"),
        "baking_parameter_editing": hasattr(baking.BakingParameters, "set"),
        "batch_baking": hasattr(baking, "bake_selected_textures_async"),
        "baking_mesh_inputs": hasattr(baking.BakingParameters, "set"),
        "baking_presets": hasattr(baking.BakingParameters, "get"),
        "resource_import": hasattr(resource, "import_project_resource"),
        "procedural_image_inputs": hasattr(source.SourceSubstance, "set_source"),
        "baking_resource_inputs": hasattr(baking.BakingParameters, "set"),
        "auto_rebake_control": hasattr(baking, "set_auto_rebake"),
        "skew_painting_control": hasattr(baking, "start_skew_painting"),
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

    def inspect_baking_parameters(
        self, texture_set: str, baker: str | None = None
    ) -> dict[str, Any]:
        if not texture_set.strip():
            raise ValueError("texture_set must be a non-empty name")
        code = '''
import substance_painter.baking as baking
import substance_painter.textureset as textureset

def json_value(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if hasattr(value, "value_raw"):
        return {"type": "Color", "value": list(value.value_raw), "color_space": str(value.color_space)}
    return {"type": type(value).__name__, "value": str(value)}

def describe(properties):
    output = {}
    for key, prop in properties.items():
        try:
            enums = prop.enum_values()
        except Exception:
            enums = {}
        output[key] = {
            "name": prop.name(),
            "label": prop.label(),
            "widget": prop.widget_type(),
            "value": json_value(prop.value()),
            "enum_values": enums,
            "metadata": prop.properties(),
        }
    return output

target = textureset.TextureSet.from_name(params["texture_set"])
settings = baking.BakingParameters.from_texture_set(target)
available = list(textureset.MeshMapUsage.__members__)
requested = params.get("baker")
if requested is not None and requested not in textureset.MeshMapUsage.__members__:
    raise ValueError(f"Unknown baker: {requested}")
baker_properties = None
linked_baker_sets = []
if requested is not None:
    usage = textureset.MeshMapUsage.__members__[requested]
    baker_properties = describe(settings.baker(usage))
    linked_baker_sets = [
        item.name() if callable(item.name) else item.name
        for item in baking.get_linked_texture_sets(target, usage)
    ]
linked_common_sets = [
    item.name() if callable(item.name) else item.name
    for item in baking.get_linked_texture_sets_common_parameters(target)
]
result = {
    "texture_set": params["texture_set"],
    "enabled": settings.is_textureset_enabled(),
    "enabled_bakers": [usage.name for usage in settings.get_enabled_bakers()],
    "available_bakers": available,
    "uv_tiles": [1001 + tile.u + 10 * tile.v for tile in target.all_uv_tiles()],
    "enabled_uv_tiles": [1001 + tile.u + 10 * tile.v for tile in settings.get_enabled_uv_tiles()],
    "curvature_method": settings.get_curvature_method().name,
    "common": describe(settings.common()),
    "baker": requested,
    "baker_parameters": baker_properties,
    "linked_common_texture_sets": linked_common_sets,
    "linked_baker_texture_sets": linked_baker_sets,
}
'''
        return _unwrap(
            self.remote.execute_python_json(
                code, {"texture_set": texture_set, "baker": baker}
            )
        )

    def configure_baking(
        self,
        texture_set: str,
        enabled: bool | None = None,
        enabled_bakers: list[str] | None = None,
        enabled_uv_tiles: list[int] | None = None,
        curvature_method: str | None = None,
        common_values: dict[str, Any] | None = None,
        baker_values: dict[str, dict[str, Any]] | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        if not texture_set.strip():
            raise ValueError("texture_set must be a non-empty name")
        if enabled is not None and not isinstance(enabled, bool):
            raise ValueError("enabled must be a boolean")
        if enabled_bakers is not None:
            if any(not isinstance(name, str) or not name for name in enabled_bakers):
                raise ValueError("enabled_bakers must contain non-empty names")
            if len(set(enabled_bakers)) != len(enabled_bakers):
                raise ValueError("enabled_bakers must not contain duplicates")
        if enabled_uv_tiles is not None:
            if any(
                not isinstance(value, int) or isinstance(value, bool) or value < 1001
                for value in enabled_uv_tiles
            ):
                raise ValueError("enabled_uv_tiles must contain UDIM integers >= 1001")
            if len(set(enabled_uv_tiles)) != len(enabled_uv_tiles):
                raise ValueError("enabled_uv_tiles must not contain duplicates")
        if curvature_method not in {None, "FromMesh", "FromNormalMap"}:
            raise ValueError("curvature_method must be FromMesh or FromNormalMap")
        common_values = common_values or {}
        baker_values = baker_values or {}
        if common_values:
            self._validate_parameter_values(common_values)
        if not isinstance(baker_values, dict):
            raise ValueError("baker_values must be an object")
        for baker_name, values in baker_values.items():
            if not isinstance(baker_name, str) or not baker_name:
                raise ValueError("baker_values keys must be non-empty baker names")
            self._validate_parameter_values(values)
        if all(
            value is None
            for value in (enabled, enabled_bakers, enabled_uv_tiles, curvature_method)
        ) and not common_values and not baker_values:
            raise ValueError("At least one baking configuration change is required")
        if not confirm:
            raise PermissionError("Baking configuration modifies the project; set confirm=true")
        code = '''
import substance_painter.colormanagement as colormanagement
import substance_painter.baking as baking
import substance_painter.textureset as textureset

def json_value(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if hasattr(value, "value_raw"):
        return {"type": "Color", "value": list(value.value_raw), "color_space": str(value.color_space)}
    return {"type": type(value).__name__, "value": str(value)}

def convert(prop, value):
    current = prop.value()
    widget = prop.widget_type()
    if widget in {"File", "FileList", "Resource"}:
        raise ValueError(f"File/resource parameter editing is disabled: {prop.short_name()}")
    def checked(number):
        metadata = prop.properties()
        minimum = metadata.get("editorMin") if widget == "RandomSeed" else metadata.get("min")
        maximum = metadata.get("editorMax") if widget == "RandomSeed" else metadata.get("max")
        if isinstance(minimum, (int, float)) and number < minimum:
            raise ValueError(f"{prop.short_name()} must be >= {minimum}")
        if isinstance(maximum, (int, float)) and number > maximum:
            raise ValueError(f"{prop.short_name()} must be <= {maximum}")
        return number
    if widget == "Color":
        if not isinstance(value, list) or len(value) not in {3, 4}:
            raise ValueError(f"{prop.short_name()} must be an RGB or RGBA array")
        return colormanagement.Color(*value[:3])
    if widget == "Combobox" and isinstance(value, str):
        enums = prop.enum_values()
        if value not in enums:
            raise ValueError(f"Unknown {prop.short_name()} enum label: {value}")
        return prop.enum_value(value)
    if isinstance(current, tuple):
        if not isinstance(value, list) or len(value) != len(current):
            raise ValueError(f"{prop.short_name()} must contain {len(current)} values")
        return tuple(value)
    if isinstance(current, bool):
        if not isinstance(value, bool):
            raise ValueError(f"{prop.short_name()} must be a boolean")
        return value
    if isinstance(current, int) and not isinstance(current, bool):
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{prop.short_name()} must be an integer")
        return checked(value)
    if isinstance(current, float):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"{prop.short_name()} must be a number")
        return checked(float(value))
    if isinstance(current, str):
        if not isinstance(value, str):
            raise ValueError(f"{prop.short_name()} must be a string")
        return value
    return value

target = textureset.TextureSet.from_name(params["texture_set"])
settings = baking.BakingParameters.from_texture_set(target)
usage_members = textureset.MeshMapUsage.__members__
requested_bakers = params.get("enabled_bakers")
if requested_bakers is not None:
    missing = [name for name in requested_bakers if name not in usage_members]
    if missing:
        raise ValueError(f"Unknown bakers: {missing}")
requested_baker_values = params.get("baker_values") or {}
missing = [name for name in requested_baker_values if name not in usage_members]
if missing:
    raise ValueError(f"Unknown bakers: {missing}")

all_tiles = {1001 + tile.u + 10 * tile.v: tile for tile in target.all_uv_tiles()}
requested_tiles = params.get("enabled_uv_tiles")
if requested_tiles is not None:
    missing_tiles = [udim for udim in requested_tiles if udim not in all_tiles]
    if missing_tiles:
        raise ValueError(f"Unknown UV tiles: {missing_tiles}")

common_props = settings.common()
unknown_common = sorted(set(params.get("common_values") or {}) - set(common_props))
if unknown_common:
    raise ValueError(f"Unknown common baking parameters: {unknown_common}")
baker_props = {}
for name, values in requested_baker_values.items():
    props = settings.baker(usage_members[name])
    unknown = sorted(set(values) - set(props))
    if unknown:
        raise ValueError(f"Unknown {name} baking parameters: {unknown}")
    baker_props[name] = props

original = {
    "enabled": settings.is_textureset_enabled(),
    "enabled_bakers": settings.get_enabled_bakers(),
    "enabled_uv_tiles": settings.get_enabled_uv_tiles(),
    "curvature_method": settings.get_curvature_method(),
    "common": {common_props[name]: common_props[name].value() for name in (params.get("common_values") or {})},
    "bakers": {
        name: {props[key]: props[key].value() for key in requested_baker_values[name]}
        for name, props in baker_props.items()
    },
}
impacted = {params["texture_set"]}
if params.get("common_values"):
    impacted.update(
        item.name() if callable(item.name) else item.name
        for item in baking.get_linked_texture_sets_common_parameters(target)
    )
for name in requested_baker_values:
    impacted.update(
        item.name() if callable(item.name) else item.name
        for item in baking.get_linked_texture_sets(target, usage_members[name])
    )

try:
    if params.get("enabled") is not None:
        settings.set_textureset_enabled(params["enabled"])
    if requested_bakers is not None:
        settings.set_enabled_bakers([usage_members[name] for name in requested_bakers])
    if requested_tiles is not None:
        settings.set_enabled_uv_tiles([all_tiles[udim] for udim in requested_tiles])
    if params.get("curvature_method") is not None:
        settings.set_curvature_method(baking.CurvatureMethod.__members__[params["curvature_method"]])
    if params.get("common_values"):
        settings.set({
            common_props[name]: convert(common_props[name], value)
            for name, value in params["common_values"].items()
        })
    for name, values in requested_baker_values.items():
        props = baker_props[name]
        settings.set({props[key]: convert(props[key], value) for key, value in values.items()})
except Exception:
    try:
        settings.set_textureset_enabled(original["enabled"])
        settings.set_enabled_bakers(original["enabled_bakers"])
        settings.set_enabled_uv_tiles(original["enabled_uv_tiles"])
        settings.set_curvature_method(original["curvature_method"])
        if original["common"]:
            settings.set(original["common"])
        for values in original["bakers"].values():
            if values:
                settings.set(values)
    except Exception:
        pass
    raise

verified_common = settings.common()
verified_bakers = {
    name: settings.baker(usage_members[name]) for name in requested_baker_values
}
result = {
    "texture_set": params["texture_set"],
    "enabled": settings.is_textureset_enabled(),
    "enabled_bakers": [usage.name for usage in settings.get_enabled_bakers()],
    "enabled_uv_tiles": [1001 + tile.u + 10 * tile.v for tile in settings.get_enabled_uv_tiles()],
    "curvature_method": settings.get_curvature_method().name,
    "common_values": {
        name: json_value(verified_common[name].value()) for name in (params.get("common_values") or {})
    },
    "baker_values": {
        name: {key: json_value(verified_bakers[name][key].value()) for key in values}
        for name, values in requested_baker_values.items()
    },
    "impacted_texture_sets": sorted(impacted),
}
'''
        return _unwrap(
            self.remote.execute_python_json(
                code,
                {
                    "texture_set": texture_set,
                    "enabled": enabled,
                    "enabled_bakers": enabled_bakers,
                    "enabled_uv_tiles": enabled_uv_tiles,
                    "curvature_method": curvature_method,
                    "common_values": common_values,
                    "baker_values": baker_values,
                },
            )
        )

    def set_baking_mesh_inputs(
        self,
        texture_set: str,
        high_poly_files: list[str] | None = None,
        cage_file: str | None = None,
        low_as_high: bool | None = None,
        cage_mode: str | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        if not texture_set.strip():
            raise ValueError("texture_set must be a non-empty name")
        if high_poly_files is not None:
            if not isinstance(high_poly_files, list) or any(
                not isinstance(path, str) for path in high_poly_files
            ):
                raise ValueError("high_poly_files must be a list of paths")
            if len(set(high_poly_files)) != len(high_poly_files):
                raise ValueError("high_poly_files must not contain duplicates")
        if cage_file is not None and not isinstance(cage_file, str):
            raise ValueError("cage_file must be a path or an empty string to clear it")
        if low_as_high is not None and not isinstance(low_as_high, bool):
            raise ValueError("low_as_high must be a boolean")
        cage_modes = {"Distance-based", "Automatic (experimental)", "Custom file"}
        if cage_mode is not None and cage_mode not in cage_modes:
            raise ValueError(f"cage_mode must be one of: {', '.join(sorted(cage_modes))}")
        if all(value is None for value in (high_poly_files, cage_file, low_as_high, cage_mode)):
            raise ValueError("At least one baking mesh input change is required")
        if not confirm:
            raise PermissionError("Baking mesh inputs modify the project; set confirm=true")

        high_poly_urls = None
        if high_poly_files is not None:
            high_poly_urls = [
                self._validate_bake_mesh_path(path).as_uri() for path in high_poly_files
            ]
        cage_url = None
        if cage_file is not None:
            cage_url = (
                self._validate_bake_mesh_path(cage_file).as_uri() if cage_file else ""
            )
            if cage_file and cage_mode is None:
                cage_mode = "Custom file"
        code = '''
import substance_painter.baking as baking
import substance_painter.textureset as textureset

target = textureset.TextureSet.from_name(params["texture_set"])
settings = baking.BakingParameters.from_texture_set(target)
common = settings.common()
required = {"HipolyMesh", "CageMesh", "LowAsHigh", "CageMode"}
missing = sorted(required - set(common))
if missing:
    raise RuntimeError(f"Painter does not expose required baking properties: {missing}")
changes = {}
if params.get("high_poly_urls") is not None:
    changes[common["HipolyMesh"]] = "|".join(params["high_poly_urls"])
if params.get("cage_url") is not None:
    changes[common["CageMesh"]] = params["cage_url"]
if params.get("low_as_high") is not None:
    changes[common["LowAsHigh"]] = params["low_as_high"]
if params.get("cage_mode") is not None:
    changes[common["CageMode"]] = common["CageMode"].enum_value(params["cage_mode"])
original = {prop: prop.value() for prop in changes}
try:
    settings.set(changes)
except Exception:
    try:
        settings.set(original)
    except Exception:
        pass
    raise
linked = [
    item.name() if callable(item.name) else item.name
    for item in baking.get_linked_texture_sets_common_parameters(target)
]
cage_enum = {value: label for label, value in common["CageMode"].enum_values().items()}
result = {
    "texture_set": params["texture_set"],
    "high_poly_files": common["HipolyMesh"].value().split("|") if common["HipolyMesh"].value() else [],
    "cage_file": common["CageMesh"].value(),
    "low_as_high": common["LowAsHigh"].value(),
    "cage_mode": cage_enum.get(common["CageMode"].value(), common["CageMode"].value()),
    "impacted_texture_sets": linked,
}
'''
        return _unwrap(
            self.remote.execute_python_json(
                code,
                {
                    "texture_set": texture_set,
                    "high_poly_urls": high_poly_urls,
                    "cage_url": cage_url,
                    "low_as_high": low_as_high,
                    "cage_mode": cage_mode,
                },
            )
        )

    def set_baking_resource_input(
        self,
        texture_set: str,
        parameter: str,
        resource_url: str | None = None,
        baker: str | None = None,
        clear: bool = False,
        confirm: bool = False,
    ) -> dict[str, Any]:
        if not texture_set.strip():
            raise ValueError("texture_set must be a non-empty name")
        if not parameter.strip():
            raise ValueError("parameter must be a non-empty name")
        if clear == (resource_url is not None):
            raise ValueError("Provide exactly one of resource_url or clear=true")
        if resource_url is not None and not resource_url.startswith("resource://"):
            raise ValueError("resource_url must start with resource://")
        if baker is not None and not baker.strip():
            raise ValueError("baker must be a non-empty name when supplied")
        if not confirm:
            raise PermissionError("Baking resource inputs modify the project; set confirm=true")
        code = '''
import substance_painter.baking as baking
import substance_painter.resource as resource
import substance_painter.textureset as textureset

target = textureset.TextureSet.from_name(params["texture_set"])
settings = baking.BakingParameters.from_texture_set(target)
if params.get("baker"):
    if params["baker"] not in textureset.MeshMapUsage.__members__:
        raise ValueError(f"Unknown baker: {params['baker']}")
    usage = textureset.MeshMapUsage.__members__[params["baker"]]
    properties = settings.baker(usage)
else:
    usage = None
    properties = settings.common()
if params["parameter"] not in properties:
    raise ValueError(f"Unknown baking parameter: {params['parameter']}")
prop = properties[params["parameter"]]
if prop.widget_type() != "Resource":
    raise ValueError(
        f"Baking parameter {params['parameter']} is {prop.widget_type()}, not Resource"
    )
value = ""
if params.get("resource_url") is not None:
    resource_id = resource.ResourceID.from_url(params["resource_url"])
    if not resource.Resource.retrieve(resource_id):
        raise ValueError(f"Resource not found: {params['resource_url']}")
    value = resource_id.url()
original = prop.value()
try:
    settings.set({prop: value})
except Exception:
    try:
        settings.set({prop: original})
    except Exception:
        pass
    raise
if usage is None:
    linked = baking.get_linked_texture_sets_common_parameters(target)
else:
    linked = baking.get_linked_texture_sets(target, usage)
result = {
    "texture_set": params["texture_set"],
    "baker": params.get("baker"),
    "parameter": params["parameter"],
    "resource_url": prop.value(),
    "cleared": not bool(prop.value()),
    "impacted_texture_sets": [
        item.name() if callable(item.name) else item.name for item in linked
    ],
}
'''
        return _unwrap(
            self.remote.execute_python_json(
                code,
                {
                    "texture_set": texture_set,
                    "parameter": parameter,
                    "resource_url": resource_url,
                    "baker": baker,
                },
            )
        )

    def capture_baking_preset(
        self, texture_set: str, bakers: list[str] | None = None
    ) -> dict[str, Any]:
        if not texture_set.strip():
            raise ValueError("texture_set must be a non-empty name")
        if bakers is not None and (
            any(not isinstance(name, str) or not name for name in bakers)
            or len(set(bakers)) != len(bakers)
        ):
            raise ValueError("bakers must contain unique non-empty names")
        code = '''
import substance_painter.baking as baking
import substance_painter.textureset as textureset

def portable(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [portable(item) for item in value]
    if hasattr(value, "value_raw"):
        return list(value.value_raw)
    raise TypeError(f"Unsupported preset value: {type(value).__name__}")

def safe_values(properties):
    return {
        key: portable(prop.value())
        for key, prop in properties.items()
        if prop.widget_type() not in {"File", "FileList", "Resource"}
    }

target = textureset.TextureSet.from_name(params["texture_set"])
settings = baking.BakingParameters.from_texture_set(target)
available = textureset.MeshMapUsage.__members__
requested = params.get("bakers")
if requested is None:
    requested = [usage.name for usage in settings.get_enabled_bakers()]
missing = [name for name in requested if name not in available]
if missing:
    raise ValueError(f"Unknown bakers: {missing}")
result = {
    "schema": "substance-painter-mcp/baking-preset@1",
    "source_texture_set": params["texture_set"],
    "enabled": settings.is_textureset_enabled(),
    "enabled_bakers": [usage.name for usage in settings.get_enabled_bakers()],
    "enabled_uv_tiles": [1001 + tile.u + 10 * tile.v for tile in settings.get_enabled_uv_tiles()],
    "curvature_method": settings.get_curvature_method().name,
    "common_values": safe_values(settings.common()),
    "baker_values": {
        name: safe_values(settings.baker(available[name])) for name in requested
    },
}
'''
        return _unwrap(
            self.remote.execute_python_json(
                code, {"texture_set": texture_set, "bakers": bakers}
            )
        )

    def apply_baking_preset(
        self,
        texture_set: str,
        preset: dict[str, Any],
        confirm: bool = False,
    ) -> dict[str, Any]:
        if not isinstance(preset, dict):
            raise ValueError("preset must be an object")
        if preset.get("schema") != "substance-painter-mcp/baking-preset@1":
            raise ValueError("Unsupported baking preset schema")
        required = {
            "enabled",
            "enabled_bakers",
            "enabled_uv_tiles",
            "curvature_method",
            "common_values",
            "baker_values",
        }
        missing = sorted(required - set(preset))
        if missing:
            raise ValueError(f"Baking preset is missing fields: {', '.join(missing)}")
        result = self.configure_baking(
            texture_set=texture_set,
            enabled=preset["enabled"],
            enabled_bakers=preset["enabled_bakers"],
            enabled_uv_tiles=preset["enabled_uv_tiles"],
            curvature_method=preset["curvature_method"],
            common_values=preset["common_values"],
            baker_values=preset["baker_values"],
            confirm=confirm,
        )
        result["preset_schema"] = preset["schema"]
        result["source_texture_set"] = preset.get("source_texture_set")
        return result

    def preflight_bake(self, texture_sets: list[str] | None = None) -> dict[str, Any]:
        if texture_sets is not None:
            if not texture_sets or any(not isinstance(name, str) or not name for name in texture_sets):
                raise ValueError("texture_sets must contain at least one non-empty name")
            if len(set(texture_sets)) != len(texture_sets):
                raise ValueError("texture_sets must not contain duplicates")
        code = '''
import os
from PySide6 import QtCore
import substance_painter.baking as baking
import substance_painter.project as project
import substance_painter.textureset as textureset

if not project.is_open():
    raise RuntimeError("No project is open")
all_sets = {
    (item.name() if callable(item.name) else item.name): item
    for item in textureset.all_texture_sets()
}
requested = params.get("texture_sets")
if requested is None:
    requested = [
        name for name, item in all_sets.items()
        if baking.BakingParameters.from_texture_set(item).is_textureset_enabled()
    ]
missing = [name for name in requested if name not in all_sets]
if missing:
    raise ValueError(f"Unknown Texture Sets: {missing}")
entries = []
all_issues = []
busy = project.is_busy()
if busy:
    all_issues.append({"code": "painter_busy", "message": "Painter is busy with another operation."})
if not requested:
    all_issues.append({"code": "no_texture_sets", "message": "No Texture Sets were selected or enabled for baking."})
for name in requested:
    item = all_sets[name]
    settings = baking.BakingParameters.from_texture_set(item)
    common = settings.common()
    errors = []
    warnings = []
    enabled_bakers = [usage.name for usage in settings.get_enabled_bakers()]
    enabled_tiles = [1001 + tile.u + 10 * tile.v for tile in settings.get_enabled_uv_tiles()]
    if not settings.is_textureset_enabled():
        warnings.append({"code": "texture_set_disabled", "message": "Batch execution will enable it temporarily."})
    if not enabled_bakers:
        errors.append({"code": "no_enabled_bakers", "message": "No mesh-map bakers are enabled."})
    if not enabled_tiles:
        errors.append({"code": "no_enabled_uv_tiles", "message": "No UV tiles are enabled for baking."})
    high_urls = common["HipolyMesh"].value().split("|") if common["HipolyMesh"].value() else []
    cage_url = common["CageMesh"].value()
    low_as_high = bool(common["LowAsHigh"].value())
    cage_value = common["CageMode"].value()
    cage_labels = {value: label for label, value in common["CageMode"].enum_values().items()}
    cage_mode = cage_labels.get(cage_value, str(cage_value))
    missing_files = []
    for url in high_urls + ([cage_url] if cage_url else []):
        local = QtCore.QUrl(url).toLocalFile()
        if not local or not os.path.isfile(local):
            missing_files.append({"url": url, "path": local})
    if not low_as_high and not high_urls:
        errors.append({"code": "missing_high_poly", "message": "LowAsHigh is false but no high-poly mesh is assigned."})
    if cage_mode == "Custom file" and not cage_url:
        errors.append({"code": "missing_cage", "message": "Custom cage mode requires a cage mesh."})
    if missing_files:
        errors.append({"code": "missing_mesh_files", "files": missing_files})
    output_size = common["OutputSize"].value()
    aa_prop = common.get("SubSampling")
    aa_label = None
    if aa_prop is not None:
        aa_label = {value: label for label, value in aa_prop.enum_values().items()}.get(aa_prop.value())
    mesh_maps = {}
    for usage_name in enabled_bakers:
        usage = textureset.MeshMapUsage.__members__[usage_name]
        resource_id = item.get_mesh_map_resource(usage)
        mesh_maps[usage_name] = resource_id.url() if resource_id else None
    entry = {
        "texture_set": name,
        "enabled": settings.is_textureset_enabled(),
        "enabled_bakers": enabled_bakers,
        "enabled_uv_tiles": enabled_tiles,
        "output_size_log2": list(output_size),
        "output_size": [2 ** output_size[0], 2 ** output_size[1]],
        "antialiasing": aa_label,
        "low_as_high": low_as_high,
        "high_poly_files": high_urls,
        "cage_mode": cage_mode,
        "cage_file": cage_url,
        "mesh_maps_before": mesh_maps,
        "errors": errors,
        "warnings": warnings,
    }
    entries.append(entry)
    all_issues.extend({"texture_set": name, **issue} for issue in errors)
result = {
    "ready": bool(entries) and not all_issues,
    "busy": busy,
    "texture_sets": entries,
    "errors": all_issues,
}
'''
        return _unwrap(
            self.remote.execute_python_json(code, {"texture_sets": texture_sets})
        )

    def start_batch_bake(
        self,
        texture_sets: list[str],
        confirm: bool = False,
        backup_path: str | None = None,
        backup_mode: str = "Incremental",
        overwrite_backup: bool = False,
    ) -> dict[str, Any]:
        if not confirm:
            raise PermissionError("Batch baking modifies mesh maps; set confirm=true to start")
        plan = self.preflight_bake(texture_sets)
        if not plan["ready"]:
            raise ValueError(f"Bake preflight failed: {plan['errors']}")
        backup = (
            self.save_project_copy(backup_path, backup_mode, overwrite_backup)
            if backup_path
            else None
        )
        code = '''
import builtins
import time
import uuid
import substance_painter.baking as baking
import substance_painter.event as event
import substance_painter.project as project
import substance_painter.textureset as textureset

if project.is_busy():
    raise RuntimeError("Painter is busy")
previous_refs = getattr(builtins, "_sp_mcp_bake_refs", None)
if previous_refs:
    for event_cls, callback in previous_refs:
        try:
            event.DISPATCHER.disconnect(event_cls, callback)
        except Exception:
            pass
all_sets = {
    (item.name() if callable(item.name) else item.name): item
    for item in textureset.all_texture_sets()
}
selected = set(params["texture_sets"])
original_enabled = {
    name: baking.BakingParameters.from_texture_set(item).is_textureset_enabled()
    for name, item in all_sets.items()
}
before_maps = {}
expected = {}
for name in params["texture_sets"]:
    item = all_sets[name]
    settings = baking.BakingParameters.from_texture_set(item)
    usages = [usage.name for usage in settings.get_enabled_bakers()]
    expected[name] = usages
    before_maps[name] = {}
    for usage_name in usages:
        resource_id = item.get_mesh_map_resource(textureset.MeshMapUsage.__members__[usage_name])
        before_maps[name][usage_name] = resource_id.url() if resource_id else None

job_id = uuid.uuid4().hex
state = {
    "job_id": job_id,
    "operation": "batch_bake",
    "texture_sets": params["texture_sets"],
    "status": "starting",
    "progress": 0.0,
    "cancel_requested": False,
    "started_at": time.time(),
    "finished_at": None,
    "error": None,
    "results": None,
}
builtins._sp_mcp_bake_state = state

def restore_enabled():
    for name, enabled in original_enabled.items():
        try:
            baking.BakingParameters.from_texture_set(all_sets[name]).set_textureset_enabled(enabled)
        except Exception:
            pass

def on_about_to_start(message):
    if getattr(builtins, "_sp_mcp_bake_state", None) is state:
        state["status"] = "running"

def on_progress(message):
    if getattr(builtins, "_sp_mcp_bake_state", None) is state:
        state["status"] = "running"
        state["progress"] = max(0.0, min(1.0, float(message.progress)))

def on_ended(message):
    if getattr(builtins, "_sp_mcp_bake_state", None) is not state:
        return
    status_name = message.status.name
    state["status"] = {"Success": "success", "Cancel": "cancelled", "Fail": "failed"}.get(
        status_name, status_name.casefold()
    )
    if status_name == "Fail":
        state["error"] = "Painter reported a baking failure; its event API exposes no per-baker log text."
    state["progress"] = 1.0 if status_name == "Success" else state["progress"]
    state["finished_at"] = time.time()
    results = {}
    for name in params["texture_sets"]:
        item = all_sets[name]
        maps = {}
        for usage_name in expected[name]:
            resource_id = item.get_mesh_map_resource(textureset.MeshMapUsage.__members__[usage_name])
            after = resource_id.url() if resource_id else None
            before = before_maps[name][usage_name]
            maps[usage_name] = {
                "before": before,
                "after": after,
                "present": after is not None,
                "changed": before != after,
                "verified": status_name == "Success" and after is not None,
                "status": (
                    ("updated" if before != after else "present_unchanged")
                    if status_name == "Success" and after is not None
                    else ("missing" if status_name == "Success" else state["status"])
                ),
            }
        results[name] = {
            "mesh_maps": maps,
            "expected_count": len(maps),
            "present_count": sum(1 for value in maps.values() if value["present"]),
            "all_present": all(value["present"] for value in maps.values()),
            "all_verified": all(value["verified"] for value in maps.values()),
        }
    state["results"] = results
    restore_enabled()

refs = [
    (event.BakingProcessAboutToStart, on_about_to_start),
    (event.BakingProcessProgress, on_progress),
    (event.BakingProcessEnded, on_ended),
]
for event_cls, callback in refs:
    event.DISPATCHER.connect_strong(event_cls, callback)
builtins._sp_mcp_bake_refs = refs
try:
    for name, item in all_sets.items():
        baking.BakingParameters.from_texture_set(item).set_textureset_enabled(name in selected)
    stop_source = baking.bake_selected_textures_async()
    builtins._sp_mcp_bake_stop_source = stop_source
    if state["status"] == "starting":
        state["status"] = "running"
except Exception as exc:
    restore_enabled()
    state["status"] = "failed"
    state["error"] = f"{type(exc).__name__}: {exc}"
    state["finished_at"] = time.time()
    raise
result = dict(state)
'''
        result = _unwrap(
            self.remote.execute_python_json(
                code, {"texture_sets": texture_sets}
            )
        )
        result["preflight"] = plan
        result["backup"] = backup
        return result

    def start_bake(
        self,
        texture_set: str,
        confirm: bool = False,
        backup_path: str | None = None,
        backup_mode: str = "Incremental",
        overwrite_backup: bool = False,
    ) -> dict[str, Any]:
        if not texture_set.strip():
            raise ValueError("texture_set must be a non-empty name")
        if not confirm:
            raise PermissionError("Baking modifies mesh maps; set confirm=true to start")
        backup = (
            self.save_project_copy(backup_path, backup_mode, overwrite_backup)
            if backup_path
            else None
        )
        code = '''
import builtins
import time
import uuid
import substance_painter.baking as baking
import substance_painter.event as event
import substance_painter.project as project
import substance_painter.textureset as textureset

if not project.is_open():
    raise RuntimeError("No project is open")
if project.is_busy():
    raise RuntimeError("Painter is busy")
target = textureset.TextureSet.from_name(params["texture_set"])
bake_settings = baking.BakingParameters.from_texture_set(target)
if not bake_settings.is_textureset_enabled() or not bake_settings.get_enabled_uv_tiles():
    raise RuntimeError(
        f"Texture Set is disabled for baking or has no enabled UV tiles: {params['texture_set']}"
    )
previous_refs = getattr(builtins, "_sp_mcp_bake_refs", None)
if previous_refs:
    for event_cls, callback in previous_refs:
        try:
            event.DISPATCHER.disconnect(event_cls, callback)
        except Exception:
            pass

job_id = uuid.uuid4().hex
state = {
    "job_id": job_id,
    "operation": "bake",
    "texture_set": params["texture_set"],
    "status": "starting",
    "progress": 0.0,
    "cancel_requested": False,
    "started_at": time.time(),
    "finished_at": None,
    "error": None,
}
builtins._sp_mcp_bake_state = state

def on_about_to_start(message):
    current = getattr(builtins, "_sp_mcp_bake_state", None)
    if current is state:
        state["status"] = "running"

def on_progress(message):
    current = getattr(builtins, "_sp_mcp_bake_state", None)
    if current is state:
        state["status"] = "running"
        state["progress"] = max(0.0, min(1.0, float(message.progress)))

def on_ended(message):
    current = getattr(builtins, "_sp_mcp_bake_state", None)
    if current is state:
        status = message.status.name
        state["status"] = {
            "Success": "success", "Cancel": "cancelled", "Fail": "failed"
        }.get(status, status.casefold())
        state["progress"] = 1.0 if status == "Success" else state["progress"]
        state["finished_at"] = time.time()

refs = [
    (event.BakingProcessAboutToStart, on_about_to_start),
    (event.BakingProcessProgress, on_progress),
    (event.BakingProcessEnded, on_ended),
]
for event_cls, callback in refs:
    event.DISPATCHER.connect_strong(event_cls, callback)
builtins._sp_mcp_bake_refs = refs
try:
    stop_source = baking.bake_async(target)
    builtins._sp_mcp_bake_stop_source = stop_source
    if state["status"] == "starting":
        state["status"] = "running"
except Exception as exc:
    state["status"] = "failed"
    state["error"] = f"{type(exc).__name__}: {exc}"
    state["finished_at"] = time.time()
    raise
result = dict(state)
'''
        result = _unwrap(
            self.remote.execute_python_json(code, {"texture_set": texture_set})
        )
        result["backup"] = backup
        return result

    def get_bake_job(self, job_id: str | None = None) -> dict[str, Any]:
        code = '''
import builtins
import substance_painter.project as project
state = getattr(builtins, "_sp_mcp_bake_state", None)
if state is None:
    result = {"found": False, "job": None, "busy": project.is_busy()}
elif params.get("job_id") and state["job_id"] != params["job_id"]:
    result = {"found": False, "job": None, "busy": project.is_busy()}
else:
    result = {"found": True, "job": dict(state), "busy": project.is_busy()}
'''
        return _unwrap(self.remote.execute_python_json(code, {"job_id": job_id}))

    def cancel_bake(self, job_id: str) -> dict[str, Any]:
        if not job_id.strip():
            raise ValueError("job_id must be non-empty")
        code = '''
import builtins
state = getattr(builtins, "_sp_mcp_bake_state", None)
stop_source = getattr(builtins, "_sp_mcp_bake_stop_source", None)
if state is None or state["job_id"] != params["job_id"]:
    raise ValueError(f"Unknown bake job: {params['job_id']}")
if state["status"] not in {"starting", "running"}:
    requested = False
else:
    requested = bool(stop_source and stop_source.request_stop())
    state["cancel_requested"] = requested or bool(
        stop_source and stop_source.stop_requested()
    )
result = {"requested": requested, "job": dict(state)}
'''
        return _unwrap(self.remote.execute_python_json(code, {"job_id": job_id}))

    def plan_mesh_reload(
        self,
        mesh_file_path: str,
        backup_path: str | None = None,
        backup_mode: str = "Incremental",
        overwrite_backup: bool = False,
        preserve_strokes: bool = True,
        import_cameras: bool = True,
    ) -> dict[str, Any]:
        mesh = self._validate_mesh_path(mesh_file_path)
        backup = None
        if backup_path:
            backup_file = self._validate_allowed_path(
                backup_path, "SP_MCP_PROJECT_ROOTS", "Mesh reload backup"
            )
            if backup_file.suffix.casefold() != ".spp":
                raise ValueError("backup_path must use the .spp extension")
            if backup_file.exists() and not overwrite_backup:
                raise FileExistsError(
                    "Backup already exists; set overwrite_backup=true to replace it: "
                    f"{backup_file}"
                )
            if backup_mode not in {"Incremental", "Full"}:
                raise ValueError("backup_mode must be Incremental or Full")
            backup = {
                "path": str(backup_file),
                "mode": backup_mode,
                "overwrite": overwrite_backup,
            }
        code = '''
import substance_painter.project as project
import substance_painter.textureset as textureset
if not project.is_open():
    raise RuntimeError("No project is open")
sets = []
for item in textureset.all_texture_sets():
    name = item.name() if callable(item.name) else item.name
    sets.append({
        "name": name,
        "uv_tiles": [str(tile) for tile in item.all_uv_tiles()],
        "stacks": [stack.name() for stack in item.all_stacks()],
    })
result = {
    "busy": project.is_busy(),
    "current_mesh": project.last_imported_mesh_path(),
    "texture_sets": sets,
}
'''
        current = _unwrap(self.remote.execute_python_json(code))
        return {
            "mesh_file_path": str(mesh),
            "bytes": mesh.stat().st_size,
            "preserve_strokes": preserve_strokes,
            "import_cameras": import_cameras,
            "backup": backup,
            "current": current,
            "requires_confirmation": True,
        }

    def start_mesh_reload(
        self,
        mesh_file_path: str,
        confirm: bool = False,
        backup_path: str | None = None,
        backup_mode: str = "Incremental",
        overwrite_backup: bool = False,
        preserve_strokes: bool = True,
        import_cameras: bool = True,
    ) -> dict[str, Any]:
        if not confirm:
            raise PermissionError("Mesh reload modifies the project; set confirm=true to start")
        plan = self.plan_mesh_reload(
            mesh_file_path,
            backup_path,
            backup_mode,
            overwrite_backup,
            preserve_strokes,
            import_cameras,
        )
        backup = (
            self.save_project_copy(backup_path, backup_mode, overwrite_backup)
            if backup_path
            else None
        )
        code = '''
import builtins
import time
import uuid
import substance_painter.project as project
import substance_painter.textureset as textureset

if project.is_busy():
    raise RuntimeError("Painter is busy")
job_id = uuid.uuid4().hex
before_sets = [
    item.name() if callable(item.name) else item.name
    for item in textureset.all_texture_sets()
]
state = {
    "job_id": job_id,
    "operation": "mesh_reload",
    "status": "running",
    "mesh_file_path": params["mesh_file_path"],
    "previous_mesh": project.last_imported_mesh_path(),
    "preserve_strokes": params["preserve_strokes"],
    "import_cameras": params["import_cameras"],
    "started_at": time.time(),
    "finished_at": None,
    "texture_sets_before": before_sets,
    "texture_sets_after": None,
    "added_texture_sets": [],
    "removed_texture_sets": [],
    "error": None,
}
builtins._sp_mcp_mesh_reload_state = state

def on_loaded(status):
    current = getattr(builtins, "_sp_mcp_mesh_reload_state", None)
    if current is not state:
        return
    after_sets = [
        item.name() if callable(item.name) else item.name
        for item in textureset.all_texture_sets()
    ]
    state["status"] = "success" if status.name == "SUCCESS" else "failed"
    state["finished_at"] = time.time()
    state["texture_sets_after"] = after_sets
    state["added_texture_sets"] = sorted(set(after_sets) - set(before_sets))
    state["removed_texture_sets"] = sorted(set(before_sets) - set(after_sets))
    if status.name != "SUCCESS":
        state["error"] = f"Painter mesh reload status: {status.name}"

builtins._sp_mcp_mesh_reload_callback = on_loaded
settings = project.MeshReloadingSettings(
    import_cameras=params["import_cameras"],
    preserve_strokes=params["preserve_strokes"],
)
try:
    project.reload_mesh(params["mesh_file_path"], settings, on_loaded)
except Exception as exc:
    state["status"] = "failed"
    state["error"] = f"{type(exc).__name__}: {exc}"
    state["finished_at"] = time.time()
    raise
result = dict(state)
'''
        result = _unwrap(
            self.remote.execute_python_json(
                code,
                {
                    "mesh_file_path": Path(mesh_file_path).expanduser().resolve().as_posix(),
                    "preserve_strokes": preserve_strokes,
                    "import_cameras": import_cameras,
                },
            )
        )
        result["backup"] = backup
        result["plan"] = plan
        return result

    def get_mesh_reload_job(self, job_id: str | None = None) -> dict[str, Any]:
        code = '''
import builtins
import substance_painter.project as project
state = getattr(builtins, "_sp_mcp_mesh_reload_state", None)
if state is None:
    result = {"found": False, "job": None, "busy": project.is_busy()}
elif params.get("job_id") and state["job_id"] != params["job_id"]:
    result = {"found": False, "job": None, "busy": project.is_busy()}
else:
    result = {"found": True, "job": dict(state), "busy": project.is_busy()}
'''
        return _unwrap(self.remote.execute_python_json(code, {"job_id": job_id}))

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
    geometry = node.get_geometry_mask()
    geometry_type = type(geometry).__name__
    if isinstance(geometry, layerstack.GeometryMaskMeshParams):
        geometry_mask = {
            "type": "Mesh",
            "inclusion_list": geometry.inclusion_list,
            "elements": list(geometry.meshes),
        }
    elif isinstance(geometry, layerstack.GeometryMaskUVTilesParams):
        geometry_mask = {
            "type": "UVTile",
            "inclusion_list": geometry.inclusion_list,
            "elements": [1001 + tile.u + 10 * tile.v for tile in geometry.uv_tiles],
        }
    else:
        geometry_mask = {"type": geometry_type, "inclusion_list": None, "elements": []}
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
        "geometry_mask": geometry_mask,
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

    def get_geometry_mask(self, uid: int) -> dict[str, Any]:
        code = '''
import substance_painter.layerstack as layerstack

node = layerstack.get_node_by_uid(params["uid"])
if not isinstance(node, layerstack.LayerNode):
    raise TypeError(f"Node {params['uid']} does not support a geometry mask")
texture_set = node.get_texture_set()
current = node.get_geometry_mask()
if isinstance(current, layerstack.GeometryMaskMeshParams):
    mask_type = "Mesh"
    elements = list(current.meshes)
elif isinstance(current, layerstack.GeometryMaskUVTilesParams):
    mask_type = "UVTile"
    elements = [1001 + tile.u + 10 * tile.v for tile in current.uv_tiles]
else:
    mask_type = type(current).__name__
    elements = []
result = {
    "uid": node.uid(),
    "name": node.get_name(),
    "type": mask_type,
    "inclusion_list": current.inclusion_list,
    "elements": elements,
    "available_meshes": list(texture_set.all_mesh_names()),
    "available_uv_tiles": [1001 + tile.u + 10 * tile.v for tile in texture_set.all_uv_tiles()],
}
'''
        return _unwrap(self.remote.execute_python_json(code, {"uid": uid}))

    def set_geometry_mask(
        self,
        uid: int,
        mask_type: str,
        elements: list[str | int],
        inclusion_list: bool = True,
    ) -> dict[str, Any]:
        normalized = mask_type.casefold()
        if normalized not in {"mesh", "uvtile", "uv_tile"}:
            raise ValueError("mask_type must be Mesh or UVTile")
        if not isinstance(elements, list):
            raise ValueError("elements must be a list")
        if normalized == "mesh" and any(not isinstance(value, str) for value in elements):
            raise ValueError("Mesh geometry mask elements must be mesh-name strings")
        if normalized != "mesh" and any(
            not isinstance(value, int) or isinstance(value, bool) or value < 1001
            for value in elements
        ):
            raise ValueError("UVTile geometry mask elements must be UDIM integers >= 1001")
        code = '''
import substance_painter.layerstack as layerstack

node = layerstack.get_node_by_uid(params["uid"])
if not isinstance(node, layerstack.LayerNode):
    raise TypeError(f"Node {params['uid']} does not support a geometry mask")
texture_set = node.get_texture_set()
if params["mask_type"] == "mesh":
    available = set(texture_set.all_mesh_names())
    missing = [name for name in params["elements"] if name not in available]
    if missing:
        raise ValueError(f"Unknown mesh names: {missing}")
    settings = layerstack.GeometryMaskMeshParams(
        inclusion_list=params["inclusion_list"], meshes=params["elements"]
    )
else:
    available = {1001 + tile.u + 10 * tile.v: tile for tile in texture_set.all_uv_tiles()}
    missing = [udim for udim in params["elements"] if udim not in available]
    if missing:
        raise ValueError(f"Unknown UV tiles: {missing}")
    settings = layerstack.GeometryMaskUVTilesParams(
        inclusion_list=params["inclusion_list"],
        uv_tiles=[available[udim] for udim in params["elements"]],
    )
node.set_geometry_mask(settings)
current = node.get_geometry_mask()
result = {
    "uid": node.uid(),
    "name": node.get_name(),
    "type": "Mesh" if isinstance(current, layerstack.GeometryMaskMeshParams) else "UVTile",
    "inclusion_list": current.inclusion_list,
    "elements": (list(current.meshes)
                 if isinstance(current, layerstack.GeometryMaskMeshParams)
                 else [1001 + tile.u + 10 * tile.v for tile in current.uv_tiles]),
}
'''
        return _unwrap(
            self.remote.execute_python_json(
                code,
                {
                    "uid": uid,
                    "mask_type": "mesh" if normalized == "mesh" else "uvtile",
                    "elements": elements,
                    "inclusion_list": inclusion_list,
                },
            )
        )

    def diff_layer_snapshots(
        self,
        before: dict[str, Any],
        after: dict[str, Any],
    ) -> dict[str, Any]:
        def flatten(snapshot: dict[str, Any]) -> dict[int, dict[str, Any]]:
            result: dict[int, dict[str, Any]] = {}

            def visit(nodes: list[dict[str, Any]], parents: list[str]) -> None:
                for index, node in enumerate(nodes):
                    clean = {key: value for key, value in node.items() if key != "children"}
                    clean["parents"] = parents
                    clean["index"] = index
                    result[int(node["uid"])] = clean
                    visit(node.get("children", []), [*parents, node["name"]])

            visit(snapshot.get("layers", []), [])
            return result

        old = flatten(before)
        new = flatten(after)
        added = [new[uid] for uid in sorted(new.keys() - old.keys())]
        removed = [old[uid] for uid in sorted(old.keys() - new.keys())]
        changed = []
        for uid in sorted(old.keys() & new.keys()):
            fields = {
                key: {"before": old[uid].get(key), "after": new[uid].get(key)}
                for key in sorted(old[uid].keys() | new[uid].keys())
                if old[uid].get(key) != new[uid].get(key)
            }
            if fields:
                changed.append({"uid": uid, "name": new[uid].get("name"), "fields": fields})
        return {
            "before_sha256": before.get("sha256"),
            "after_sha256": after.get("sha256"),
            "equal": not added and not removed and not changed,
            "added": added,
            "removed": removed,
            "changed": changed,
            "counts": {"added": len(added), "removed": len(removed), "changed": len(changed)},
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

    def plan_layer_recipe(
        self,
        recipe: list[dict[str, Any]],
        texture_set: str | None = None,
        backup_path: str | None = None,
        backup_mode: str = "Incremental",
        overwrite_backup: bool = False,
    ) -> dict[str, Any]:
        self._validate_recipe(recipe)
        normalized = self._normalize_recipe(recipe)
        if backup_path is not None:
            backup = self._validate_allowed_path(
                backup_path, "SP_MCP_PROJECT_ROOTS", "Recipe backup"
            )
            if backup.suffix.casefold() != ".spp":
                raise ValueError("backup_path must use the .spp extension")
            if backup.exists() and not overwrite_backup:
                raise FileExistsError(
                    f"Recipe backup already exists; set overwrite_backup=true: {backup}"
                )
        if backup_mode not in {"Incremental", "Full"}:
            raise ValueError("backup_mode must be Incremental or Full")
        code = '''
import substance_painter.textureset as textureset

stack = (textureset.TextureSet.from_name(params["texture_set"]).get_stack()
         if params.get("texture_set") else textureset.get_active_stack())
aliases = {"Roughness": "SpecularRoughness", "Metallic": "BaseMetalness", "Emission": "Emissive"}
channels = sorted({
    name
    for item in params["flat"]
    for name in (list(item.get("channels", {}))
                 + list(item.get("active_channels", []))
                 + (["BaseColor"] if item.get("base_color") is not None else []))
})
resolved = {}
for name in channels:
    canonical = name if name in textureset.ChannelType.__members__ else aliases.get(name)
    if not canonical or canonical not in textureset.ChannelType.__members__:
        raise ValueError(f"Unknown channel: {name}")
    resolved[name] = canonical
material = stack.material()
result = {
    "texture_set": material.name() if callable(material.name) else material.name,
    "stack": stack.name(),
    "resolved_channels": resolved,
}
'''

        flat: list[dict[str, Any]] = []

        def visit(items: list[dict[str, Any]]) -> None:
            for item in items:
                flat.append(item)
                visit(item.get("children") or [])

        visit(normalized)
        runtime = _unwrap(
            self.remote.execute_python_json(
                code, {"texture_set": texture_set, "flat": flat}
            )
        )
        counts = Counter(str(item["type"]).casefold() for item in flat)
        current = self.snapshot_layer_tree(texture_set)
        return {
            "valid": True,
            "texture_set": runtime["texture_set"],
            "stack": runtime["stack"],
            "node_count": len(flat),
            "node_types": dict(sorted(counts.items())),
            "resolved_channels": runtime["resolved_channels"],
            "backup": {
                "requested": backup_path is not None,
                "path": str(Path(backup_path).expanduser().resolve()) if backup_path else None,
                "mode": backup_mode if backup_path else None,
                "overwrite": overwrite_backup if backup_path else False,
            },
            "before_sha256": current["sha256"],
            "recipe": normalized,
        }

    def create_layer_recipe(
        self,
        recipe: list[dict[str, Any]],
        texture_set: str | None = None,
        backup_path: str | None = None,
        backup_mode: str = "Incremental",
        overwrite_backup: bool = False,
    ) -> dict[str, Any]:
        plan = self.plan_layer_recipe(
            recipe,
            texture_set,
            backup_path,
            backup_mode,
            overwrite_backup,
        )
        backup = None
        if backup_path is not None:
            backup = self.save_project_copy(
                backup_path, mode=backup_mode, overwrite=overwrite_backup
            )
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
        result = _unwrap(
            self.remote.execute_python_json(
                code, {"recipe": self._normalize_recipe(recipe), "texture_set": texture_set}
            )
        )
        try:
            after = self.snapshot_layer_tree(texture_set)
        except Exception:
            for node in reversed(result.get("nodes", [])):
                try:
                    self.delete_layer(int(node["uid"]))
                except Exception:
                    pass
            raise
        result["plan"] = {key: value for key, value in plan.items() if key != "recipe"}
        result["backup"] = backup
        result["after_sha256"] = after["sha256"]
        return result

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

    def insert_smart_material(
        self,
        resource_url: str,
        texture_set: str | None = None,
        parent_uid: int | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        if not resource_url.startswith("resource://"):
            raise ValueError("resource_url must start with resource://")
        code = '''
import substance_painter.layerstack as layerstack
import substance_painter.resource as resource
import substance_painter.textureset as textureset

stack = (textureset.TextureSet.from_name(params["texture_set"]).get_stack()
         if params.get("texture_set") else textureset.get_active_stack())
if params.get("parent_uid") is not None:
    parent = layerstack.get_node_by_uid(params["parent_uid"])
    if not isinstance(parent, layerstack.GroupLayerNode):
        raise TypeError("parent_uid must identify a GroupLayerNode")
    position = layerstack.InsertPosition.inside_node(parent, layerstack.NodeStack.Substack)
else:
    position = layerstack.InsertPosition.from_textureset_stack(stack)
node = None
try:
    resource_id = resource.ResourceID.from_url(params["resource_url"])
    node = layerstack.insert_smart_material(position, resource_id)
    if params.get("name"):
        node.set_name(params["name"])
except Exception:
    if node is not None:
        try:
            layerstack.delete_node(node)
        except Exception:
            pass
    raise
result = {
    "uid": node.uid(),
    "name": node.get_name(),
    "type": type(node).__name__,
    "resource_url": params["resource_url"],
    "child_count": len(node.sub_layers()),
}
'''
        return _unwrap(
            self.remote.execute_python_json(
                code,
                {
                    "resource_url": resource_url,
                    "texture_set": texture_set,
                    "parent_uid": parent_uid,
                    "name": name,
                },
            )
        )

    def apply_smart_mask(self, uid: int, resource_url: str) -> dict[str, Any]:
        return self.insert_mask_effect(uid, "smart_mask", resource_url=resource_url)

    def get_fill_projection(self, uid: int) -> dict[str, Any]:
        code = '''
import substance_painter.layerstack as layerstack

node = layerstack.get_node_by_uid(params["uid"])
if not isinstance(node, layerstack.FillLayerNode):
    raise TypeError(f"Node {params['uid']} is not a FillLayerNode")
projection = node.get_projection_parameters()
transform = getattr(projection, "uv_transformation", None) if projection else None
projection_3d = getattr(projection, "projection_3d", None) if projection else None
depth_culling = getattr(projection, "depth_culling", None) if projection else None
backface_culling = getattr(projection, "backface_culling", None) if projection else None
result = {
    "uid": node.uid(),
    "name": node.get_name(),
    "mode": node.get_projection_mode().name,
    "filtering_mode": getattr(getattr(projection, "filtering_mode", None), "name", None),
    "uv_wrapping_mode": getattr(getattr(projection, "uv_wrapping_mode", None), "name", None),
    "hardness": getattr(projection, "hardness", None),
    "shape_crop_mode": getattr(getattr(projection, "shape_crop_mode", None), "name", None),
    "angle": getattr(projection, "angle", None),
    "backface_culling_angle": getattr(projection, "backface_culling_angle", None),
    "transform": ({
        "scale_mode": transform.scale_mode.name,
        "scale": list(transform.scale) if transform.scale is not None else None,
        "rotation": transform.rotation,
        "offset": list(transform.offset) if transform.offset is not None else None,
    } if transform else None),
    "projection_3d": ({
        "offset": list(projection_3d.offset),
        "rotation": list(projection_3d.rotation),
        "scale": list(projection_3d.scale),
    } if projection_3d else None),
    "depth_culling": ({
        "enabled": depth_culling.enabled,
        "hardness": depth_culling.hardness,
    } if depth_culling else None),
    "backface_culling": ({
        "enabled": backface_culling.enabled,
        "hardness": backface_culling.hardness,
    } if backface_culling else None),
}
'''
        return _unwrap(self.remote.execute_python_json(code, {"uid": uid}))

    def set_fill_projection(
        self,
        uid: int,
        mode: str,
        scale: list[float] | None = None,
        rotation: float | None = None,
        offset: list[float] | None = None,
    ) -> dict[str, Any]:
        if mode not in {"Fill", "UV", "Triplanar"}:
            raise ValueError("mode must be Fill, UV, or Triplanar")
        for label, value in (("scale", scale), ("offset", offset)):
            if value is not None and (
                len(value) != 2
                or any(not isinstance(component, (int, float)) for component in value)
            ):
                raise ValueError(f"{label} must contain exactly two numbers")
        if scale is not None and any(value <= 0 for value in scale):
            raise ValueError("scale components must be greater than zero")
        if rotation is not None and not isinstance(rotation, (int, float)):
            raise ValueError("rotation must be a number")
        if mode == "Fill" and any(value is not None for value in (scale, rotation, offset)):
            raise ValueError("Fill projection does not accept transform parameters")
        if mode == "Triplanar" and offset is not None:
            raise ValueError("Triplanar projection does not support offset")
        code = '''
import dataclasses
import substance_painter.layerstack as layerstack

node = layerstack.get_node_by_uid(params["uid"])
if not isinstance(node, layerstack.FillLayerNode):
    raise TypeError(f"Node {params['uid']} is not a FillLayerNode")
original_mode = node.get_projection_mode()
original_params = node.get_projection_parameters()
try:
    mode = layerstack.ProjectionMode.__members__[params["mode"]]
    node.set_projection_mode(mode)
    if mode != layerstack.ProjectionMode.Fill:
        projection = node.get_projection_parameters()
        transform = projection.uv_transformation
        transform = dataclasses.replace(
            transform,
            scale=(params["scale"] if params.get("scale") is not None else transform.scale),
            rotation=(params["rotation"] if params.get("rotation") is not None else transform.rotation),
            offset=(params["offset"] if params.get("offset") is not None else transform.offset),
        )
        node.set_projection_parameters(dataclasses.replace(projection, uv_transformation=transform))
except Exception:
    node.set_projection_mode(original_mode)
    if original_params is not None:
        node.set_projection_parameters(original_params)
    raise
projection = node.get_projection_parameters()
transform = getattr(projection, "uv_transformation", None) if projection else None
result = {
    "uid": node.uid(),
    "name": node.get_name(),
    "mode": node.get_projection_mode().name,
    "transform": ({
        "scale_mode": transform.scale_mode.name,
        "scale": list(transform.scale) if transform.scale is not None else None,
        "rotation": transform.rotation,
        "offset": list(transform.offset) if transform.offset is not None else None,
    } if transform else None),
}
'''
        return _unwrap(
            self.remote.execute_python_json(
                code,
                {
                    "uid": uid,
                    "mode": mode,
                    "scale": scale,
                    "rotation": rotation,
                    "offset": offset,
                },
            )
        )

    def set_fill_projection_advanced(
        self,
        uid: int,
        mode: str,
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        supported = {"UV", "Triplanar", "Planar", "Spherical", "Cylindrical"}
        if mode not in supported:
            raise ValueError(f"mode must be one of: {', '.join(sorted(supported))}")
        if not isinstance(settings, dict):
            raise ValueError("settings must be an object")
        self._validate_projection_settings(mode, settings)
        code = '''
import dataclasses
import substance_painter.layerstack as layerstack

node = layerstack.get_node_by_uid(params["uid"])
if not isinstance(node, layerstack.FillLayerNode):
    raise TypeError(f"Node {params['uid']} is not a FillLayerNode")
original_mode = node.get_projection_mode()
original_params = node.get_projection_parameters()
try:
    node.set_projection_mode(layerstack.ProjectionMode.__members__[params["mode"]])
    projection = node.get_projection_parameters()
    values = params["settings"]
    changes = {}
    if values.get("filtering_mode") is not None:
        changes["filtering_mode"] = layerstack.FilteringMode.__members__[values["filtering_mode"]]
    if values.get("uv_wrapping_mode") is not None:
        changes["uv_wrapping_mode"] = layerstack.UVWrapMode.__members__[values["uv_wrapping_mode"]]
    if values.get("shape_crop_mode") is not None:
        changes["shape_crop_mode"] = layerstack.ShapeCropMode.__members__[values["shape_crop_mode"]]
    if values.get("hardness") is not None:
        changes["hardness"] = values["hardness"]
    if values.get("angle") is not None:
        changes["angle"] = values["angle"]
    if values.get("backface_culling_angle") is not None:
        changes["backface_culling_angle"] = values["backface_culling_angle"]
    transform_values = values.get("transform") or {}
    if transform_values:
        transform = projection.uv_transformation
        transform = dataclasses.replace(
            transform,
            scale=transform_values.get("scale", transform.scale),
            rotation=transform_values.get("rotation", transform.rotation),
            offset=transform_values.get("offset", transform.offset),
        )
        changes["uv_transformation"] = transform
    projection_3d_values = values.get("projection_3d") or {}
    if projection_3d_values:
        projection_3d = projection.projection_3d
        projection_3d = dataclasses.replace(
            projection_3d,
            offset=projection_3d_values.get("offset", projection_3d.offset),
            rotation=projection_3d_values.get("rotation", projection_3d.rotation),
            scale=projection_3d_values.get("scale", projection_3d.scale),
        )
        changes["projection_3d"] = projection_3d
    for key in ("depth_culling", "backface_culling"):
        culling_values = values.get(key) or {}
        if culling_values:
            current = getattr(projection, key)
            changes[key] = dataclasses.replace(
                current,
                enabled=culling_values.get("enabled", current.enabled),
                hardness=culling_values.get("hardness", current.hardness),
            )
    node.set_projection_parameters(dataclasses.replace(projection, **changes))
except Exception:
    node.set_projection_mode(original_mode)
    if original_params is not None:
        node.set_projection_parameters(original_params)
    raise
projection = node.get_projection_parameters()
transform = projection.uv_transformation
projection_3d = getattr(projection, "projection_3d", None)
result = {
    "uid": node.uid(),
    "name": node.get_name(),
    "mode": node.get_projection_mode().name,
    "transform": {
        "scale": list(transform.scale) if transform.scale is not None else None,
        "rotation": transform.rotation,
        "offset": list(transform.offset) if transform.offset is not None else None,
    },
    "projection_3d": ({
        "offset": list(projection_3d.offset),
        "rotation": list(projection_3d.rotation),
        "scale": list(projection_3d.scale),
    } if projection_3d else None),
    "filtering_mode": getattr(getattr(projection, "filtering_mode", None), "name", None),
    "uv_wrapping_mode": getattr(getattr(projection, "uv_wrapping_mode", None), "name", None),
    "shape_crop_mode": getattr(getattr(projection, "shape_crop_mode", None), "name", None),
    "hardness": getattr(projection, "hardness", None),
    "angle": getattr(projection, "angle", None),
    "backface_culling_angle": getattr(projection, "backface_culling_angle", None),
}
'''
        return _unwrap(
            self.remote.execute_python_json(
                code, {"uid": uid, "mode": mode, "settings": settings}
            )
        )

    def get_fill_sources(self, uid: int) -> dict[str, Any]:
        code = '''
import substance_painter.layerstack as layerstack

node = layerstack.get_node_by_uid(params["uid"])
if not isinstance(node, layerstack.FillLayerNode):
    raise TypeError(f"Node {params['uid']} is not a FillLayerNode")

def describe(source):
    resource_id = getattr(source, "resource_id", None)
    color = None
    if hasattr(source, "get_color"):
        value = source.get_color()
        color = {
            "value": list(value.value_raw),
            "color_space": str(value.color_space),
        }
    return {
        "type": type(source).__name__,
        "resource_url": resource_id.url() if resource_id else None,
        "color": color,
        "uid": source.uid() if hasattr(source, "uid") and callable(source.uid) else None,
    }

if node.source_mode.name == "Material":
    material = describe(node.get_material_source())
    channels = {}
else:
    material = None
    channels = {
        channel.name: describe(node.get_source(channel))
        for channel in sorted(node.active_channels, key=lambda item: item.name)
    }
result = {
    "uid": node.uid(),
    "name": node.get_name(),
    "source_mode": node.source_mode.name,
    "material": material,
    "channels": channels,
}
'''
        return _unwrap(self.remote.execute_python_json(code, {"uid": uid}))

    def get_procedural_inputs(
        self, uid: int, channel: str | None = None
    ) -> dict[str, Any]:
        code = '''
import substance_painter.layerstack as layerstack
import substance_painter.textureset as textureset

def resolve_source(node, requested):
    if isinstance(node, (layerstack.GeneratorEffectNode, layerstack.FilterEffectNode)):
        if requested is not None:
            raise ValueError("channel must be omitted for Generator/Filter effects")
        source = node.get_source()
        if source is None:
            raise ValueError("Generator/Filter effect has no procedural source")
        return source, None
    if node.source_mode.name == "Material":
        if requested is not None:
            raise ValueError("channel must be omitted for a material-mode Fill")
        return node.get_material_source(), None
    if not requested:
        raise ValueError("channel is required for a split-mode Fill")
    aliases = {"Roughness": "SpecularRoughness", "Metallic": "BaseMetalness", "Emission": "Emissive"}
    name = requested if requested in textureset.ChannelType.__members__ else aliases.get(requested)
    if not name or name not in textureset.ChannelType.__members__:
        raise ValueError(f"Unknown channel: {requested}")
    resolved = textureset.ChannelType.__members__[name]
    if resolved not in node.active_channels:
        raise ValueError(f"Channel is not active on this Fill: {requested}")
    return node.get_source(resolved), resolved.name

def describe(item):
    resource_url = None
    try:
        resource_id = getattr(item, "resource_id", None)
    except ValueError:
        resource_id = None
    if resource_id is not None:
        try:
            resource_url = resource_id.url()
        except ValueError:
            resource_url = None
    color = None
    if hasattr(item, "get_color"):
        value = item.get_color()
        color = {"value": list(value.value_raw), "color_space": str(value.color_space)}
    anchor_uid = None
    if hasattr(item, "anchor"):
        anchor_uid = item.anchor().uid()
    return {
        "type": type(item).__name__,
        "resource_url": resource_url,
        "color": color,
        "anchor_uid": anchor_uid,
        "uid": item.uid() if hasattr(item, "uid") and callable(item.uid) else None,
    }

node = layerstack.get_node_by_uid(params["uid"])
supported = (
    layerstack.FillLayerNode,
    layerstack.FillEffectNode,
    layerstack.GeneratorEffectNode,
    layerstack.FilterEffectNode,
)
if not isinstance(node, supported):
    raise TypeError(f"Node {params['uid']} has no supported procedural source")
source, channel_name = resolve_source(node, params.get("channel"))
if not hasattr(source, "image_inputs") or not hasattr(source, "get_source"):
    raise TypeError(f"Fill source {type(source).__name__} has no procedural image inputs")
result = {
    "uid": node.uid(),
    "name": node.get_name(),
    "source_mode": getattr(getattr(node, "source_mode", None), "name", None),
    "node_type": type(node).__name__,
    "channel": channel_name,
    "source_type": type(source).__name__,
    "inputs": {
        name: describe(source.get_source(name)) for name in source.image_inputs
    },
}
'''
        return _unwrap(
            self.remote.execute_python_json(code, {"uid": uid, "channel": channel})
        )

    def set_procedural_input(
        self,
        uid: int,
        input_name: str,
        resource_url: str | None = None,
        channel: str | None = None,
        reset: bool = False,
    ) -> dict[str, Any]:
        if not input_name.strip():
            raise ValueError("input_name must be a non-empty identifier")
        if reset == (resource_url is not None):
            raise ValueError("Provide exactly one of resource_url or reset=true")
        if resource_url is not None and not resource_url.startswith("resource://"):
            raise ValueError("resource_url must start with resource://")
        code = '''
import substance_painter.layerstack as layerstack
import substance_painter.resource as resource
import substance_painter.textureset as textureset

def resolve_source(node, requested):
    if isinstance(node, (layerstack.GeneratorEffectNode, layerstack.FilterEffectNode)):
        if requested is not None:
            raise ValueError("channel must be omitted for Generator/Filter effects")
        source = node.get_source()
        if source is None:
            raise ValueError("Generator/Filter effect has no procedural source")
        return source, None
    if node.source_mode.name == "Material":
        if requested is not None:
            raise ValueError("channel must be omitted for a material-mode Fill")
        return node.get_material_source(), None
    if not requested:
        raise ValueError("channel is required for a split-mode Fill")
    aliases = {"Roughness": "SpecularRoughness", "Metallic": "BaseMetalness", "Emission": "Emissive"}
    name = requested if requested in textureset.ChannelType.__members__ else aliases.get(requested)
    if not name or name not in textureset.ChannelType.__members__:
        raise ValueError(f"Unknown channel: {requested}")
    resolved = textureset.ChannelType.__members__[name]
    if resolved not in node.active_channels:
        raise ValueError(f"Channel is not active on this Fill: {requested}")
    return node.get_source(resolved), resolved.name

def describe(item):
    resource_url = None
    try:
        resource_id = getattr(item, "resource_id", None)
    except ValueError:
        resource_id = None
    if resource_id is not None:
        try:
            resource_url = resource_id.url()
        except ValueError:
            resource_url = None
    color = None
    if hasattr(item, "get_color"):
        value = item.get_color()
        color = {"value": list(value.value_raw), "color_space": str(value.color_space)}
    anchor_uid = item.anchor().uid() if hasattr(item, "anchor") else None
    return {
        "type": type(item).__name__,
        "resource_url": resource_url,
        "color": color,
        "anchor_uid": anchor_uid,
        "uid": item.uid() if hasattr(item, "uid") and callable(item.uid) else None,
    }

node = layerstack.get_node_by_uid(params["uid"])
supported = (
    layerstack.FillLayerNode,
    layerstack.FillEffectNode,
    layerstack.GeneratorEffectNode,
    layerstack.FilterEffectNode,
)
if not isinstance(node, supported):
    raise TypeError(f"Node {params['uid']} has no supported procedural source")
source, channel_name = resolve_source(node, params.get("channel"))
if not hasattr(source, "image_inputs") or not hasattr(source, "get_source"):
    raise TypeError(f"Fill source {type(source).__name__} has no procedural image inputs")
if params["input_name"] not in source.image_inputs:
    raise ValueError(f"Unknown procedural image input: {params['input_name']}")
original = source.get_source(params["input_name"])
original_invalid_resource = False
try:
    original_resource = getattr(original, "resource_id", None)
except ValueError:
    original_resource = None
    original_invalid_resource = True
original_color = original.get_color() if hasattr(original, "get_color") else None
original_anchor = original.anchor() if hasattr(original, "anchor") else None
if (original_resource is None and original_color is None and original_anchor is None
        and not original_invalid_resource):
    raise TypeError(f"Cannot safely restore source type: {type(original).__name__}")
try:
    if params.get("resource_url") is not None:
        resource_id = resource.ResourceID.from_url(params["resource_url"])
        if not resource.Resource.retrieve(resource_id):
            raise ValueError(f"Resource not found: {params['resource_url']}")
        updated = source.set_source(params["input_name"], resource_id)
    else:
        source.reset_source(params["input_name"])
        updated = source.get_source(params["input_name"])
except Exception:
    try:
        if original_resource is not None:
            source.set_source(params["input_name"], original_resource)
        elif original_color is not None:
            source.set_source(params["input_name"], original_color)
        elif original_anchor is not None:
            source.set_source(params["input_name"], original_anchor)
        else:
            source.reset_source(params["input_name"])
    except Exception:
        pass
    raise
result = {
    "uid": node.uid(),
    "name": node.get_name(),
    "source_mode": getattr(getattr(node, "source_mode", None), "name", None),
    "node_type": type(node).__name__,
    "channel": channel_name,
    "input_name": params["input_name"],
    "source": describe(updated),
    "reset": params["resource_url"] is None,
}
'''
        return _unwrap(
            self.remote.execute_python_json(
                code,
                {
                    "uid": uid,
                    "input_name": input_name,
                    "resource_url": resource_url,
                    "channel": channel,
                },
            )
        )

    def set_fill_resource(
        self,
        uid: int,
        resource_url: str,
        channel: str | None = None,
        material_mode: bool = False,
    ) -> dict[str, Any]:
        if not resource_url.startswith("resource://"):
            raise ValueError("resource_url must start with resource://")
        if material_mode and channel is not None:
            raise ValueError("channel must be omitted when material_mode=true")
        if not material_mode and not channel:
            raise ValueError("channel is required when material_mode=false")
        code = '''
import substance_painter.layerstack as layerstack
import substance_painter.resource as resource
import substance_painter.textureset as textureset

node = layerstack.get_node_by_uid(params["uid"])
if not isinstance(node, layerstack.FillLayerNode):
    raise TypeError(f"Node {params['uid']} is not a FillLayerNode")
resource_id = resource.ResourceID.from_url(params["resource_url"])
aliases = {"Roughness": "SpecularRoughness", "Metallic": "BaseMetalness", "Emission": "Emissive"}
requested = params["channel"]
channel_name = None if params["material_mode"] else (
    requested if requested in textureset.ChannelType.__members__ else aliases.get(requested)
)
if not params["material_mode"] and (
    not channel_name or channel_name not in textureset.ChannelType.__members__
):
    raise ValueError(f"Unknown channel: {requested}")
resolved = textureset.ChannelType.__members__[channel_name] if channel_name else None
original_channels = set(node.active_channels)
original_source = node.get_source(resolved) if resolved in original_channels else None
try:
    if params["material_mode"]:
        source = node.set_material_source(resource_id)
        resolved_channel = None
    else:
        node.active_channels = original_channels | {resolved}
        source = node.set_source(resolved, resource_id)
        resolved_channel = resolved.name
except Exception:
    if resolved is not None:
        if original_source is not None:
            try:
                node.set_source(resolved, original_source)
            except Exception:
                pass
        node.active_channels = original_channels
    raise
verified_id = getattr(source, "resource_id", None)
result = {
    "uid": node.uid(),
    "name": node.get_name(),
    "source_mode": node.source_mode.name,
    "channel": resolved_channel,
    "source_type": type(source).__name__,
    "resource_url": verified_id.url() if verified_id else params["resource_url"],
}
'''
        return _unwrap(
            self.remote.execute_python_json(
                code,
                {
                    "uid": uid,
                    "resource_url": resource_url,
                    "channel": channel,
                    "material_mode": material_mode,
                },
            )
        )

    def get_fill_parameters(
        self, uid: int, channel: str | None = None
    ) -> dict[str, Any]:
        code = '''
import substance_painter.layerstack as layerstack
import substance_painter.textureset as textureset

def json_value(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if hasattr(value, "value_raw"):
        return {
            "type": "Color",
            "value": list(value.value_raw),
            "color_space": str(value.color_space),
        }
    return {"type": type(value).__name__, "value": str(value)}

def resolve_source(node, requested):
    if node.source_mode.name == "Material":
        if requested is not None:
            raise ValueError("channel must be omitted for a material-mode Fill")
        return node.get_material_source(), None
    if not requested:
        raise ValueError("channel is required for a split-mode Fill")
    aliases = {"Roughness": "SpecularRoughness", "Metallic": "BaseMetalness", "Emission": "Emissive"}
    name = requested if requested in textureset.ChannelType.__members__ else aliases.get(requested)
    if not name or name not in textureset.ChannelType.__members__:
        raise ValueError(f"Unknown channel: {requested}")
    resolved = textureset.ChannelType.__members__[name]
    if resolved not in node.active_channels:
        raise ValueError(f"Channel is not active on this Fill: {requested}")
    return node.get_source(resolved), resolved.name

node = layerstack.get_node_by_uid(params["uid"])
if not isinstance(node, layerstack.FillLayerNode):
    raise TypeError(f"Node {params['uid']} is not a FillLayerNode")
source, channel_name = resolve_source(node, params.get("channel"))
if not hasattr(source, "get_parameters") or not hasattr(source, "get_properties"):
    raise TypeError(f"Fill source {type(source).__name__} has no procedural parameters")
properties = source.get_properties()
values = source.get_parameters()
described = {}
for name, prop in properties.items():
    try:
        enums = prop.enum_values()
    except Exception:
        enums = {}
    described[name] = {
        "label": prop.label(),
        "widget": prop.widget_type(),
        "value": json_value(values.get(name, prop.value())),
        "enum_values": enums,
        "metadata": prop.properties(),
    }
result = {
    "uid": node.uid(),
    "name": node.get_name(),
    "source_mode": node.source_mode.name,
    "channel": channel_name,
    "source_type": type(source).__name__,
    "presets": source.get_preset_list() if hasattr(source, "get_preset_list") else [],
    "parameters": described,
}
'''
        return _unwrap(
            self.remote.execute_python_json(code, {"uid": uid, "channel": channel})
        )

    def set_fill_parameters(
        self,
        uid: int,
        values: dict[str, Any],
        channel: str | None = None,
    ) -> dict[str, Any]:
        self._validate_parameter_values(values)
        code = '''
import substance_painter.colormanagement as colormanagement
import substance_painter.layerstack as layerstack
import substance_painter.textureset as textureset

def json_value(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if hasattr(value, "value_raw"):
        return {"type": "Color", "value": list(value.value_raw), "color_space": str(value.color_space)}
    return {"type": type(value).__name__, "value": str(value)}

def resolve_source(node, requested):
    if node.source_mode.name == "Material":
        if requested is not None:
            raise ValueError("channel must be omitted for a material-mode Fill")
        return node.get_material_source(), None
    if not requested:
        raise ValueError("channel is required for a split-mode Fill")
    aliases = {"Roughness": "SpecularRoughness", "Metallic": "BaseMetalness", "Emission": "Emissive"}
    name = requested if requested in textureset.ChannelType.__members__ else aliases.get(requested)
    if not name or name not in textureset.ChannelType.__members__:
        raise ValueError(f"Unknown channel: {requested}")
    resolved = textureset.ChannelType.__members__[name]
    if resolved not in node.active_channels:
        raise ValueError(f"Channel is not active on this Fill: {requested}")
    return node.get_source(resolved), resolved.name

def convert(prop, value):
    current = prop.value()
    widget = prop.widget_type()
    if widget in {"File", "FileList", "Resource"}:
        raise ValueError(f"File/resource parameter editing is disabled: {prop.short_name()}")
    def checked(number):
        metadata = prop.properties()
        minimum = metadata.get("editorMin") if widget == "RandomSeed" else metadata.get("min")
        maximum = metadata.get("editorMax") if widget == "RandomSeed" else metadata.get("max")
        if isinstance(minimum, (int, float)) and number < minimum:
            raise ValueError(f"{prop.short_name()} must be >= {minimum}")
        if isinstance(maximum, (int, float)) and number > maximum:
            raise ValueError(f"{prop.short_name()} must be <= {maximum}")
        return number
    if widget == "Color":
        if not isinstance(value, list) or len(value) not in {3, 4}:
            raise ValueError(f"{prop.short_name()} must be an RGB or RGBA array")
        if any(not isinstance(item, (int, float)) or isinstance(item, bool) for item in value):
            raise ValueError(f"{prop.short_name()} color components must be numbers")
        return colormanagement.Color(*value[:3])
    if widget == "Combobox" and isinstance(value, str):
        enums = prop.enum_values()
        if value not in enums:
            raise ValueError(f"Unknown {prop.short_name()} enum label: {value}")
        return prop.enum_value(value)
    if isinstance(current, tuple):
        if not isinstance(value, list) or len(value) != len(current):
            raise ValueError(f"{prop.short_name()} must contain {len(current)} values")
        return tuple(value)
    if isinstance(current, bool):
        if not isinstance(value, bool):
            raise ValueError(f"{prop.short_name()} must be a boolean")
        return value
    if isinstance(current, int) and not isinstance(current, bool):
        if isinstance(value, bool) and widget == "Togglebutton":
            return int(value)
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{prop.short_name()} must be an integer")
        return checked(value)
    if isinstance(current, float):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"{prop.short_name()} must be a number")
        return checked(float(value))
    if isinstance(current, str):
        if not isinstance(value, str):
            raise ValueError(f"{prop.short_name()} must be a string")
        return value
    return value

node = layerstack.get_node_by_uid(params["uid"])
if not isinstance(node, layerstack.FillLayerNode):
    raise TypeError(f"Node {params['uid']} is not a FillLayerNode")
source, channel_name = resolve_source(node, params.get("channel"))
if not hasattr(source, "get_parameters") or not hasattr(source, "get_properties"):
    raise TypeError(f"Fill source {type(source).__name__} has no procedural parameters")
properties = source.get_properties()
unknown = sorted(set(params["values"]) - set(properties))
if unknown:
    raise ValueError(f"Unknown procedural parameters: {unknown}")
converted = {name: convert(properties[name], value) for name, value in params["values"].items()}
original = source.get_parameters()
try:
    source.set_parameters(converted)
except Exception:
    try:
        source.set_parameters({name: original[name] for name in converted})
    except Exception:
        pass
    raise
verified = source.get_parameters()
result = {
    "uid": node.uid(),
    "name": node.get_name(),
    "source_mode": node.source_mode.name,
    "channel": channel_name,
    "updated": {name: json_value(verified[name]) for name in converted},
}
'''
        return _unwrap(
            self.remote.execute_python_json(
                code, {"uid": uid, "channel": channel, "values": values}
            )
        )

    def apply_fill_preset(
        self, uid: int, preset: str, channel: str | None = None
    ) -> dict[str, Any]:
        if not preset.strip():
            raise ValueError("preset must be a non-empty name")
        code = '''
import substance_painter.layerstack as layerstack
import substance_painter.textureset as textureset

def resolve_source(node, requested):
    if node.source_mode.name == "Material":
        if requested is not None:
            raise ValueError("channel must be omitted for a material-mode Fill")
        return node.get_material_source(), None
    if not requested:
        raise ValueError("channel is required for a split-mode Fill")
    aliases = {"Roughness": "SpecularRoughness", "Metallic": "BaseMetalness", "Emission": "Emissive"}
    name = requested if requested in textureset.ChannelType.__members__ else aliases.get(requested)
    if not name or name not in textureset.ChannelType.__members__:
        raise ValueError(f"Unknown channel: {requested}")
    resolved = textureset.ChannelType.__members__[name]
    if resolved not in node.active_channels:
        raise ValueError(f"Channel is not active on this Fill: {requested}")
    return node.get_source(resolved), resolved.name

node = layerstack.get_node_by_uid(params["uid"])
if not isinstance(node, layerstack.FillLayerNode):
    raise TypeError(f"Node {params['uid']} is not a FillLayerNode")
source, channel_name = resolve_source(node, params.get("channel"))
if not hasattr(source, "get_preset_list") or not hasattr(source, "apply_preset"):
    raise TypeError(f"Fill source {type(source).__name__} has no procedural presets")
available = source.get_preset_list()
if params["preset"] not in available:
    raise ValueError(f"Unknown source preset: {params['preset']}")
original = source.get_parameters()
try:
    source.apply_preset(params["preset"])
except Exception:
    try:
        source.set_parameters(original)
    except Exception:
        pass
    raise
result = {
    "uid": node.uid(),
    "name": node.get_name(),
    "channel": channel_name,
    "preset": params["preset"],
    "available_presets": available,
}
'''
        return _unwrap(
            self.remote.execute_python_json(
                code, {"uid": uid, "preset": preset, "channel": channel}
            )
        )

    def list_anchor_points(self, texture_set: str | None = None) -> dict[str, Any]:
        code = '''
import substance_painter.layerstack as layerstack
import substance_painter.textureset as textureset

sets = ([textureset.TextureSet.from_name(params["texture_set"])]
        if params.get("texture_set") else textureset.all_texture_sets())

def flatten(nodes):
    output = []
    for node in nodes:
        output.append(node)
        if isinstance(node, layerstack.GroupLayerNode):
            output.extend(flatten(node.sub_layers()))
    return output

anchors = []
for item in sets:
    set_name = item.name() if callable(item.name) else item.name
    for stack in item.all_stacks():
        for owner in flatten(layerstack.get_root_layer_nodes(stack)):
            effects = list(owner.content_effects()) if isinstance(owner, layerstack.LayerNode) else []
            if isinstance(owner, layerstack.LayerNode) and owner.has_mask():
                effects.extend(owner.mask_effects())
            for effect in effects:
                if isinstance(effect, layerstack.AnchorPointEffectNode):
                    anchors.append({
                        "uid": effect.uid(),
                        "name": effect.get_name(),
                        "texture_set": set_name,
                        "stack": stack.name(),
                        "owner_uid": owner.uid(),
                        "owner_name": owner.get_name(),
                        "in_mask": effect in (owner.mask_effects() if owner.has_mask() else []),
                    })
result = {"count": len(anchors), "anchors": anchors}
'''
        return _unwrap(
            self.remote.execute_python_json(code, {"texture_set": texture_set})
        )

    def set_fill_anchor_source(
        self,
        uid: int,
        anchor_uid: int,
        channel: str | None = None,
        material_mode: bool = False,
    ) -> dict[str, Any]:
        if material_mode and channel is not None:
            raise ValueError("channel must be omitted when material_mode=true")
        if not material_mode and not channel:
            raise ValueError("channel is required when material_mode=false")
        code = '''
import substance_painter.layerstack as layerstack
import substance_painter.textureset as textureset

node = layerstack.get_node_by_uid(params["uid"])
anchor = layerstack.get_node_by_uid(params["anchor_uid"])
if not isinstance(node, layerstack.FillLayerNode):
    raise TypeError(f"Node {params['uid']} is not a FillLayerNode")
if not isinstance(anchor, layerstack.AnchorPointEffectNode):
    raise TypeError(f"Node {params['anchor_uid']} is not an AnchorPointEffectNode")
if node.get_texture_set() != anchor.get_texture_set():
    raise ValueError("Fill and Anchor Point must belong to the same Texture Set")
if params["material_mode"]:
    source = node.set_material_source(anchor)
    resolved_channel = None
else:
    aliases = {"Roughness": "SpecularRoughness", "Metallic": "BaseMetalness", "Emission": "Emissive"}
    requested = params["channel"]
    channel_name = requested if requested in textureset.ChannelType.__members__ else aliases.get(requested)
    if not channel_name or channel_name not in textureset.ChannelType.__members__:
        raise ValueError(f"Unknown channel: {requested}")
    resolved = textureset.ChannelType.__members__[channel_name]
    original_channels = set(node.active_channels)
    original_source = node.get_source(resolved) if resolved in original_channels else None
    try:
        node.active_channels = original_channels | {resolved}
        source = node.set_source(resolved, anchor)
    except Exception:
        if original_source is not None:
            try:
                node.set_source(resolved, original_source)
            except Exception:
                pass
        node.active_channels = original_channels
        raise
    resolved_channel = resolved.name
result = {
    "uid": node.uid(),
    "name": node.get_name(),
    "source_mode": node.source_mode.name,
    "channel": resolved_channel,
    "source_type": type(source).__name__,
    "anchor_uid": anchor.uid(),
    "anchor_name": anchor.get_name(),
}
'''
        return _unwrap(
            self.remote.execute_python_json(
                code,
                {
                    "uid": uid,
                    "anchor_uid": anchor_uid,
                    "channel": channel,
                    "material_mode": material_mode,
                },
            )
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

    def import_project_resource(
        self,
        file_path: str,
        usage: str,
        name: str | None = None,
        group: str | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        return self._import_resource(file_path, usage, name, group, "project", confirm)

    def import_session_resource(
        self,
        file_path: str,
        usage: str,
        name: str | None = None,
        group: str | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        return self._import_resource(file_path, usage, name, group, "session", confirm)

    def _import_resource(
        self,
        file_path: str,
        usage: str,
        name: str | None,
        group: str | None,
        scope: str,
        confirm: bool,
    ) -> dict[str, Any]:
        if not confirm:
            raise PermissionError(f"{scope.title()} resource import requires confirm=true")
        normalized_usage = usage.strip().upper()
        if normalized_usage not in SAFE_RESOURCE_IMPORT_USAGES:
            allowed = ", ".join(sorted(SAFE_RESOURCE_IMPORT_USAGES))
            raise ValueError(f"usage must be one of the safe import usages: {allowed}")
        for label, value in (("name", name), ("group", group)):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{label} must be a non-empty string when supplied")
        input_path = self._validate_resource_import_path(file_path)
        code = '''
import substance_painter.project as project
import substance_painter.resource as resource

if params["scope"] == "project":
    if not project.is_open():
        raise RuntimeError("No project is open")
    if project.is_busy():
        raise RuntimeError("Painter is busy and cannot import a project resource")
usage = resource.Usage.__members__[params["usage"]]
if params["scope"] == "project":
    item = resource.import_project_resource(
        params["file_path"], usage, params.get("name"), params.get("group")
    )
else:
    item = resource.import_session_resource(
        params["file_path"], usage, params.get("name"), params.get("group")
    )
identifier = item.identifier()
retrieved = resource.Resource.retrieve(identifier)
result = {
    "scope": params["scope"],
    "source_path": params["file_path"],
    "url": identifier.url(),
    "name": identifier.name,
    "context": identifier.context,
    "version": identifier.version,
    "location": item.location().name,
    "type": item.type().name,
    "category": item.category(),
    "usages": [value.name for value in item.usages()],
    "verified": any(candidate.identifier() == identifier for candidate in retrieved),
}
'''
        result = _unwrap(
            self.remote.execute_python_json(
                code,
                {
                    "scope": scope,
                    "file_path": input_path.as_posix(),
                    "usage": normalized_usage,
                    "name": name,
                    "group": group,
                },
            )
        )
        if not result.get("verified"):
            raise IOError(f"Painter resource import could not be verified: {input_path}")
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

    @staticmethod
    def _validate_projection_settings(mode: str, settings: dict[str, Any]) -> None:
        allowed = {
            "filtering_mode",
            "uv_wrapping_mode",
            "shape_crop_mode",
            "hardness",
            "angle",
            "backface_culling_angle",
            "transform",
            "projection_3d",
            "depth_culling",
            "backface_culling",
        }
        unknown = sorted(set(settings) - allowed)
        if unknown:
            raise ValueError(f"Unknown projection settings: {', '.join(unknown)}")
        supported_by_mode = {
            "UV": {"filtering_mode", "uv_wrapping_mode", "transform"},
            "Triplanar": {
                "filtering_mode",
                "shape_crop_mode",
                "hardness",
                "transform",
                "projection_3d",
            },
            "Planar": {
                "filtering_mode",
                "uv_wrapping_mode",
                "shape_crop_mode",
                "backface_culling_angle",
                "transform",
                "projection_3d",
                "depth_culling",
                "backface_culling",
            },
            "Spherical": {
                "filtering_mode",
                "uv_wrapping_mode",
                "shape_crop_mode",
                "transform",
                "projection_3d",
            },
            "Cylindrical": {
                "filtering_mode",
                "uv_wrapping_mode",
                "shape_crop_mode",
                "angle",
                "transform",
                "projection_3d",
                "backface_culling",
            },
        }
        unsupported = sorted(set(settings) - supported_by_mode[mode])
        if unsupported:
            raise ValueError(
                f"{mode} projection does not support: {', '.join(unsupported)}"
            )

        enums = {
            "filtering_mode": {"BilinearHQ", "BilinearSharp", "Nearest"},
            "uv_wrapping_mode": {
                "RepeatNone",
                "RepeatHorizontally",
                "RepeatVertically",
                "Repeat",
            },
            "shape_crop_mode": {"CroppedToShape", "ExtendsOutsideShape"},
        }
        for key, choices in enums.items():
            value = settings.get(key)
            if value is not None and value not in choices:
                raise ValueError(f"{key} must be one of: {', '.join(sorted(choices))}")

        for key in ("hardness",):
            value = settings.get(key)
            if value is not None and (
                not isinstance(value, (int, float)) or not 0 <= value <= 1
            ):
                raise ValueError(f"{key} must be a number in the 0..1 range")
        angle = settings.get("angle")
        if angle is not None and not isinstance(angle, (int, float)):
            raise ValueError("angle must be a number")
        backface_angle = settings.get("backface_culling_angle")
        if backface_angle is not None and (
            not isinstance(backface_angle, (int, float)) or not 45 <= backface_angle <= 135
        ):
            raise ValueError("backface_culling_angle must be in the 45..135 range")

        def validate_object(key: str, allowed_fields: set[str]) -> dict[str, Any]:
            value = settings.get(key) or {}
            if not isinstance(value, dict):
                raise ValueError(f"{key} must be an object")
            extra = sorted(set(value) - allowed_fields)
            if extra:
                raise ValueError(f"Unknown {key} settings: {', '.join(extra)}")
            return value

        transform = validate_object("transform", {"scale", "rotation", "offset"})
        projection_3d = validate_object(
            "projection_3d", {"offset", "rotation", "scale"}
        )
        for key in ("depth_culling", "backface_culling"):
            culling = validate_object(key, {"enabled", "hardness"})
            if "enabled" in culling and not isinstance(culling["enabled"], bool):
                raise ValueError(f"{key}.enabled must be a boolean")
            if "hardness" in culling and (
                not isinstance(culling["hardness"], (int, float))
                or not 0 <= culling["hardness"] <= 1
            ):
                raise ValueError(f"{key}.hardness must be in the 0..1 range")

        def validate_vector(container: dict[str, Any], key: str, length: int) -> None:
            if key not in container:
                return
            value = container[key]
            if (
                not isinstance(value, (list, tuple))
                or len(value) != length
                or any(not isinstance(component, (int, float)) for component in value)
            ):
                raise ValueError(f"{key} must contain exactly {length} numbers")

        for key in ("scale", "offset"):
            validate_vector(transform, key, 2)
        if "rotation" in transform and not isinstance(transform["rotation"], (int, float)):
            raise ValueError("transform.rotation must be a number")
        for key in ("offset", "rotation", "scale"):
            validate_vector(projection_3d, key, 3)
        if "scale" in transform and any(value <= 0 for value in transform["scale"]):
            raise ValueError("transform.scale components must be greater than zero")
        if "scale" in projection_3d and any(
            value <= 0 for value in projection_3d["scale"]
        ):
            raise ValueError("projection_3d.scale components must be greater than zero")
        if mode == "Triplanar" and "offset" in transform:
            raise ValueError("Triplanar projection does not support transform.offset")

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

    @classmethod
    def _validate_mesh_path(cls, mesh_file_path: str) -> Path:
        mesh = cls._validate_allowed_path(
            mesh_file_path, "SP_MCP_MESH_ROOTS", "Mesh reload"
        )
        if mesh.suffix.casefold() not in {".fbx", ".obj", ".dae", ".ply", ".usd"}:
            raise ValueError("mesh_file_path must use fbx, obj, dae, ply, or usd")
        if not mesh.is_file():
            raise FileNotFoundError(f"Mesh file does not exist: {mesh}")
        return mesh

    @classmethod
    def _validate_bake_mesh_path(cls, mesh_file_path: str) -> Path:
        mesh = cls._validate_allowed_path(
            mesh_file_path, "SP_MCP_BAKE_MESH_ROOTS", "Baking mesh input"
        )
        supported = {
            ".fbx", ".abc", ".obj", ".dae", ".ply", ".gltf", ".glb",
            ".usd", ".usda", ".usdc", ".usdz",
        }
        if mesh.suffix.casefold() not in supported:
            raise ValueError(
                "Baking mesh inputs must use fbx, abc, obj, dae, ply, gltf, glb, or usd"
            )
        if not mesh.is_file():
            raise FileNotFoundError(f"Baking mesh input does not exist: {mesh}")
        return mesh

    @classmethod
    def _validate_resource_import_path(cls, file_path: str) -> Path:
        resource_path = cls._validate_allowed_path(
            file_path, "SP_MCP_RESOURCE_ROOTS", "Resource import"
        )
        if resource_path.suffix.casefold() in BLOCKED_RESOURCE_EXTENSIONS:
            raise ValueError(
                f"Executable or script-like resource files are not allowed: {resource_path.suffix}"
            )
        if not resource_path.is_file():
            raise FileNotFoundError(f"Resource file does not exist: {resource_path}")
        return resource_path

    @staticmethod
    def _validate_color(color: list[float]) -> None:
        if len(color) != 3 or any(not isinstance(value, (int, float)) for value in color):
            raise ValueError("color must contain exactly three numbers")
        if any(value < 0 or value > 1 for value in color):
            raise ValueError("color components must be in the 0..1 range")

    @staticmethod
    def _validate_parameter_values(values: dict[str, Any]) -> None:
        if not isinstance(values, dict) or not values:
            raise ValueError("values must be a non-empty object")
        for name, value in values.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("parameter names must be non-empty strings")
            items = value if isinstance(value, list) else [value]
            if not isinstance(value, (str, int, float, bool, list)):
                raise ValueError(f"Unsupported value type for parameter: {name}")
            if isinstance(value, list) and not value:
                raise ValueError(f"Parameter arrays must not be empty: {name}")
            for item in items:
                if not isinstance(item, (str, int, float, bool)):
                    raise ValueError(f"Parameter arrays must contain scalar values: {name}")
                if isinstance(item, float) and not math.isfinite(item):
                    raise ValueError(f"Parameter values must be finite: {name}")
