# Changelog

All notable changes to this project are documented in this file.

## 0.9.0 - 2026-07-28

Version 0.9.0 expands the server from 70 to 75 tools and completes a guarded Painter project lifecycle with typed mesh-import settings.

### Planned and asynchronous project creation

- Added `plan_project_creation` for approved mesh, mesh-map, template, output, backup, overwrite, and context-replacement validation without mutation.
- Added typed project settings for normal-map format, tangent-space mode, UV workflow, default resolution, cameras, mesh scale, Auto UV, USD, and glTF.
- Added `create_project` with explicit confirmation and mandatory verified backup before replacing an open project.
- Bridged Painter's asynchronous project loading through `ProjectEditionEntered` instead of assuming that `project.create()` returning means the project is no longer busy.
- Added persistent creation state with job ID, timestamps, terminal status, output, Texture Sets, recovery path, and error.
- Added `get_project_creation_job` with local `.spp` existence and byte-size verification after Painter saves the new project.
- Closed partial projects and attempted to reopen the verified backup if creation or save failed.

### Safe project switching and saving

- Added `open_project` for `.spp` files below `SP_MCP_PROJECT_ROOTS`.
- Required a verified backup when the current project has unsaved changes and restored the original or backup if opening the target failed.
- Added `save_project` with explicit confirmation, Full/Incremental modes, dirty-state verification, file existence, and byte-size checks.
- Rejected output/current/backup/open-target path collisions before any project context was closed.

### Typed Auto UV and mesh-specific settings

- Added strict schemas for every public `AutoUnwrapSettings` field, including count- or texel-density-based UV tile packing.
- Validated margin range, island orientation, UV tile count, texel density, and power-of-two reference resolution locally.
- Added USD scope, variants, subdivision, and frame settings; added glTF normal-map inversion for project creation.
- Extended existing mesh-reload planning and jobs with Auto UV and USD settings while retaining preserve-strokes, camera, backup, and Texture Set diff behavior.
- Reported public lifecycle/import support through runtime capability probes.

### Validation

- Expanded the automated suite from 55 to 61 tests and verified all 75 FastMCP schemas.
- Identified and fixed the real Painter lifecycle boundary where `project.create()` returns while Painter still reports busy.
- Created a 256px OpenGL project asynchronously from the live sample FBX and verified the 21 MB output.
- Verified a 955 MB current-project backup, explicit Full save, exact original-project reopen, and automatic failure-safe restoration.
- Reloaded the original FBX with typed Auto UV settings, preserved strokes, observed zero Texture Set name changes, and verified the final save.
- Removed the generated project, backup, and dedicated test directory after successful restoration.

## 0.8.0 - 2026-07-28

Version 0.8.0 expands the server from 65 to 70 tools and closes the filesystem-to-Painter resource pipeline without weakening the server's approved-root model.

### Sandboxed resource ingestion

- Added `import_project_resource` and `import_session_resource` with the independent `SP_MCP_RESOURCE_ROOTS` allowlist.
- Required explicit `confirm=true`, an existing regular file, and one of 14 safe visual/content usages.
- Excluded shader, particle script, receiver/emitter, and other executable-oriented usages; also rejected common executable and script-like file extensions before contacting Painter.
- Supported optional Painter resource names and groups while transporting every value through the existing JSON parameter channel.
- Returned context, versioned `resource://` URL, location, Painter type, category, usages, and source path.
- Re-retrieved the exact returned ResourceID and failed the operation if post-import verification could not find it.

### Procedural image inputs

- Added `get_procedural_inputs` for Fill layers, Fill effects, Generator effects, and Filter effects.
- Described each graph image input as a bitmap ResourceID, uniform color with color space, or Anchor Point UID.
- Added `set_procedural_input` for verified `resource://` connections and reset-to-default behavior.
- Snapshotted bitmap, color, or Anchor sources and restored the original input if Painter rejected a new assignment.
- Kept scalar/vector procedural parameters in `set_fill_parameters`; filesystem-backed graphs now use the dedicated import and image-input tools.

### Baking Resource properties and Painter 12.1 capability reporting

- Added `set_baking_resource_input` for common or per-baker properties whose runtime widget type is `Resource`.
- Verified the ResourceID before mutation, required explicit confirmation, reported linked Texture Set impact, and rolled back on failure.
- Live-tested Painter 12.1's common `OffsetMap` skew-correction resource input.
- Added explicit runtime capabilities for resource import, procedural image inputs, baking Resource inputs, auto-rebake control, and skew-painting control.
- Confirmed that Painter 12.1.1 exposes skew-related bake properties but no public Python control for Auto Rebake or entering Skew Painting mode; those UI-only controls therefore report `false` instead of relying on fragile UI automation.

### Validation

- Expanded the automated suite from 49 to 55 tests and verified all 70 FastMCP schemas.
- Imported one PNG into both project and session contexts and re-retrieved both exact versioned identities.
- Connected the project image to linked baking `OffsetMap`, a temporary Fill's Base Color, and a Mask Editor Generator's `texture` image input.
- Verified the Generator transition from a raw uniform color to a project bitmap and back to the same default uniform color.
- Cleared the Offset Map, deleted temporary layer content, and confirmed exact layer-tree SHA-256 restoration.

## 0.7.0 - 2026-07-28

Version 0.7.0 expands the server from 60 to 65 tools and turns the existing asynchronous bake primitive into a production-oriented, multi-Texture-Set baking workflow.

### Sandboxed baking mesh inputs

- Added `set_baking_mesh_inputs` for one or more high-poly meshes, an optional cage mesh, Low as High, and Cage Mode.
- Added the independent `SP_MCP_BAKE_MESH_ROOTS` allowlist and required every supplied mesh to exist below an approved root with a supported mesh extension.
- Encoded paths as local file URLs and joined multiple high-poly inputs in Painter's native `HipolyMesh` format.
- Automatically selected Custom file cage mode when a cage was supplied without an explicit mode.
- Applied shared baking properties transactionally and restored every touched property if Painter rejected any update.
- Reported all Texture Sets affected by Painter's linked common-parameter groups.

### Portable baking presets

- Added `capture_baking_preset` with the versioned `substance-painter-mcp/baking-preset@1` schema.
- Captured Texture Set enablement, enabled bakers, selected UDIMs, curvature mode, common values, and selected per-baker values.
- Excluded File, FileList, and Resource widgets so presets remain portable and cannot smuggle machine-specific paths around the sandbox.
- Added `apply_baking_preset`, which validates the schema and routes through the existing confirmed, transactional baker configuration path.

### Preflight and batch execution

- Added `preflight_bake` for one or more Texture Sets, defaulting to the currently bake-enabled sets.
- Reported resolution, antialiasing, enabled bakers, enabled UV tiles, high-poly/cage inputs, current mesh-map resources, expected maps, and structured warnings/errors.
- Detected missing mesh inputs, disabled Low as High, invalid cage combinations, missing files, empty baker/tile selections, duplicate/unknown Texture Sets, closed projects, and active Painter jobs before mutation.
- Added `start_batch_bake` with explicit confirmation, optional verified `.spp` backup, Painter event progress, cooperative cancellation, and persistent job state.
- Temporarily selected exactly the requested Texture Sets for Painter's batch API and restored every original bake-enabled state after success, cancellation, failure, or launch exceptions.
- Captured mesh-map URLs before and after the job and returned a per-Texture-Set, per-baker manifest with presence, change, verification, and status fields.
- Documented Painter's public event limitation: a failed bake exposes only a global failure result, not per-baker log text.

### Validation

- Expanded the automated suite from 43 to 49 tests and verified all 65 FastMCP schemas.
- Live-assigned an existing FBX high-poly mesh through the approved-root sandbox in Painter 12.1.1.
- Captured and reapplied an AO/ID preset and obtained a ready preflight for a three-Texture-Set project.
- Cancelled a seven-map batch and verified exact restoration of all original Texture Set enablement.
- Completed a temporary 256x256 AO batch, observed the mesh-map resource change, verified the result manifest, and restored the original 4096 resolution, 8x8 antialiasing, seven enabled bakers, and AO ray count.

## 0.6.0 - 2026-07-28

Version 0.6.0 expands the server from 53 to 60 tools and adds typed procedural authoring, Anchor Point source graphs, and transactional baker configuration.

### Procedural Substance authoring

- Added `get_fill_parameters` for procedural values, labels, widget types, ranges, enum labels, metadata, and available presets.
- Added `set_fill_parameters` with JSON-safe scalar/vector inputs, sRGB color conversion, enum-label resolution, numeric range validation, finite-number checks, and rollback of every touched parameter if Painter rejects an update.
- Added `apply_fill_preset` with source capability checks, exact preset-name validation, and parameter rollback on failure.
- Supported material-mode and per-channel procedural sources with OpenPBR channel aliases.
- Rejected generic `File`, `FileList`, and `Resource` widget edits so filesystem paths cannot bypass approved-root controls.

### Anchor Point bindings

- Added `list_anchor_points` across one or all Texture Sets with stack, owner layer, and mask/content context.
- Added `set_fill_anchor_source` for channel or complete-material bindings using stable Fill and Anchor UIDs.
- Verified Texture Set compatibility before creating Painter `SourceReference` objects.
- Preserved the original active-channel set and source when a channel binding fails.

### Typed baker configuration

- Added `inspect_baking_parameters` for common settings or one baker, including current values, labels, widgets, ranges, enum labels, available bakers, standard UDIM numbers, and linked Texture Sets.
- Added `configure_baking` for Texture Set enablement, enabled bakers, selected UDIMs, curvature method, common properties, and per-baker properties.
- Accepted human-readable combobox labels and converted them through Painter's own enum metadata.
- Added explicit `confirm=true`, local schema checks, Painter property-range validation, unknown property/baker/UDIM rejection, and full touched-state rollback.
- Reported the union of Texture Sets affected by linked common and per-baker properties.

### Validation

- Expanded the automated suite from 37 to 43 tests and verified all 60 FastMCP schemas.
- Live-tested 30 exposed parameters and three named presets on the starter Carbon Fiber material.
- Round-tripped Carbon Roughness and an sRGB Carbon Color, then applied `Large Shiny Carbon Fiber`.
- Created a mask Anchor Point, discovered its owner context, and connected it to another Fill's Base Color as a `SourceReference`.
- Deleted both temporary Fill layers and verified exact layer-tree digest restoration.
- Changed common Dilation Width from 32 to 33 and AO Secondary Rays from 64 to 65, detected their three-Texture-Set linked impact, and restored both original values.

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
