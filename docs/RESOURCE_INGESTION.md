# Resource Ingestion and Procedural Inputs

Version 1.0 provides a guarded path from an approved local file to a verified Painter ResourceID in project, session, or persistent shelf scope, then into Fill, Generator, Filter, or baking inputs.

## Approved roots and safe content

Configure one or more input roots in the MCP server environment:

```json
{
  "env": {
    "SP_MCP_RESOURCE_ROOTS": "D:\\SubstanceResources;E:\\StudioLibrary"
  }
}
```

All import tools require `confirm=true`, an existing regular file below one of those roots, and a safe usage. Supported usages are `ALPHA`, `BASE_MATERIAL`, `BRUSH`, `COLOR_LUT`, `ENVIRONMENT`, `EXPORT`, `FILTER`, `FONT`, `GENERATOR`, `PROCEDURAL`, `SMART_MASK`, `SMART_MATERIAL`, and `TEXTURE`.

Shader, particle script, emitter/receiver, and other executable-oriented usages are not accepted. Common executable and script-like extensions are rejected even when placed under an approved root. Painter still performs final format/usage compatibility validation.

## Project versus session resources

Use `import_project_resource` when the resource must travel with the `.spp` project:

```json
{
  "file_path": "D:\\SubstanceResources\\fabric_mask.png",
  "usage": "TEXTURE",
  "name": "Fabric Mask",
  "group": "Studio Imports",
  "confirm": true
}
```

Use `import_session_resource` for temporary resources that should disappear when Painter exits. A project import requires an open, non-busy project; a session import does not.

Both tools return a versioned `resource://` URL, Painter context/location/type, category, usages, and `verified`. The server re-retrieves the exact returned ResourceID before reporting success.

Project imports are persistent mutations. Painter's public API does not expose a general-purpose safe delete for an arbitrary embedded project resource, so use session scope for disposable experiments.

## Persistent shelf resources

Use `list_shelves` to inspect every configured shelf, its path, whether it accepts imports, and whether Painter is currently crawling it. `import_shelf_resource` uses the same approved-root, safe-usage, confirmation, and exact-ResourceID verification rules as project/session imports. Omit `shelf_name` to target Painter's user shelf, or supply a name returned by `list_shelves`:

```json
{
  "file_path": "D:\\SubstanceResources\\fabric_mask.png",
  "usage": "TEXTURE",
  "shelf_name": "studio-library",
  "name": "Fabric Mask",
  "group": "Studio Imports",
  "confirm": true
}
```

Unlike session imports, shelf imports remain on disk and can be reused by later projects and Painter sessions. The server refuses read-only shelves and reports the shelf name/path, exact versioned URL, Painter type, usages, and verification result.

Call `start_shelf_refresh(shelf_name, confirm=true)` after files are changed outside Painter. The operation attaches strong handlers before requesting refresh and returns a persistent job ID. Poll `get_shelf_refresh_job(job_id)` for `starting`, `running`, `success`, or `failed`; success is set only after Painter emits `ShelfCrawlingEnded`. Starting a second refresh while that shelf is already crawling is rejected.

## Procedural image inputs

`get_procedural_inputs(uid, channel)` supports:

- material-mode or split-mode Fill layers;
- Fill effects;
- Generator effects;
- Filter effects.

For split-mode Fill sources, provide the active channel. Generator and Filter effects reject a channel because they expose one procedural source directly.

Each input reports its source type, versioned ResourceID when bitmap-backed, uniform color and color space, Anchor UID when reference-backed, and source UID.

Connect an imported resource:

```json
{
  "uid": 1402,
  "input_name": "texture",
  "resource_url": "resource://project0/Fabric Mask?version=..."
}
```

Or restore the graph's default input:

```json
{
  "uid": 1402,
  "input_name": "texture",
  "reset": true
}
```

Exactly one action is required. Before assignment, the server snapshots bitmap, uniform-color, or Anchor state and restores it if Painter rejects the new resource.

## Baking Resource properties

Painter's baking property set may include Resource widgets. In Painter 12.1, the common `OffsetMap` input stores a grayscale skew-correction map.

```json
{
  "texture_set": "Body",
  "parameter": "OffsetMap",
  "resource_url": "resource://project0/Skew Offset?version=...",
  "confirm": true
}
```

Set `baker` to target a per-baker Resource property. Use `clear=true` instead of `resource_url` to clear the input. The tool verifies the ResourceID, confirms that the runtime property widget is `Resource`, snapshots the prior value, applies transactionally, and reports every linked Texture Set affected.

## Painter 12.1 Auto Rebake and Skew Painting

[Painter 12.1 introduced Auto Rebake and Skew Correction Painting](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/release-notes/version-12-1), but the 12.1.1 public Python `baking` module does not expose methods for toggling Auto Rebake or entering the Skew Painting mode. `get_capabilities` therefore reports `auto_rebake_control: false` and `skew_painting_control: false` on that build.

This is intentionally capability-based. The MCP exposes supported skew data such as `SkewFaceBehavior` through typed baking configuration and `OffsetMap` through the dedicated Resource setter, while avoiding fragile screen-coordinate automation for UI-only controls.
