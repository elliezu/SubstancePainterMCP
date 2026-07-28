# Project Lifecycle and Typed Mesh Import

Version 0.9 adds a guarded workflow for creating, saving, opening, and reloading Painter projects. Context-changing operations require explicit confirmation and use approved roots, backups, jobs, and file verification.

## Approved roots

- `SP_MCP_MESH_ROOTS` protects primary project and reload meshes.
- `SP_MCP_RESOURCE_ROOTS` protects optional `.spt` templates and mesh-map inputs.
- `SP_MCP_PROJECT_ROOTS` protects new `.spp` outputs, backups, and projects opened through MCP.

The server rejects collisions between the current project, new output, backup, and open target before closing any context.

## Plan before creating

`plan_project_creation` validates all filesystem inputs and normalizes settings without modifying Painter.

```json
{
  "mesh_file_path": "D:\\Meshes\\character.fbx",
  "output_path": "D:\\SubstanceProjects\\character.spp",
  "settings": {
    "normal_map_format": "OpenGL",
    "tangent_space_mode": "PerFragment",
    "project_workflow": "UVTile",
    "default_texture_resolution": 2048,
    "import_cameras": false
  },
  "replace_current": true,
  "backup_current_path": "D:\\SubstanceProjects\\before_create.spp"
}
```

If a project is open, `replace_current=true` and a separate `backup_current_path` are mandatory. A ready plan has `ready: true` and no structured errors.

## Auto UV schema

Provide `auto_unwrap_settings` inside project settings or directly to mesh reload:

```json
{
  "recompute_seams": true,
  "recompute_uv_islands": true,
  "recompute_packing": true,
  "margin_size": 5,
  "island_orientation": "KeepOriginal",
  "uv_tiles": {
    "mode": "texel_density",
    "texel_density": 20,
    "reference_resolution": 2048
  },
  "avoid_elongated_uv_islands": true,
  "create_fewer_seams": false
}
```

UV tile packing may use `mode: count` with `max_count` from 1 to 1024, or `mode: texel_density` with density from 0.01 to 1,000,000 and a power-of-two reference resolution from 128 to 4096.

Painter 12.1's UI advertises a new Hard Surface unwrap mode, but the 12.1.1 public `AutoUnwrapSettings` dataclass does not expose a dedicated hard-surface field. The MCP reports and uses only supported public fields.

## USD and glTF settings

USD settings are supported during project creation and mesh reload:

```json
{
  "type": "usd",
  "scope_name": "/Character",
  "variants": null,
  "subdivision_level": 1,
  "frame": 0
}
```

Project creation additionally accepts glTF settings:

```json
{
  "type": "gltf",
  "invert_normal_maps": false
}
```

Painter 12.1.1 exposes no FBX-specific public settings dataclass. Generic scale, camera, tangent-space, workflow, resolution, and Auto UV settings still apply to FBX.

## Create and poll

Call `create_project` with the reviewed plan fields and `confirm=true`. The tool first creates and verifies the current-project backup, closes the current context, then starts Painter project creation.

Painter returns from `project.create()` while still busy. The MCP therefore waits for `ProjectEditionEntered` in Painter, saves the new project in Full mode from that event, and stores persistent job state. Poll `get_project_creation_job(job_id)` until `success` or `failed`; successful jobs include output existence, byte count, and `verified`.

If project creation or save fails, the callback closes any partial project and attempts to open the verified backup. The job records `recovered_project` and any recovery failure.

## Open and save

`open_project` accepts only an existing `.spp` below `SP_MCP_PROJECT_ROOTS` and requires `confirm=true`. If the current project is dirty, a separate `backup_current_path` is mandatory. If Painter rejects the target, the operation attempts to reopen the original path or verified backup.

`save_project` intentionally overwrites the current saved project. It requires `confirm=true`, accepts `Incremental` or `Full`, and verifies that Painter cleared the dirty state and that the file still exists with nonzero bytes.

## Typed mesh reload

`plan_mesh_reload` and `start_mesh_reload` retain their existing backup, preserve-strokes, camera, asynchronous status, and Texture Set diff behavior. Version 0.9 adds `auto_unwrap_settings` and USD `mesh_settings`; the normalized values are included in the plan and persistent job state.
