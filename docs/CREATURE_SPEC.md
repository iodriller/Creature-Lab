# Creature Spec

`CreatureSpec` is the portable JSON body graph used by every simulator backend.

```bash
uv run creature-lab schema creature --out docs/schemas/creature.schema.json
uv run creature-lab validate examples/quadruped.json
```

## Shape

```json
{
  "name": "quadruped",
  "parts": [],
  "joints": [],
  "motors": [],
  "metadata": {}
}
```

- `parts` are rigid bodies. Supported shapes are `box`, `sphere`, `capsule`, and `cylinder`.
- `joints` connect parts into one rooted acyclic graph. Supported joint types are `fixed` and
  `hinge`.
- `motors` drive hinge joints with sinusoidal open-loop control.
- `metadata` is freeform project data and does not affect physics.

## Parts

Every part needs a unique `id`, `shape`, and positive `mass`.

- `box` requires `size: [x, y, z]`.
- `sphere` requires `radius`.
- `capsule` and `cylinder` require `radius` and `length`.
- Optional `color` is RGB with values from `0` to `1`.

## Joints

Each joint names a `parent`, `child`, `type`, optional `anchor`, optional hinge `axis`,
optional `limit`, and optional `rest_orientation`.

The root part is the only part that is not the child of any joint. Creature Lab rejects:

- missing parent/child part ids
- more than one root
- cycles
- duplicate joint ids
- hinge joints with a zero axis

## Motors

Each motor references one known joint:

```json
{"joint": "hip_fl", "type": "sinusoid", "amplitude": 0.7, "frequency": 2.0, "phase": 0.0, "offset": 0.1, "max_force": 20.0}
```

Creature Lab rejects motors that reference unknown joints or duplicate the same joint.
`offset` is the center angle around which the sinusoid moves. `max_force` is an optional
position-servo torque limit in N·m; when omitted, the backend's small-creature default is used.
Human-scale bodies should declare it explicitly—the packaged 60 kg humanoid uses 160 N·m.

## Common Validation Failures

Invalid parent:

```json
{"id": "hip", "parent": "missing", "child": "leg", "type": "hinge"}
```

Unsupported shape:

```json
{"id": "body", "shape": "mesh", "mass": 1.0}
```

Missing required body dimensions:

```json
{"id": "body", "shape": "box", "mass": 1.0}
```

Unknown motor joint:

```json
{"joint": "missing_joint", "type": "sinusoid", "amplitude": 0.5, "frequency": 1.0}
```
