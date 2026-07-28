# Substance Painter MCP

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![MCP SDK 1.x](https://img.shields.io/badge/MCP_SDK-1.x-5A67D8)](https://github.com/modelcontextprotocol/python-sdk)
[![Tested with Painter 12.1.1](https://img.shields.io/badge/Painter-12.1.1-99E83F)](https://www.adobe.com/products/substance3d/apps/painter.html)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An MCP server that lets AI clients inspect, audit, edit, and export from a local Adobe Substance 3D Painter project.

Version **1.0.0** provides 79 focused MCP tools. It completes the guarded resource workflow with shelf discovery, persistent shelf imports, and event-driven shelf refresh jobs, on top of the planned project lifecycle, production baking, and transactional layer authoring added throughout the 0.x releases. It is live-validated against **Substance 3D Painter 12.1.1**.

> This is an independent community project and is not affiliated with or endorsed by Adobe.

## Highlights

- Inspect the open project, Texture Sets, channels, resources, export presets, and complete layer tree.
- Create and edit Fill, Paint, and Group layers through stable layer UIDs.
- Build nested layer recipes atomically and roll back every created node if a step fails.
- Plan recipe scope and channel resolution without mutation, optionally creating an approved `.spp` backup before execution.
- Set OpenPBR-aware Fill channels, masks, visibility, opacity, blend modes, names, and selection.
- Control Mesh or UDIM geometry masks and compare detailed layer snapshots by UID.
- Insert Fill, Paint, Generator, Filter, Levels, Anchor, and Smart Mask effects into mask stacks.
- Apply shelf Smart Materials/Masks and configure UV or Triplanar Fill transforms.
- Assign shelf resources to individual Fill channels or complete materials.
- Import safe visual resources from approved roots into the project, current Painter session, or a writable shelf.
- Discover configured shelves and monitor explicit shelf-index refreshes through persistent event-backed jobs.
- Inspect and edit typed procedural Substance parameters, including colors and enum labels.
- Inspect, connect, reset, and transactionally restore procedural image inputs on Fill, Generator, and Filter sources.
- Discover Anchor Points with owner context and connect them to Fill channels or materials.
- Configure Planar, Spherical, and Cylindrical projection transforms and culling.
- Inspect and transactionally configure common baking properties, individual bakers, UV tiles, and linked Texture Set impact.
- Assign high-poly and cage meshes only from approved roots, then capture or apply portable baking presets.
- Preflight and batch-bake multiple Texture Sets with optional backup, cancellation, state restoration, and per-map verification.
- Preflight and monitor mesh reloads while preserving strokes and reporting Texture Set changes.
- Audit project structure and search layers or resources without mutating the project.
- Preview exact export paths before writing and restrict exports to explicitly allowed directories.
- Save verified project copies without changing the current project's location.
- Plan and create projects from approved meshes with optional templates, mesh maps, Auto UV, USD/glTF settings, verified backup, and failure recovery.
- Open approved projects safely and explicitly save the current project with post-write verification.
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
| `plan_project_creation` | Validate all new-project inputs, typed settings, output, backup, and current-context impact. |
| `get_project_creation_job` | Poll asynchronous project creation, recovery state, and output-file verification. |
| `get_shelf_refresh_job` | Poll the latest explicit shelf refresh and its crawling state. |
| `get_capabilities` | Probe channels, blend modes, and version-dependent runtime features. |
| `audit_project` | Report resolution, channels, layer hygiene, and outdated resources. |
| `inspect_baking` | Inspect enabled bakers, UV tiles, and mesh-map assignments without baking. |
| `inspect_baking_parameters` | Inspect typed common properties or one baker, including ranges and enum labels. |
| `preflight_bake` | Validate project state, mesh inputs, bakers, UV tiles, and expected maps for one or more Texture Sets. |
| `get_bake_job` | Read progress and terminal status for an asynchronous bake. |
| `get_mesh_reload_job` | Read completion status and Texture Set changes for a mesh reload. |
| `list_layers` | Return a recursive UID-based layer tree. |
| `find_layers` | Search by name, type, or visibility and include parent paths. |
| `snapshot_layer_tree` | Capture layers, masks, effects, active channels, and a deterministic digest. |
| `diff_layer_snapshots` | Compare snapshots by UID and report added, removed, or changed nodes. |
| `get_geometry_mask` | Inspect Mesh/UDIM mask state and available geometry elements. |
| `get_fill_parameters` | Inspect procedural values, editor metadata, ranges, enums, and presets. |
| `get_procedural_inputs` | Inspect bitmap, color, or Anchor sources used by procedural image inputs. |
| `list_anchor_points` | Discover Anchor Points with Texture Set, stack, and owner context. |
| `list_export_presets` | List built-in and shelf export presets. |
| `inspect_export_preset` | Resolve a preset and preview its exact map names without writing. |
| `list_export_profiles` | List curated VRChat, Blender, Unity, Unreal, and generic profiles. |
| `list_project_resources` | List resources referenced by the current project. |
| `list_shelves` | List configured shelves, paths, write capability, and current crawling state. |
| `search_resources` | Search resources by query, usage, URL, or type. |
| `find_outdated_resources` | Build a read-only replacement plan for outdated project resources. |

### Layer editing

| Tool | Purpose |
|---|---|
| `create_fill_layer` | Create a Fill layer with an optional base color. |
| `create_paint_layer` | Create a Paint layer. |
| `create_group` | Create a layer group. |
| `plan_layer_recipe` | Validate a recipe, resolve channels, and preview backup/mutation scope. |
| `create_layer_recipe` | Create nested structures atomically, optionally after an `.spp` backup. |
| `set_geometry_mask` | Apply inclusion/exclusion masks using mesh names or UDIM numbers. |
| `insert_smart_material` | Apply a Smart Material at stack top or inside a group. |
| `apply_smart_mask` | Apply a Smart Mask with transactional cleanup on failure. |
| `set_fill_base_color` | Convert an sRGB input color into Painter's working color space. |
| `set_fill_channels` | Set multiple uniform channels, including Roughness, Metallic, and Emission aliases. |
| `get_fill_projection` | Inspect Fill projection mode and common UV transforms. |
| `set_fill_projection` | Set Fill, UV, or Triplanar projection and transforms transactionally. |
| `get_fill_sources` | Inspect material-mode or per-channel Fill sources. |
| `set_fill_resource` | Assign a `resource://` asset to one channel or a complete Fill material. |
| `set_fill_parameters` | Transactionally update typed procedural Substance parameters. |
| `set_procedural_input` | Connect a verified resource to a procedural image input or reset its default. |
| `apply_fill_preset` | Apply a named preset exposed by the current procedural source. |
| `set_fill_anchor_source` | Bind an Anchor Point to one Fill channel or the complete material. |
| `set_fill_projection_advanced` | Configure UV, Triplanar, Planar, Spherical, or Cylindrical projection details. |
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
| `create_project` | Back up the current context, asynchronously create/save a project, and recover on failure. |
| `open_project` | Switch to an approved `.spp`, requiring a backup when the current project is dirty. |
| `save_project` | Explicitly overwrite and verify the current saved project after `confirm=true`. |
| `export_smart_material` | Export a Group as a verified `.spsm` file. |
| `export_smart_mask` | Export a layer mask as a verified `.spmsk` file. |
| `replace_outdated_resources` | Apply Painter's atomic resource replacement after `confirm=true`. |
| `import_project_resource` | Import and verify a safe visual resource inside the open project after `confirm=true`. |
| `import_session_resource` | Import and verify a safe visual resource for the current Painter session after `confirm=true`. |
| `import_shelf_resource` | Persist and verify a safe visual resource in a writable Painter shelf after `confirm=true`. |
| `start_shelf_refresh` | Refresh one configured shelf and bridge Painter crawling events into a persistent job. |
| `start_bake` | Start an asynchronous bake after `confirm=true`, optionally creating a project copy first. |
| `cancel_bake` | Request cooperative cancellation of a running bake job. |
| `configure_baking` | Transactionally configure Texture Set enablement, bakers, UDIMs, curvature, and typed properties after `confirm=true`. |
| `set_baking_mesh_inputs` | Assign or clear sandboxed high-poly/cage files, Low as High, and Cage Mode transactionally. |
| `set_baking_resource_input` | Set or clear a Resource-typed common/per-baker property transactionally. |
| `capture_baking_preset` | Capture portable common, baker, UDIM, curvature, and enablement settings without file-backed values. |
| `apply_baking_preset` | Validate and transactionally apply a captured baking preset after `confirm=true`. |
| `start_batch_bake` | Preflight and asynchronously bake multiple Texture Sets with restoration and a per-map result manifest. |
| `plan_mesh_reload` | Validate an approved mesh path and preview backup/current Texture Set scope. |
| `start_mesh_reload` | Optionally back up, then asynchronously reload a mesh after `confirm=true`. |
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
        "SP_MCP_PROJECT_ROOTS": "D:\\SubstanceBackups",
        "SP_MCP_MESH_ROOTS": "D:\\Meshes",
        "SP_MCP_BAKE_MESH_ROOTS": "D:\\BakeMeshes",
        "SP_MCP_RESOURCE_ROOTS": "D:\\SubstanceResources"
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
| `SP_MCP_MESH_ROOTS` | unset | Approved input roots for FBX, OBJ, DAE, PLY, and USD mesh reloads. |
| `SP_MCP_BAKE_MESH_ROOTS` | unset | Approved roots for high-poly and cage meshes used by baking. |
| `SP_MCP_RESOURCE_ROOTS` | unset | Approved input roots for project/session/shelf resource imports. |

Exports are disabled until `SP_MCP_EXPORT_ROOTS` is configured. `plan_texture_export` performs a read-only preflight. `export_textures` repeats the validation and refuses existing targets unless `overwrite=true` is explicitly supplied.

Project copying is independently disabled until `SP_MCP_PROJECT_ROOTS` is configured. `save_project_copy` uses Painter's `save_as_copy`, verifies the resulting file, and confirms that the current project path did not change.

Mesh reload and project creation are independently disabled until `SP_MCP_MESH_ROOTS` is configured. `plan_mesh_reload` is read-only; `start_mesh_reload` additionally requires `confirm=true` and accepts typed Auto UV or USD settings. Project creation also requires an output under `SP_MCP_PROJECT_ROOTS`; optional templates and mesh maps come from `SP_MCP_RESOURCE_ROOTS`. A backup path under `SP_MCP_PROJECT_ROOTS` is mandatory before replacing an open project.

High-poly and cage assignment is independently disabled until `SP_MCP_BAKE_MESH_ROOTS` is configured. `set_baking_mesh_inputs` accepts only existing mesh files below those roots. `preflight_bake` then validates the effective Painter settings before `start_batch_bake` changes any mesh maps.

Resource import is independently disabled until `SP_MCP_RESOURCE_ROOTS` is configured. Project, session, and shelf imports require `confirm=true`, reject executable/script-like extensions and unsafe script/shader usages, and verify the returned `resource://` identity through Painter before returning it. Shelf imports additionally require a configured writable shelf; refresh jobs report Painter's actual crawling events instead of guessing from request completion.

## Safety model

- User values such as names, colors, and UIDs are serialized as base64-encoded JSON instead of being interpolated into Python source.
- Results are returned directly; the server no longer relies on a shared `C:\temp` result file that could become stale or collide across requests.
- Failed connections stop at the configured timeout instead of hanging for an hour.
- Connection, HTTP, and Painter script failures are reported as distinct error types.
- Layer mutations use UIDs to avoid editing the wrong layer when names are duplicated.
- Project creation separates preflight from execution, requires confirmation and a verified backup before replacing an open context, runs through Painter events, and attempts recovery on failure.
- New-project output, current-project, backup, and open-target paths are checked for collisions before context switching.
- Texture exports require approved roots, a preflight plan, explicit overwrite consent, and post-export file verification.
- Baking and mesh reload require explicit confirmation, expose persistent job state, and never depend on a long-lived HTTP request.
- Mesh inputs are restricted to approved roots and Painter-supported extensions.
- Generic procedural/baker parameter setters reject file and resource widgets; filesystem-backed inputs require dedicated sandboxed tools instead of accepting arbitrary paths.
- Resource imports use an independent approved-root policy, a safe usage allowlist, script/executable rejection, and post-import retrieval verification.
- Shelf writes require explicit confirmation and a writable configured shelf; shelf refresh state is retained in Painter and driven by crawling events.
- Procedural and baking resource setters accept only existing `resource://` identities and restore the original source/property if Painter rejects an update.
- Baking configuration reports every linked Texture Set affected by shared common or per-baker parameters and rolls the touched state back if any update fails.
- Batch baking restores every Texture Set's original bake-enabled state after success, cancellation, launch failure, or Painter failure.
- Baking presets omit file/resource widgets by design, keeping machine-specific paths out of portable configuration payloads.
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

# v0.4 geometry, recipe backup, projection, and Smart asset application
.venv\Scripts\python.exe scripts\live_v04.py `
  --output-root D:\SubstanceMCPTest --project-copy

# v0.5 Fill resources/projections plus optional bake and same-mesh reload jobs
$env:SP_MCP_MESH_ROOTS = "D:\Meshes"
.venv\Scripts\python.exe scripts\live_v05.py `
  --mesh D:\Meshes\sample.fbx --run-bake --run-mesh-reload

# v0.6 procedural parameters, presets, Anchor bindings, and baker config rollback
.venv\Scripts\python.exe scripts\live_v06.py

# v0.7 high-poly assignment, preset round trip, preflight, cancel/restore, and optional successful bake
$env:SP_MCP_BAKE_MESH_ROOTS = "D:\BakeMeshes"
.venv\Scripts\python.exe scripts\live_v07.py `
  --high-poly D:\BakeMeshes\sample_high.fbx --success

# v0.8 project/session imports, OffsetMap, Fill bitmap, and Generator image input round trips
$env:SP_MCP_RESOURCE_ROOTS = "D:\SubstanceResources"
.venv\Scripts\python.exe scripts\live_v08.py `
  --image D:\SubstanceResources\validation.png

# v0.9 backed-up async project creation, original reopen, and typed Auto UV mesh reload
$env:SP_MCP_MESH_ROOTS = "D:\Meshes"
$env:SP_MCP_PROJECT_ROOTS = "D:\SubstanceProjects"
.venv\Scripts\python.exe scripts\live_v09.py `
  --output D:\SubstanceProjects\mcp_created.spp `
  --backup D:\SubstanceProjects\before_creation.spp

# v1.0 persistent shelf import, crawl events, ResourceID verification, and cleanup
$env:SP_MCP_RESOURCE_ROOTS = "D:\SubstanceResources"
.venv\Scripts\python.exe scripts\live_v10.py `
  --source D:\SubstanceResources\validation.png `
  --shelf-path D:\SubstanceResources\mcp-validation-shelf `
  --shelf-name mcp-validation
```

The 1.0.0 validation run used Painter 12.1.1 and a saved three-Texture-Set test project. It verified all 79 FastMCP schemas and 64 automated tests. The lifecycle validation saved the current 955 MB project; created and verified a 21 MB 256px OpenGL project through a `ProjectEditionEntered` job; verified the backup and explicit Full save; reopened the exact original `.spp`; reloaded the same FBX using typed Auto UV settings while preserving strokes; and observed zero added or removed Texture Sets. The shelf validation then created a disposable writable shelf, imported a PNG as a versioned `SHELF` resource, observed real `ShelfCrawlingStarted` and `ShelfCrawlingEnded` events, re-retrieved the exact ResourceID after refresh, removed the shelf, and restored the original project. All generated project, backup, and shelf artifacts were removed after successful restoration.

## Roadmap and release notes

- See [docs/RECIPES.md](docs/RECIPES.md) and the [VRChat outfit starter recipe](examples/recipes/vrchat_outfit.json) for transaction examples.
- See [docs/PROCEDURAL_AND_BAKING.md](docs/PROCEDURAL_AND_BAKING.md) for typed procedural parameters, Anchor bindings, linked baker settings, and configuration examples.
- See [docs/PRODUCTION_BAKING.md](docs/PRODUCTION_BAKING.md) for sandboxed mesh inputs, portable presets, preflight, batch jobs, and result manifests.
- See [docs/RESOURCE_INGESTION.md](docs/RESOURCE_INGESTION.md) for sandboxed imports, safe usages, procedural inputs, and baking Resource properties.
- See [docs/PROJECT_LIFECYCLE.md](docs/PROJECT_LIFECYCLE.md) for project creation, context switching, Auto UV, USD/glTF settings, jobs, and recovery.
- See [CHANGELOG.md](CHANGELOG.md) for detailed release notes.
- See [docs/ROADMAP.md](docs/ROADMAP.md) for completed milestones and remaining Painter automation work.

## License

MIT. See [LICENSE](LICENSE).
