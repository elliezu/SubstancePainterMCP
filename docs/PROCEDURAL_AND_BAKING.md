# Procedural Sources, Anchor Points, and Baker Configuration

Version 0.6 exposes Painter's typed property system without falling back to arbitrary Python execution. Always inspect a source or baker first: property identifiers, value types, ranges, enum labels, and even visibility can differ between assets and Painter releases.

## Procedural Fill sources

`get_fill_parameters(uid, channel)` resolves the source currently assigned to a Fill layer and returns its editable parameters and named presets.

- Omit `channel` when the Fill is in Material mode.
- Supply a channel such as `BaseColor`, `Roughness`, or `Metallic` when the Fill is in Split mode.
- A uniform color, Anchor reference, or non-procedural bitmap has no procedural parameter interface and is rejected with a typed error.

Example response fields for one parameter:

```json
{
  "carbon_roughness": {
    "label": "Carbon Roughness",
    "widget": "Slider",
    "value": 0.5,
    "enum_values": {},
    "metadata": {"min": 0, "max": 1, "step": 0.01}
  }
}
```

Update only the identifiers that need to change:

```json
{
  "uid": 1204,
  "values": {
    "carbon_roughness": 0.37,
    "carbon_color": [0.2, 0.45, 0.75]
  }
}
```

`set_fill_parameters` converts colors and combobox labels to Painter-native values, checks numeric ranges, and applies the values as one batch. If conversion or application fails, it restores every touched parameter. File and resource widgets are intentionally rejected because they need separate approved-root policies.

Use `apply_fill_preset` only with a name returned by `get_fill_parameters`. Painter source presets are asset-specific and case-sensitive.

## Anchor Point source graphs

`list_anchor_points` returns stable Anchor UIDs together with the Texture Set, stack, owner layer, and whether the Anchor is in a mask. This context matters because an Anchor can only be referenced within a compatible Texture Set.

To bind an Anchor to one channel:

```json
{
  "uid": 1300,
  "anchor_uid": 1295,
  "channel": "BaseColor",
  "material_mode": false
}
```

To use a material Anchor, omit `channel` and set `material_mode` to `true`. Painter performs the final compatibility check; the server also rejects cross-Texture-Set bindings before mutation.

## Inspecting baker properties

`inspect_baking_parameters(texture_set)` returns Texture Set enablement, selected bakers, standard UDIM numbers, curvature mode, all common properties, and linked common-parameter Texture Sets.

Pass a baker such as `AO`, `Curvature`, `ID`, or `Position` to additionally return that baker's properties and linked group:

```json
{
  "texture_set": "Body",
  "baker": "AO"
}
```

Combobox properties expose labels and numeric values. Callers may send the readable label—for example, `"Cosine"` for AO Distribution—and the server resolves it with Painter's runtime metadata.

## Transactional configuration

`configure_baking` requires `confirm=true`. Every field is optional, but at least one change must be requested.

```json
{
  "texture_set": "Body",
  "enabled": true,
  "enabled_bakers": ["Normal", "AO", "Curvature"],
  "enabled_uv_tiles": [1001, 1002],
  "curvature_method": "FromMesh",
  "common_values": {
    "OutputSize": [11, 11],
    "DilationWidth": 16
  },
  "baker_values": {
    "AO": {
      "NbSecondary": 64,
      "Distribution": "Cosine"
    },
    "Curvature": {
      "AutoMinMax": true
    }
  },
  "confirm": true
}
```

The operation snapshots all touched state before editing. If any property, baker, or UV tile fails validation or application, the server restores Texture Set enablement, enabled bakers, selected tiles, curvature mode, and every touched property.

Painter can link common or per-baker properties across Texture Sets. The response therefore includes `impacted_texture_sets`; review that list before starting a bake. Use `start_bake` and `get_bake_job` only after the configuration is verified, and use an optional `.spp` backup for production projects.
