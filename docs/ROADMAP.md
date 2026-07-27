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

### Completed in 0.2.0

- Fill, Paint, and Group creation plus UID-based rename, visibility, opacity, blending, selection, and deletion.
- Multiple uniform Fill channels with OpenPBR alias normalization.
- White/Black layer-mask creation, replacement, and removal.
- Recursive layer search with parent paths.
- Project health auditing.
- Export-preset, project-resource, and resource-query inspection.
- Runtime capability detection.
- Approved-root texture export with a read-only plan and output-file verification.

### Layer structure and recipes

- `move_layer(uid, position, reference_uid)`
  - Support `above`, `below`, `inside`, and `top` only when Painter exposes a lossless public API.
  - Verify parent and ordering before and after the operation.
- `create_layer_recipe(recipe)`
  - Create Group, Fill, and Paint nodes as one transaction.
  - Roll back every created node if any step fails.
- `set_active_channels(uid, channels)`.
- Insert Fill, Generator, and Filter effects into mask content.

### Project inspection

- `snapshot_layer_tree`
  - Produce stable JSON snapshots suitable for before/after diffs.

### Resources and presets

- Add server-side type and usage filters to `search_resources`.
- `inspect_export_preset(preset, texture_set)`.
- `find_outdated_resources` plus an explicit replacement plan.

## P2 - Sandboxed file operations

These operations require approved output locations and result verification, but no UI interaction.

### Texture export

- Completed: `plan_texture_export`, `export_textures`, approved-root checks, overwrite protection, and generated-file size verification.
- Add curated export profiles for VRChat, Unity, Unreal Engine, and Blender.

### Project saving and backups

- Prefer `save_project_copy(path)`.
- Allow overwriting the current project through `save_project` only after an explicit request.
- Optionally create a backup before applying a layer recipe.

### Smart Materials and Smart Masks

- Export a selected group as a Smart Material or Smart Mask.
- Verify the generated file and confirm that Painter can rediscover it.

## P3 - Long-running jobs and event bridging

Painter's asynchronous APIs need to be connected to MCP progress and cancellation.

### Baking

- Inspect baker and mesh-map state for selected Texture Sets.
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
