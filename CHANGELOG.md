# Changelog

All notable changes to this project are documented in this file.

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
