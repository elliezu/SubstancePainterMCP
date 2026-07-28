# Substance Painter MCP Roadmap

Painter 12.1.1 is the current validation baseline. Features should be enabled from `get_capabilities` results rather than from a version string alone.

## Design principles

1. Keep read-only inspection separate from project mutations.
2. Identify layers by UID, never by a potentially duplicated name.
3. Split file-producing operations into preview/validation and execution phases.
4. Expose Painter busy state, progress, and cancellation for long-running work.
5. Create test artifacts only in dedicated locations, then verify and clean them.
6. Prefer focused domain tools so normal workflows do not require arbitrary Python execution.

## P1 - Deterministic project automation

These features can be created, verified, and cleaned up in a sample project without subjective visual review.

### Completed in 0.2.0-0.4.0

- Fill, Paint, and Group creation plus UID-based rename, visibility, opacity, blending, selection, and deletion.
- Multiple uniform Fill channels with OpenPBR alias normalization.
- White/Black layer-mask creation, replacement, and removal.
- Recursive layer search with parent paths.
- Project health auditing.
- Export-preset, project-resource, and resource-query inspection.
- Runtime capability detection.
- Approved-root texture export with a read-only plan and output-file verification.
- Transactional nested layer recipes with automatic rollback.
- Active-channel replacement with OpenPBR aliases.
- Fill, Paint, Generator, Filter, Levels, Anchor, and Smart Mask insertion in masks.
- Detailed layer/effect snapshots with deterministic SHA-256 digests.
- Server-side resource type/usage filtering with malformed legacy metadata isolation.
- Export-preset inspection and outdated-resource replacement planning.
- Current Geometry Mask inspection and Mesh/UDIM inclusion/exclusion editing.
- Mutation-free recipe planning, optional pre-operation backup, and snapshot diffs.
- Smart Material and Smart Mask application from validated resource URLs.
- UV and Triplanar Fill projection transforms with failure rollback.

### Layer structure and recipes

- `move_layer(uid, position, reference_uid)`
  - Support `above`, `below`, `inside`, and `top` only when Painter exposes a lossless public API.
  - Verify parent and ordering before and after the operation.
- `create_layer_recipe(recipe)`
  - Completed through 0.4.0 with planning, nested nodes, rollback, snapshot verification, and optional backup.
- `set_active_channels(uid, channels)` completed in 0.3.0.
- Mask-content effects completed in 0.3.0.

### Project inspection

- `snapshot_layer_tree`
  - Completed through 0.4.0 with geometry state, stable JSON, SHA-256, and UID-based diffs.

### Resources and presets

- Completed: server-side type and usage filters for `search_resources`.
- Completed: `inspect_export_preset(preset, texture_set)`.
- Completed: `find_outdated_resources` and confirmed atomic replacement.

## P2 - Sandboxed file operations

These operations require approved output locations and result verification, but no UI interaction.

### Texture export

- Completed: `plan_texture_export`, `export_textures`, approved-root checks, overwrite protection, and generated-file size verification.
- Completed in 0.3.0: curated VRChat, Unity, Unreal Engine, Blender, and generic PBR profiles.

### Project saving and backups

- Completed: `save_project_copy(path)` with an independent approved-root sandbox.
- Allow overwriting the current project through `save_project` only after an explicit request.
- Completed in 0.4.0: optional backup before applying a layer recipe.

### Smart Materials and Smart Masks

- Completed: export a selected group or mask as verified `.spsm` / `.spmsk` files.
- Completed in 0.4.0: apply shelf Smart Materials and Smart Masks transactionally.
- Next: confirm that Painter can rediscover a generated file in a configured shelf.

### Fill sources and projections

- Completed in 0.4.0: inspect projections and set Fill, UV, or Triplanar transforms.
- Next: connect bitmap/material resources as Fill sources with usage validation.
- Next: expose advanced Planar, Spherical, and Cylindrical projection parameters.

## P3 - Long-running jobs and event bridging

Painter's asynchronous APIs need to be connected to MCP progress and cancellation.

### Baking

- Completed read-only inspection of baker enablement, UV tiles, mesh-map assignments, and curvature mode.
- Validate bake settings before starting.
- Stream progress from `bake_selected_textures_async`.
- Investigate Painter 12.1 Auto Rebake and Skew Map capabilities.
- Return structured failures by baker with relevant logs.

### Project creation and mesh reload

- Support Painter 12.0.2+ `AutoUnwrapUVTilesSettings`.
- Define schemas for USD, glTF, and FBX import options.
- Diff Texture Sets and layer impact after a mesh reload.
- Create an automatic backup before destructive topology changes.

## P4 - Visual QA and human approval

These tasks may require user input because correctness depends on appearance rather than structured state.

- Choose among Generator, Filter, and Smart Mask results.
- Evaluate bake artifacts and edge quality.
- Approve color and roughness direction.
- Compare camera framing and viewport renders.
- Validate mesh and material matching in a Blender-to-Painter round trip.

Where possible, automation should produce viewport captures and A/B candidates first so one approval can resolve the decision.

## Proposed automation packages

### VRChat Outfit Texture Recipe

1. Inspect Texture Sets and channels.
2. Create Base, Color Variation, Roughness, and Detail groups.
3. Apply a color palette.
4. Connect AO- and Curvature-driven masks.
5. Export through a Unity profile.
6. Validate generated files and naming rules.

### Project Health Check

1. Snapshot the project, Texture Sets, layers, and resources.
2. Detect outdated or missing resources.
3. Report duplicate and non-standard layer names.
4. Check export-preset compatibility.
5. Return a remediation plan or apply only explicitly approved changes.

### Blender Round Trip

1. Generate a mesh/material manifest in Blender.
2. Create a Painter project or reload its mesh.
3. Validate Texture Set matching.
4. Bake and export.
5. Connect Blender nodes and verify file hashes.

This workflow first requires a shared manifest schema between the Painter MCP and Blender-side tooling.

## Safety constraint: existing-layer movement

Painter's public Python API currently exposes insertion positions for newly created content but no confirmed lossless method for moving an existing layer node. Reconstructing a layer through clone-and-delete could discard paints, effects, masks, or resource bindings. `move_layer` must remain unimplemented until the runtime exposes a safe primitive or a fully verified transactional strategy is available.
