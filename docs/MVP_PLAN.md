# Creature Lab — MVP Plan

**Status:** bootstrap plan  
**Primary decision:** Python-first MVP with PyBullet + Viser, designed as a backend-agnostic creature lab.  
**Core rule:** Every creature is JSON. Every task is JSON. Every episode is a trace. Every simulator is an adapter.

## 1. Product concept

Creature Lab is a minimal, visual simulation playground where humans or LLM agents design small modular robot-creatures, run them in simple physical worlds, mutate their bodies/controllers, and save animated replays.

The repo should feel like an agent-accessible physical zoo. Instead of giving an agent only document/browser/code tools, we give it safe physical tools: create limbs, change joints, tune motors, run episodes, inspect failures, damage parts, save the best creature, and replay the lineage.

The first public impression should be:

```text
clone repo -> install -> run one command -> browser opens -> weird little creature moves
```

The project should be fun before it is serious. The fun visual loop is the hook. The clean data contracts are what make it useful later.

## 2. MVP boundaries

MVP is:

- a Python package
- a schema-driven creature format
- a simple simulator wrapper
- a live browser viewer
- a trace/replay system
- a tiny set of tasks
- a baseline no-LLM mutator
- an optional LLM tool loop
- docs and tests that make the architecture clear

MVP is not:

- a full robotics simulator
- a Unity/Godot game
- an Isaac/ROS project
- an RL benchmark suite
- photorealistic simulation
- real hardware control
- a cloud product
- a mesh/asset pipeline

## 3. Recommended stack

Use the smallest stack that can produce live animated creatures quickly:

- Python 3.11+
- uv for package/environment management
- PyBullet as first physics backend
- Viser as live browser-based 3D viewer
- Pydantic for schemas and validation
- Typer for CLI
- Rich for readable terminal output
- NumPy for math
- imageio/imageio-ffmpeg for replay export
- LiteLLM for optional model-provider abstraction
- pytest for tests
- ruff for linting/formatting

Do not start with Unity, Godot, Isaac, ROS, CUDA, databases, or a web app framework. Those can come later through adapters/exporters.

## 4. Architecture

The project must not become backend-specific spaghetti. PyBullet is the first backend, not the architecture.

```text
User prompt or CLI command
        |
        v
Agent tools / baseline mutator
        |
        v
CreatureSpec.json + TaskSpec.json
        |
        v
Backend adapter: PyBullet first, MuJoCo/Godot/Unity later
        |
        v
FrameState stream
        |
        v
EpisodeTrace.jsonl
        |
        v
Live viewer / replay viewer / video exporter / future engine viewers
```

Permanent layers:

- schemas
- task definitions
- controller definitions
- agent tool contracts
- episode trace format
- lineage/artifact layout
- tests around those contracts

Disposable/adaptable layers:

- PyBullet implementation details
- Viser scene implementation
- future Unity/Godot/MuJoCo adapters

## 5. Core data contracts

### 5.1 CreatureSpec

`CreatureSpec` is the source of truth for a creature. It should describe only portable concepts:

- name and metadata
- body parts
- primitive shapes: box, sphere, capsule, cylinder
- part dimensions
- masses
- colors
- parent/child joints
- joint type: fixed, hinge, ball later
- joint anchor/axis/limits
- motors and controller parameters

Example shape:

```json
{
  "name": "tripod",
  "parts": [
    {"id": "torso", "shape": "box", "size": [0.45, 0.22, 0.12], "mass": 1.0},
    {"id": "leg_a", "shape": "capsule", "length": 0.35, "radius": 0.04, "mass": 0.2}
  ],
  "joints": [
    {"id": "hip_a", "parent": "torso", "child": "leg_a", "type": "hinge", "axis": [0, 1, 0], "limit": [-0.8, 0.8]}
  ],
  "motors": [
    {"joint": "hip_a", "type": "sinusoid", "amplitude": 0.6, "frequency": 2.0, "phase": 0.0}
  ]
}
```

Validation rules:

- all part ids are unique
- all joint ids are unique
- all joint parent/child ids exist
- every non-root part has one parent joint
- dimensions and masses are positive
- motor joint ids exist
- joint limits are valid
- colors are optional and bounded if present

### 5.2 TaskSpec

`TaskSpec` describes the world and scoring:

- task name
- duration
- timestep
- terrain type
- friction
- target position
- reward components
- optional damage event

Initial tasks:

1. `crawl_forward`: maximize forward distance.
2. `reach_target`: move toward a target marker.
3. `recover_after_damage`: damage a limb mid-run and score recovery.

### 5.3 FrameState

`FrameState` is a backend-neutral snapshot:

- timestamp
- part transforms: position + quaternion
- optional joint angles
- optional contacts
- instantaneous score
- events such as damage or fall

### 5.4 EpisodeTrace

`EpisodeTrace` is the replay artifact. It must allow animation without re-running physics.

It should include:

- run id
- creature spec hash or full spec reference
- task spec hash or full spec reference
- backend metadata
- score summary
- frame states
- events

Use newline-delimited JSON for large traces when needed.

### 5.5 AgentTrace

`AgentTrace` records the agent/mutator loop:

- attempt number
- observation
- mutation/action
- validation result
- score
- chosen best creature
- short explanation

This makes the project feel like a creature lineage lab, not just a physics viewer.

## 6. Backend adapter contract

Create a small backend protocol before implementing PyBullet details.

Expected interface:

```python
class SimBackend(Protocol):
    def build(self, creature: CreatureSpec, task: TaskSpec) -> None: ...
    def reset(self) -> None: ...
    def step(self, dt: float) -> FrameState: ...
    def apply_motor_targets(self, targets: dict[str, float]) -> None: ...
    def damage_part(self, part_id: str) -> None: ...
    def close(self) -> None: ...
```

Rules:

- only backend modules import PyBullet
- schema modules never import physics engines
- agents never import PyBullet
- viewers consume `FrameState` or `EpisodeTrace`, not PyBullet objects
- tests should exercise the backend through the protocol

## 7. Viewer and animation pipeline

The project is about animation, not still photos.

MVP viewer:

- Viser browser scene
- floor grid
- target marker
- colored primitive creature parts
- live transform updates
- contact markers
- motion trail
- score/status panel

Replay pipeline:

```text
run physics -> emit FrameState -> save EpisodeTrace -> replay trace -> optional GIF/MP4
```

Important distinction:

- replay portability is easy: any renderer can draw recorded poses
- physics portability is hard: different engines solve joints/friction differently

So the promise is:

> specs, tasks, tools, traces, and replays are portable; exact physics behavior is backend-dependent.

## 8. LLM tool layer

The LLM should make slow design decisions, not high-frequency motor decisions.

Allowed tools:

- inspect_creature
- add_limb
- remove_limb
- resize_limb
- set_joint_limit
- set_motor
- run_episode
- inspect_contacts
- inspect_score
- damage_limb
- save_creature

Avoid:

- raw torque control every simulation step
- arbitrary code execution from LLM output
- direct backend access
- unvalidated creature mutations

Every mutation must validate the resulting `CreatureSpec` before simulation.

## 9. Baseline mutator

The repo must be useful without an LLM provider. Include a tiny baseline mutator:

- random amplitude/frequency/phase changes
- random limb length changes within safe bounds
- simple hill-climb: keep the best creature
- deterministic seed support

This gives tests and demos without external services.

## 10. CLI design

Planned command shape:

```bash
uv run creature-lab demo
uv run creature-lab run examples/tripod.json --task crawl_forward
uv run creature-lab replay runs/latest
uv run creature-lab evolve examples/tripod.json --attempts 20
uv run creature-lab ask "make it crawl farther" --attempts 5
uv run creature-lab validate examples/tripod.json
```

Early implementation can support only `demo`, `run`, `validate`, and `replay`.

## 11. Repository layout

Target layout:

```text
creature_lab/
  __init__.py
  cli.py
  schema/
    creature.py
    task.py
    trace.py
  backends/
    base.py
    pybullet_backend.py
  controllers/
    sinusoid.py
    cpg.py
  viewers/
    viser_viewer.py
    trace_player.py
    video_exporter.py
  agents/
    tools.py
    loop.py
    prompts.py
  export/
    urdf.py
    mjcf.py
examples/
  worm.json
  tripod.json
  spider.json
docs/
  MVP_PLAN.md
tests/
  test_schema.py
  test_trace.py
  test_backend_smoke.py
```

Do not create all modules before they are needed. This is the map, not permission to overbuild.

## 12. Road to MVP

### Phase 0 — Repo bootstrap

Deliverables:

- README
- CLAUDE.md
- .gitignore
- docs/MVP_PLAN.md

Success:

- repo communicates the idea clearly
- future coding agents have guardrails
- no premature implementation clutter

### Phase 1 — Package skeleton and schemas

Deliverables:

- pyproject.toml
- package skeleton
- `CreatureSpec`, `TaskSpec`, `FrameState`, `EpisodeTrace`
- example creatures
- schema validation tests
- JSON round-trip tests

Success:

- `uv sync` works
- `uv run pytest` works
- invalid creatures fail validation
- example creatures validate

### Phase 2 — Controller and trace

Deliverables:

- sinusoidal controller
- target generation per joint
- trace writer/reader
- simple score helpers

Success:

- controller outputs deterministic targets
- traces can be saved and loaded
- tests avoid exact physics trajectories

### Phase 3 — PyBullet backend smoke simulation

Deliverables:

- backend protocol
- PyBullet adapter
- primitive body creation
- hinge constraints/motors
- plane terrain
- short run command

Success:

- a simple creature simulates for a few seconds
- frames are emitted
- score is finite
- trace is saved

### Phase 4 — Viser live viewer

Deliverables:

- live browser viewer
- primitive rendering from `FrameState`
- target marker
- floor grid
- score panel
- motion trail/contact markers if easy

Success:

- `uv run creature-lab demo` opens a browser view
- creature moves live
- replay is saved

### Phase 5 — Replay and export

Deliverables:

- trace replay command
- optional GIF/MP4 export
- artifact folder structure

Success:

- replay works without re-running physics
- demo artifacts are shareable

### Phase 6 — Baseline evolution loop

Deliverables:

- simple mutation operators
- hill-climb loop
- lineage trace
- best creature saving

Success:

- `evolve` runs multiple attempts
- best score is tracked
- best creature and replay are saved

### Phase 7 — Optional LLM loop

Deliverables:

- tool wrappers
- prompt template
- validation around mutations
- provider abstraction
- agent trace

Success:

- LLM can perform a few safe design iterations
- invalid mutations are rejected
- no backend internals leak into tools

## 13. What not to do

- Do not expose PyBullet as the public API.
- Do not force users to write URDF/MJCF for v0.
- Do not start with RL training.
- Do not add Unity/Godot before the Python demo works.
- Do not build a full web dashboard before the live viewer works.
- Do not optimize for photorealism.
- Do not let the LLM execute arbitrary simulator code.
- Do not rely on exact physics reproducibility for tests.
- Do not commit generated videos or run folders.

## 14. Future extensibility

### MuJoCo

Add an MJCF exporter and MuJoCo backend later for more serious robotics-style simulation.

### Unity

Use a future URDF/export path and a Unity-side viewer/player if polished game-engine visuals become important.

### Godot

Use glTF/GLB and a Godot scene builder for a game-like creature zoo later. Do not make Godot a v0 dependency.

### Browser viewer

A Three.js/Rapier frontend can later replay `EpisodeTrace` in the browser. This is easier than moving physics into the browser first.

### RL

Add a Gymnasium-compatible wrapper only after tasks, specs, traces, and backend loops are stable.

## 15. MVP acceptance criteria

MVP is done when:

- a fresh clone can install with documented commands
- at least one creature spec validates
- at least one task spec validates
- a PyBullet backend can run a short episode
- Viser can show live animated motion
- traces are saved and replayable
- a baseline mutator can run multiple attempts
- tests cover schemas, traces, and backend smoke behavior
- README includes an animated artifact or clear path to generate one

## 16. Immediate next tasks

1. Add package skeleton and `pyproject.toml`.
2. Implement Pydantic schemas.
3. Add example `tripod.json` and `crawl_forward` task.
4. Add validation CLI.
5. Add schema tests.
6. Add backend protocol.
7. Add minimal PyBullet backend.
8. Add live Viser viewer.
9. Save and replay traces.
10. Add baseline mutator.

Keep every step small and testable.
