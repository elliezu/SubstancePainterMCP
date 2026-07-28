# Changelog

All notable changes to this project are documented in this file.

## 0.5.0 - 2026-07-28

Version 0.5.0 expands the server from 44 to 53 tools and closes two major automation gaps: resource-driven Fill authoring and observable long-running Painter jobs.

### Fill resources and advanced projections

- Added `get_fill_sources` to inspect material-mode and per-channel Fill sources, including resource URLs, uniform colors, source types, and source UIDs.
- Added `set_fill_resource` for per-channel procedural/bitmap resources and whole-material resources.
- Added local URL and channel-mode validation, automatic channel activation, and rollback of active-channel/source state if a channel assignment fails.
- Expanded `get_fill_projection` with shape crop, projection angle, 3D transforms, and depth/backface culling.
- Added `set_fill_projection_advanced` for UV, Triplanar, Planar, Spherical, and Cylindrical modes.
- Validated filtering, wrapping, crop mode, vector dimensions, positive scales, numeric ranges, and mode-specific transform restrictions before contacting Painter.
- Restored both the prior projection mode and parameters if a projection update fails.

### Asynchronous baking

- Added `start_bake` with explicit `confirm=true`, optional verified project-copy backup, and preflight rejection of disabled Texture Sets or empty UV-tile selections.
- Added `get_bake_job` with persistent job ID, progress, busy state, timestamps, cancellation state, and terminal result.
- Added `cancel_bake` using Painter's cooperative `StopSource` API.
- Bridged `BakingProcessAboutToStart`, `BakingProcessProgress`, and `BakingProcessEnded` without holding an MCP/HTTP request open for the duration of a bake.

### Mesh reload workflow

- Added `plan_mesh_reload` with approved input roots, extension/existence checks, mesh size, current mesh, Texture Set/UV tile inventory, settings, and backup preflight.
- Added `start_mesh_reload` with explicit confirmation, optional verified `.spp` backup, camera/stroke-preservation options, and asynchronous completion tracking.
- Added `get_mesh_reload_job` with prior/new Texture Set lists and added/removed name diffs.
- Added `SP_MCP_MESH_ROOTS` so mesh inputs are independently sandboxed from exports and project backups.

### Validation

- Expanded the automated suite from 33 to 37 tests and verified all 53 FastMCP schemas.
- Live-tested a starter procedural Texture as a Base Color Fill source and verified the resulting `SourceSubstance` URL.
- Live-tested Planar filtering/wrapping, UV/3D transforms, depth/backface culling, plus Spherical, Cylindrical, and Triplanar mode-specific parameters and round-trip inspection.
- Started a bake on an enabled Texture Set, requested cancellation, and observed a terminal `cancelled` event with Painter returning to idle.
- Reloaded the same 5,571,148-byte FBX with `preserve_strokes=true`; Painter reported success and the three Texture Set names were unchanged.
- Removed each temporary Fill layer and verified exact layer-tree digest restoration after authoring tests.

## 0.4.0 - 2026-07-28

Version 0.4.0 expands the server from 36 to 44 tools and adds safe geometry-aware authoring, preflighted recipe execution, Smart asset application, and Fill projection control.

### Geometry masks and snapshots

- Added `get_geometry_mask` with the current mask type, inclusion/exclusion behavior, enabled elements, and valid mesh/UDIM choices.
- Added `set_geometry_mask` using Painter's current `GeometryMaskMeshParams` and `GeometryMaskUVTilesParams` APIs instead of deprecated setters.
- Accepted standard UDIM numbers at the MCP boundary and converted them to Painter UV Tile objects internally.
- Extended layer snapshots with geometry-mask state.
- Added `diff_layer_snapshots` to report added, removed, reordered, and property-changed nodes by UID.

### Planned and backed-up recipes

- Added `plan_layer_recipe` for read-only schema validation, Texture Set resolution, OpenPBR channel resolution, node counts, snapshot digest, and backup preflight.
- Added optional pre-operation `.spp` copies to `create_layer_recipe` through `SP_MCP_PROJECT_ROOTS`.
- Added post-creation snapshot verification and root-node cleanup if verification itself fails.
- Added [recipe documentation](docs/RECIPES.md) and a valid [VRChat outfit starter recipe](examples/recipes/vrchat_outfit.json).

### Smart assets and Fill projection

- Added `insert_smart_material` at Texture Set top level or inside an existing group.
- Added `apply_smart_mask` as a discoverable, transaction-protected Smart Mask operation.
- Added `get_fill_projection` for projection mode, filtering, wrapping, hardness, and UV transform inspection.
- Added `set_fill_projection` for Fill, UV, and Triplanar modes with scale, rotation, and offset validation.
- Restored the previous projection settings if any projection update step fails.

### Validation

- Expanded the automated suite from 27 to 33 tests and verified all 44 FastMCP schemas.
- Live-tested Mesh geometry masking with `pants_low` and UDIM masking with tile `1001`.
- Live-tested UV scale/rotation/offset and Triplanar scale/rotation changes.
- Applied the starter `Aluminium Anodized Red` Smart Material and verified its two generated child layers.
- Applied the starter `Cavity Rust` Smart Mask and verified its generated Mask Editor effect.
- Created and verified a 951,014,813-byte pre-recipe project copy while preserving the original project path.
- Used snapshot diffs to detect five inserted nodes, then verified exact final snapshot restoration after cleanup.
- Deleted the temporary project backup and all generated validation layers after the run.

## 0.3.0 - 2026-07-28

Version 0.3.0 expands the server from 22 to 36 MCP tools and completes most deterministic P1/P2 automation that can be safely verified without subjective visual review.

### Transactional layer automation

- Added `create_layer_recipe` for nested Group, Fill, and Paint structures.
- Added preflight schema, color, nesting-depth, and node-type validation.
- Added in-Painter transaction rollback: every node created by a failed recipe is removed before the error is returned.
- Preserved declared layer order when inserting at the top of a Texture Set or group.
- Added optional visibility, active-channel, Fill-channel, base-color, and mask configuration to recipe nodes.
- Added `set_active_channels` with OpenPBR aliases for Roughness, Metallic, and Emission.

### Masks, effects, and snapshots

- Added `insert_mask_effect` for Fill, Paint, Generator, Filter, Levels, Anchor, and Smart Mask content.
- Added resource-URL validation before resource-backed effects are inserted.
- Added `snapshot_layer_tree`, including masks, mask effects, content effects, active channels, group state, and a deterministic SHA-256 digest.
- Used snapshot equality to verify both failed-recipe rollback and final live-test cleanup.

### Resources and baking inspection

- Added server-side `resource_type` and `usage` filters to `search_resources`.
- Isolated malformed legacy shelf usage metadata so one incompatible resource no longer aborts a complete search.
- Added `find_outdated_resources` and explicit `confirm=true` gating for Painter's atomic `replace_project_resources` operation.
- Added read-only `inspect_baking` output for Texture Set enablement, bakers, UV tiles, mesh-map resources, and curvature mode.

### Export workflows and backups

- Added read-only `inspect_export_preset` with per-Texture-Set map-name previews.
- Added curated `generic-pbr`, `vrchat-pbr`, `blender`, `unity-hdrp`, `unity-urp`, and `unreal-engine` profiles.
- Added `plan_profile_export` and `export_with_profile` on top of the existing approved-root and overwrite gates.
- Added verified Smart Material (`.spsm`) and Smart Mask (`.spmsk`) file exports.
- Added `save_project_copy` using Painter's non-relocating `save_as_copy` API.
- Added independent `SP_MCP_PROJECT_ROOTS`, `.spp` extension validation, overwrite protection, output size verification, and current-project path verification.

### Validation

- Expanded the automated suite from 16 to 27 tests, including FastMCP schema registration for all 36 tools.
- Added `scripts/live_features.py` for repeatable transactional and file-output testing.
- Live-validated nested recipe creation and cleanup, multi-node failure rollback, OpenPBR active channels, Levels/Anchor/Generator mask effects, filtered resource search, and baking inspection.
- Exported and verified a 36,271-byte Smart Material and a 33,865-byte Smart Mask.
- Exported and verified 18 texture files across three UDIM Texture Sets using the generic PBR profile.
- Saved and verified a 951,014,813-byte project copy while confirming that Painter kept the original project path.
- Removed all temporary Painter layers and generated validation artifacts after the run.

### Intentionally deferred

- Existing-layer movement remains deferred because Painter exposes insertion positions but no confirmed lossless move primitive.
- Bake execution, progress, and cancellation remain deferred until an event bridge can reliably map Painter's asynchronous lifecycle onto MCP progress without orphaning jobs.
- Project creation and mesh reload remain deferred until automatic pre-operation backups and post-operation Texture Set diffs are implemented together.

## 0.2.0 - 2026-07-28

Version 0.2.0 modernizes the original MCP proof of concept into an installable, tested, and safety-gated server for current Substance 3D Painter workflows.

### Compatibility and packaging

- Live-validated the server with Adobe Substance 3D Painter 12.1.1.
- Migrated the MCP layer to FastMCP on the stable MCP Python SDK 1.x line (`mcp>=1.28,<2`).
- Reorganized the project as a standard `src`-layout Python package.
- Added `python -m substance_painter_mcp` and the `substance-painter-mcp` console entry point.
- Added compatibility wrappers for users of the original `src/server.py` and `src/painter_remote.py` modules.
- Added Python 3.10+ project metadata, development dependencies, an MIT license, and package build configuration.

### Reliability and security

- Replaced the previous 3,600-second request hang with an environment-configurable timeout that defaults to 30 seconds.
- Added distinct connection, HTTP, and remote-script exception types for actionable client errors.
- Removed the fixed `C:\temp` result file, preventing stale-result reads and cross-request collisions.
- Encoded operation parameters as base64 JSON before embedding them in Painter scripts, preventing values such as layer names from altering generated Python source.
- Made arbitrary Painter Python execution opt-in through `SP_MCP_ALLOW_EXECUTE_PYTHON=1`.
- Added UID-based mutation so duplicate layer names cannot silently target the wrong node.

### Project inspection

- Added connection and project status, project metadata, and recursive layer-tree tools.
- Added runtime capability detection for Painter versions, OpenPBR channels, masks, geometry masks, and available blend modes.
- Added recursive layer search with type, visibility, and parent-path context.
- Added project auditing for Texture Set resolution, channels, duplicate names, layer hygiene, and outdated resources.
- Added project-resource listing and resource search.
- Added built-in and shelf export-preset discovery.

### Layer editing

- Added Fill, Paint, and Group creation.
- Added layer rename, visibility, per-channel opacity, blend mode, multi-selection, and deletion.
- Added sRGB-to-Painter-working-space conversion for Fill base colors.
- Added multi-channel uniform Fill updates with aliases for Roughness, Metallic, Emission, and their OpenPBR canonical channel names.
- Added White/Black layer-mask creation, replacement, and removal.

### Guarded texture export

- Added `plan_texture_export` to resolve expected outputs and detect conflicts without writing files.
- Added `export_textures` with explicitly approved export roots through `SP_MCP_EXPORT_ROOTS`.
- Refused existing output files unless `overwrite=true` is explicitly requested.
- Added post-export checks for every generated file and its byte size.

### Tests and validation

- Added 16 automated tests covering transport encoding, timeout and error paths, input isolation, color conversion, opacity validation, and operation behavior.
- Added a read-only live smoke test and a reversible write smoke test that always attempts to remove temporary nodes.
- Verified all 22 MCP tool registrations and a status call through the installed console entry point.
- Exercised live Group/Fill/Paint creation, channel changes, masks, selection, audit, resource search, preset discovery, and cleanup in a Painter sample scene.
- Completed a guarded 256 px PNG export using the PBR Metallic Roughness preset and verified the generated Base Color, Roughness, Metallic, Normal, and Height files.

### Known limits

- Existing layer reordering is not exposed because Painter's public API provides insertion positions but no safe operation for moving an existing node. A clone-and-delete workaround could lose data and is intentionally not used.
- Long-running baking, progress reporting, cancellation, project backups, and engine-specific export profiles remain roadmap items.
- Visual quality decisions for generators, filters, smart masks, bake artifacts, and Blender round trips still require human review.
