# Substance Painter MCP

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![MCP SDK 1.x](https://img.shields.io/badge/MCP_SDK-1.x-5A67D8)](https://github.com/modelcontextprotocol/python-sdk)
[![Tested with Painter 12.1.1](https://img.shields.io/badge/Painter-12.1.1-99E83F)](https://www.adobe.com/products/substance3d/apps/painter.html)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An MCP server that lets AI clients inspect, audit, edit, and export from a local Adobe Substance 3D Painter project.

Version **0.3.0** provides 36 focused MCP tools, transactional layer recipes, detailed layer snapshots, mask effects, baking inspection, filtered resource search, curated engine exports, verified Smart Material/Mask output, and sandboxed project backups. It remains live-validated against **Substance 3D Painter 12.1.1**.

> This is an independent community project and is not affiliated with or endorsed by Adobe.

## Highlights

- Inspect the open project, Texture Sets, channels, resources, export presets, and complete layer tree.
- Create and edit Fill, Paint, and Group layers through stable layer UIDs.
- Build nested layer recipes atomically and roll back every created node if a step fails.
- Set OpenPBR-aware Fill channels, masks, visibility, opacity, blend modes, names, and selection.
- Insert Fill, Paint, Generator, Filter, Levels, Anchor, and Smart Mask effects into mask stacks.
- Audit project structure and search layers or resources without mutating the project.
- Preview exact export paths before writing and restrict exports to explicitly allowed directories.
- Save verified project copies without changing the current project's location.
- Detect runtime capabilities instead of trusting Painter's reported Python API version alone.
- Keep arbitrary Python execution disabled unless the user explicitly opts in.

## Compatibility

| Component | Supported / validated |
|---|---|
| Adobe Substance 3D Painter | Live-tested with 12.1.1 |
| Painter Python API | Runtime reported 0.3.5 in the validated build |
| Python | 3.10 or newer |
| MCP Python SDK | `mcp>=1.28,<2` |
| Transport | MCP stdio to Painter HTTP remote scripting |
| Painter endpoint | `localhost:60041` by default |

Painter builds may expose newer features while reporting an older API version string. `get_capabilities` therefore probes the running application for supported channels, blend modes, OpenPBR behavior, and version-specific features.

## Available tools

### Inspection and diagnostics

| Tool | Purpose |
|---|---|
| `painter_status` | Check the connection, Painter/API versions, and whether a project is open. |
| `get_project_info` | Return the project path and Texture Sets. |
| `get_capabilities` | Probe channels, blend modes, and version-dependent runtime features. |
| `audit_project` | Report resolution, channels, layer hygiene, and outdated resources. |
| `inspect_baking` | Inspect enabled bakers, UV tiles, and mesh-map assignments without baking. |
| `list_layers` | Return a recursive UID-based layer tree. |
| `find_layers` | Search by name, type, or visibility and include parent paths. |
| `snapshot_layer_tree` | Capture layers, masks, effects, active channels, and a deterministic digest. |
| `list_export_presets` | List built-in and shelf export presets. |
| `inspect_export_preset` | Resolve a preset and preview its exact map names without writing. |
| `list_export_profiles` | List curated VRChat, Blender, Unity, Unreal, and generic profiles. |
| `list_project_resources` | List resources referenced by the current project. |
| `search_resources` | Search resources by query, usage, URL, or type. |
| `find_outdated_resources` | Build a read-only replacement plan for outdated project resources. |

### Layer editing

| Tool | Purpose |
|---|---|
| `create_fill_layer` | Create a Fill layer with an optional base color. |
| `create_paint_layer` | Create a Paint layer. |
| `create_group` | Create a layer group. |
| `create_layer_recipe` | Create nested Group/Fill/Paint structures atomically with rollback. |
| `set_fill_base_color` | Convert an sRGB input color into Painter's working color space. |
| `set_fill_channels` | Set multiple uniform channels, including Roughness, Metallic, and Emission aliases. |
| `set_active_channels` | Replace a Fill or Paint layer's active channel set. |
| `set_layer_mask` | Add, replace, or remove a White/Black mask. |
| `insert_mask_effect` | Insert procedural or paint effects into a layer's mask stack. |
| `set_layer_properties` | Set visibility and channel-specific opacity or blend mode. |
| `rename_layer` | Rename a layer by UID. |
| `select_layers` | Select one or more layers by UID. |
| `delete_layer` | Delete a layer by UID. |

Layer names are not unique in Painter. All mutation tools therefore use the UIDs returned by `list_layers` or `find_layers`.

### Export and advanced access

| Tool | Purpose |
|---|---|
| `plan_texture_export` | Resolve expected output files and conflicts without writing anything. |
| `export_textures` | Export within approved roots and verify every generated file and size. |
| `plan_profile_export` | Preview a curated engine-profile export. |
| `export_with_profile` | Export with a curated profile and verify generated files. |
| `save_project_copy` | Write a verified `.spp` backup without relocating the current project. |
| `export_smart_material` | Export a Group as a verified `.spsm` file. |
| `export_smart_mask` | Export a layer mask as a verified `.spmsk` file. |
| `replace_outdated_resources` | Apply Painter's atomic resource replacement after `confirm=true`. |
| `execute_python` | Run arbitrary Painter Python only when explicitly enabled. |

## Installation

```powershell
git clone https://github.com/elliezu/SubstancePainterMCP.git
cd SubstancePainterMCP
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
```

For development and tests:

```powershell
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m pytest
```

## Start Painter with remote scripting

Painter must be started as a new process with remote scripting enabled:

```powershell
"C:\Program Files\Adobe\Adobe Substance 3D Painter\Adobe Substance 3D Painter.exe" --enable-remote-scripting
```

You can add the same argument to a Windows shortcut's **Target** field:

```text
"C:\Program Files\Adobe\Adobe Substance 3D Painter\Adobe Substance 3D Painter.exe" --enable-remote-scripting
```

If Painter is already running without this argument, launching the shortcut may only focus the existing process. Exit Painter completely, then start it again from the modified shortcut. No manual port configuration is needed: Painter opens `localhost:60041` automatically.

Verify the listener in PowerShell:

```powershell
Get-NetTCPConnection -LocalPort 60041
```

## Configure an MCP client

Example for Claude Desktop on Windows:

```json
{
  "mcpServers": {
    "substance-painter": {
      "command": "C:\\Tools\\SubstancePainterMCP\\.venv\\Scripts\\python.exe",
      "args": ["-m", "substance_painter_mcp"],
      "env": {
        "SP_MCP_TIMEOUT": "120",
        "SP_MCP_EXPORT_ROOTS": "D:\\SubstanceExports",
        "SP_MCP_PROJECT_ROOTS": "D:\\SubstanceBackups"
      }
    }
  }
}
```

Replace the paths with your installation and export directories. You may also use `.venv\Scripts\substance-painter-mcp.exe` directly as the command.

## Environment variables

| Variable | Default | Description |
|---|---:|---|
| `SP_MCP_HOST` | `localhost` | Painter remote-scripting host. |
| `SP_MCP_PORT` | `60041` | Painter remote-scripting port. |
| `SP_MCP_TIMEOUT` | `30` | HTTP timeout in seconds. |
| `SP_MCP_ALLOW_EXECUTE_PYTHON` | unset | Set to `1` to expose arbitrary Python execution. |
| `SP_MCP_EXPORT_ROOTS` | unset | Approved export roots. Separate multiple Windows paths with `;`. |
| `SP_MCP_PROJECT_ROOTS` | unset | Approved roots for `.spp` project copies. |

Exports are disabled until `SP_MCP_EXPORT_ROOTS` is configured. `plan_texture_export` performs a read-only preflight. `export_textures` repeats the validation and refuses existing targets unless `overwrite=true` is explicitly supplied.

Project copying is independently disabled until `SP_MCP_PROJECT_ROOTS` is configured. `save_project_copy` uses Painter's `save_as_copy`, verifies the resulting file, and confirms that the current project path did not change.

## Safety model

- User values such as names, colors, and UIDs are serialized as base64-encoded JSON instead of being interpolated into Python source.
- Results are returned directly; the server no longer relies on a shared `C:\temp` result file that could become stale or collide across requests.
- Failed connections stop at the configured timeout instead of hanging for an hour.
- Connection, HTTP, and Painter script failures are reported as distinct error types.
- Layer mutations use UIDs to avoid editing the wrong layer when names are duplicated.
- Texture exports require approved roots, a preflight plan, explicit overwrite consent, and post-export file verification.
- Arbitrary Python is opt-in and disabled by default.

The server is designed for local use. Do not expose Painter's remote-scripting port to untrusted networks.

## Testing and live validation

Run the automated suite:

```powershell
.venv\Scripts\python.exe -m pytest
```

The current suite covers request encoding, typed errors, timeout behavior, input isolation, color conversion, opacity validation, and operation-level behavior.

With Painter running and a disposable project open, use the live smoke test:

```powershell
# Read-only inspection
.venv\Scripts\python.exe scripts\live_smoke.py

# Reversible create -> edit -> verify -> delete round trip
.venv\Scripts\python.exe scripts\live_smoke.py --write

# Full v0.3 transaction, mask-effect, Smart asset, export, and backup validation
.venv\Scripts\python.exe scripts\live_features.py `
  --output-root D:\SubstanceMCPTest --texture-export --project-copy
```

The 0.3.0 validation run used Painter 12.1.1 and a saved test project with three UDIM Texture Sets. It verified all 36 FastMCP tool schemas, multi-node recipe rollback by comparing pre/post SHA-256 snapshots, nested layer creation, OpenPBR channel aliases, mask Levels/Anchor/Generator insertion, filtered generator search, preset map inspection, `.spsm` and `.spmsk` export, 18 guarded 256 px PNG texture outputs, and a verified 951 MB `.spp` copy. The original project path remained unchanged, all temporary layers were removed, and test artifacts were deleted after verification.

## Roadmap and release notes

- See [CHANGELOG.md](CHANGELOG.md) for detailed 0.3.0 and 0.2.0 release notes.
- See [docs/ROADMAP.md](docs/ROADMAP.md) for planned layer recipes, snapshots, backups, engine-specific export profiles, async baking, and Blender round-trip workflows.

## License

MIT. See [LICENSE](LICENSE).
