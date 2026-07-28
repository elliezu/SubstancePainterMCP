# Production Baking

Version 0.7 adds a guarded workflow around Painter's asynchronous baking API: assign approved mesh inputs, capture or apply a portable configuration, run a read-only preflight, start a batch, and inspect a persistent result manifest.

## 1. Approve baking mesh roots

Set `SP_MCP_BAKE_MESH_ROOTS` in the MCP server environment. Multiple Windows roots are separated with semicolons.

```json
{
  "env": {
    "SP_MCP_BAKE_MESH_ROOTS": "D:\\Assets\\Bake;E:\\Shared\\Meshes",
    "SP_MCP_PROJECT_ROOTS": "D:\\SubstanceBackups"
  }
}
```

This allowlist is separate from `SP_MCP_MESH_ROOTS`, which protects project mesh reload. Baking inputs must exist below an approved root and use FBX, Alembic, OBJ, DAE, PLY, glTF, GLB, or USD-family extensions.

## 2. Assign high-poly and cage inputs

`set_baking_mesh_inputs` requires `confirm=true` because Painter stores these settings in the project. An empty list clears high-poly inputs; an empty cage string clears the cage.

```json
{
  "texture_set": "Body",
  "high_poly_files": [
    "D:\\Assets\\Bake\\character_high.fbx",
    "D:\\Assets\\Bake\\accessories_high.fbx"
  ],
  "cage_file": "D:\\Assets\\Bake\\character_cage.fbx",
  "low_as_high": false,
  "cage_mode": "Custom file",
  "confirm": true
}
```

Painter can link common baking properties across Texture Sets. The response includes `impacted_texture_sets`, and the operation rolls every touched value back if one update fails.

## 3. Capture and apply portable presets

Capture all exposed baker settings or only selected bakers:

```json
{
  "texture_set": "Body",
  "bakers": ["Normal", "AO", "Curvature", "ID"]
}
```

The returned payload uses schema `substance-painter-mcp/baking-preset@1`. It includes enablement, enabled bakers, standard UDIMs, curvature method, common values, and per-baker values. File, FileList, and Resource widgets are omitted deliberately; assign filesystem-backed inputs through `set_baking_mesh_inputs` or import and connect them through `set_baking_resource_input` on each machine.

Painter 12.1 exposes `OffsetMap` as a common Resource property for skew correction. Import the texture through `import_project_resource`, then connect its verified URL with `set_baking_resource_input`. Auto Rebake and entering Skew Painting mode remain UI-only in Painter 12.1.1's public Python API; `get_capabilities` reports both controls as unavailable.

Apply the captured object with `apply_baking_preset` and `confirm=true`. Application uses the same validation, linked-impact reporting, and rollback guarantees as `configure_baking`.

## 4. Preflight without mutation

Call `preflight_bake` with an explicit list, or omit it to inspect the currently bake-enabled Texture Sets.

```json
{
  "texture_sets": ["Body", "Accessories"]
}
```

Each Texture Set reports:

- output resolution and antialiasing label;
- enabled bakers and standard UDIM tiles;
- Low as High, cage mode, and resolved high-poly/cage files;
- current mesh-map resource URLs;
- the expected baker outputs;
- structured warnings and errors.

Only a response with `ready: true` can be passed to batch execution. Preflight rejects duplicate or unknown Texture Sets, a closed or busy project, no enabled baker or tile, missing high-poly input when Low as High is disabled, and missing or inconsistent cage files.

## 5. Start and monitor a batch

```json
{
  "texture_sets": ["Body", "Accessories"],
  "confirm": true,
  "backup_path": "D:\\SubstanceBackups\\character_before_bake.spp",
  "backup_mode": "Incremental",
  "overwrite_backup": false
}
```

`start_batch_bake` repeats preflight, optionally creates and verifies a project copy, then temporarily enables exactly the requested Texture Sets for Painter's batch API. Poll `get_bake_job`; use `cancel_bake` for cooperative cancellation.

The server restores every Texture Set's original bake-enabled state after all terminal outcomes, including launch exceptions. This restoration does not undo generated mesh maps—successful baking is the requested mutation.

## Result manifests

A terminal batch result contains one entry for every expected Texture Set/baker pair:

```json
{
  "baker": "AO",
  "before": "resource://project0/old_ao?...",
  "after": "resource://project0/ambient_occlusion_Body?...",
  "present": true,
  "changed": true,
  "verified": true,
  "status": "updated"
}
```

`verified` means Painter reported global success and a mesh-map resource exists after the bake. `changed` distinguishes a newly generated resource URL from a retained one. At the Texture Set level, `expected_count`, `present_count`, `all_present`, and `all_verified` make automated acceptance straightforward.

Painter's public `BakingProcessEnded` event exposes Success, Cancel, or Fail globally. It does not provide per-baker diagnostic text, so a failed job reports a structured map manifest plus an explicit global error rather than inventing baker-specific causes. Painter's log remains the source for detailed engine diagnostics.

## Recommended production sequence

1. Save the working `.spp` and configure approved roots.
2. Assign high-poly/cage inputs and inspect `impacted_texture_sets`.
3. Apply a reviewed preset.
4. Run `preflight_bake` and resolve every error.
5. Start with a `backup_path` for valuable projects.
6. Poll until terminal, then require `all_verified` for every selected Texture Set.
7. Review visual bake quality in Painter; structured verification confirms resources, not artistic correctness.
