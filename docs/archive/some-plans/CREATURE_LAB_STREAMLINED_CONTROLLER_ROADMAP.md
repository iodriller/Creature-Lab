# Creature Lab — Streamlined Controller, UX, and Product Roadmap

**Repository:** `oney-erge/Creature-Lab`  
**Prepared:** 2026-07-20  
**Target release:** `0.2.0`  
**Status:** Proposed consolidated roadmap

---

## 1. Executive decision

Creature Lab already has most of the physical simulation foundation it needs:

- articulated `CreatureSpec` bodies
- portable `TaskSpec` worlds and rewards
- PyBullet and MuJoCo backends
- deterministic sinusoid and CPG gait generation
- a low-level step-by-step `CreatureEnv`
- observations, actions, traces, diagnosis, robustness, reports, evolution, and export
- a browser build editor

The missing product layer is **controller architecture**.

Today, the standard `run` and build-editor paths mainly execute a prewritten oscillating gait. A target can affect the score, but it normally does not steer the robot. The repository already contains pieces of a closed-loop system—target-vector observations, step actions, position/velocity/torque control—but these pieces are not yet connected into the primary workflow.

The next roadmap should therefore **not add more unrelated features**. It should turn Creature Lab into a coherent system where a user can:

```text
Build body
  → choose movement behavior
  → configure controller
  → simulate
  → understand why it failed
  → improve body and controller
  → qualify the result
  → export a reproducible design pack
```

The recommended product identity remains:

> **Creature Lab is a Git-native design debugger and qualification lab for articulated robots.**

Its strongest promise should become:

> **Creature Lab tells you whether a robot can perform a physical objective, why it fails, and which body or controller change is most likely to improve it.**

---

## 2. What exists today

### 2.1 The normal movement path

The standard simulation path selects one of two controllers:

- `sinusoid`
- `cpg`

The controller emits desired joint angles. PyBullet or MuJoCo then applies those commands and resolves gravity, inertia, collisions, friction, and contacts.

The target and reward measure the outcome. They do not normally produce steering commands.

### 2.2 The closed-loop substrate already exists

`CreatureEnv` already supports:

- `reset()`
- `step(action)`
- normalized joint action vectors
- position, velocity, and torque modes
- root position and velocity observations
- joint position and velocity observations
- contact observations
- optional target-vector observations
- recording observations and actions into traces

This means Creature Lab does **not** need a new simulation system. It needs a controller contract, controller configuration, better observations, and a unified user-facing path.

### 2.3 The current configuration gaps

The following are missing or incomplete:

1. **No first-class `ControllerSpec` JSON**
   - Controller selection is mainly a CLI string.
   - CPG parameters are constructor defaults rather than project configuration.
   - Controller settings are not a portable, independently versioned artifact.

2. **No target-directed built-in controller**
   - A target may change scoring.
   - The default gait does not turn toward it or slow down near it.

3. **No reusable controller interface**
   - There is no clear lifecycle such as `reset()`, `observe()`, `act()`, and `describe()` shared across controller types.

4. **Insufficient feedback signals**
   - Target vector is available, but body-frame target bearing, heading error, root orientation, gravity vector, angular velocity, and normalized terrain-relative signals are not fully standardized.

5. **Actuator realism is too thin**
   - Motor configuration mostly contains sinusoid amplitude, frequency, and phase.
   - Backend actuation uses broad defaults rather than per-joint force, torque, speed, stiffness, and damping limits.

6. **The primary CLI/editor path bypasses `CreatureEnv`**
   - Closed-loop control exists as an advanced API rather than the normal way to run target tasks.

7. **Controller-aware diagnosis is missing**
   - The tool can identify falls and drift, but it cannot yet explain controller saturation, steering failure, oscillation, overshoot, insufficient torque, or poor feedback tuning.

8. **Qualification does not yet combine body, controller, task, robustness, and backend agreement into one pass/fail result.**

---

## 3. Product boundary

Creature Lab must remain separate from Agentarium.

### Creature Lab owns

- one articulated robot at a time
- morphology and actuator authoring
- deterministic and feedback controllers
- physical simulation
- body/controller debugging
- robustness and sim-to-sim analysis
- qualification profiles
- local optimization
- reproducible traces and exports

### Agentarium owns

- multi-agent orchestration
- personas and agent memory
- challenge generation
- tool-call timelines
- worlds and broad challenge systems
- leaderboards
- cloud execution
- Studio-style agent experiences
- agents as the primary product actor

### Hard exclusions

Do not add to Creature Lab:

- multi-agent modes
- agent personas or memory
- generic tool-calling frameworks
- challenge-generation chat
- world-building systems
- leaderboards
- cloud simulation services
- real-time LLM motor or torque control
- a broad GPU-scale RL training platform
- a second frontend framework or full web application

LLMs may remain optional **design editors between simulations**. They should not drive the robot at simulation frequency.

---

## 4. Target architecture

The project should formalize four portable artifacts.

```text
creature.json
  Physical structure and actuator capabilities

task.json
  World, objective, target, disturbances, and reward

controller.json
  Movement policy, observations, gains, gait, steering, and safety limits

run_manifest.json
  Exact creature + task + controller + backend + versions + seed
```

The durable rule becomes:

> **Every creature is JSON. Every task is JSON. Every controller is JSON. Every episode is a trace. Every simulator is an adapter.**

### 4.1 Responsibility split

#### `CreatureSpec`

Keep only physical properties:

- parts
- mass and geometry
- joints and limits
- actuator assignment
- actuator capability:
  - maximum force/torque
  - maximum velocity
  - stiffness/damping defaults
  - optional electrical/mechanical metadata later

#### `TaskSpec`

Keep:

- terrain
- target or waypoint
- episode duration
- disturbances
- success conditions
- reward weights
- termination rules
- qualification thresholds when task-specific

#### `ControllerSpec`

Add:

- controller type
- controlled joints
- action mode
- observation signals
- gait parameters
- steering parameters
- posture/balance parameters
- safety limits
- target stopping behavior
- deterministic seed where applicable

#### `RunManifest`

Record:

- hashes of all three specs
- backend and backend version
- Creature Lab version
- timestep and seed
- exact command
- controller implementation name/version
- warnings
- output artifacts

---

## 5. Controller system

## 5.1 Controller protocol

Create a backend-neutral controller protocol.

```python
class Controller(Protocol):
    def reset(self, context: ControllerContext) -> None: ...
    def act(
        self,
        observation: ControllerObservation,
        t: float,
    ) -> JointCommand: ...
    def describe(self) -> ControllerMetadata: ...
```

A controller must never directly import PyBullet or MuJoCo. It receives normalized observations and returns joint commands.

### Required core types

- `ControllerContext`
- `ControllerObservation`
- `JointCommand`
- `ControllerMetadata`
- `ControllerSpec`
- `ControllerRegistry`

### Recommended files

```text
creature_lab/
  controllers/
    base.py
    registry.py
    legacy_sinusoid.py
    cpg.py
    target_seek.py
    posture.py
    hybrid.py
    scripted.py
  schema/
    controller.py
```

---

## 5.2 Controller families

### P0 controllers

#### 1. Legacy sinusoid

Purpose:

- preserve all existing creatures and baselines
- provide exact backward compatibility
- convert current `MotorSpec` amplitude/frequency/phase into a generated `ControllerSpec`

This remains the simplest movement demonstration.

#### 2. Configurable CPG

Move the currently hard-coded CPG parameters into JSON:

- global frequency
- amplitude
- coupling strength
- phase lag
- per-joint amplitude overrides
- per-joint phase offsets
- joint chain or group definition
- optional contact-based phase reset

This becomes the preferred open-loop locomotion controller.

#### 3. Target-seeking gait controller

This is the highest-priority missing controller.

It should:

1. read target position relative to the robot
2. transform the target vector into the robot body frame
3. calculate target distance and heading error
4. modulate left/right gait amplitude or phase
5. slow down near the target
6. stop within a configurable radius
7. optionally reverse only when the target is significantly behind

The first version should wrap the CPG rather than inventing a whole locomotion policy.

Conceptually:

```text
Base CPG gait
  + heading-error steering
  + target-distance speed scaling
  + stop radius
  = target-seeking locomotion
```

This is deterministic, lightweight, explainable, and does not require an LLM or trained neural network.

#### 4. Posture and balance controller

Add a small feedback layer that can:

- maintain a target root height
- resist excessive pitch and roll
- reduce gait amplitude during instability
- apply hip/leg corrections
- stop or enter recovery mode after a severe tilt

Start with proportional-derivative feedback and gravity-vector stabilization.

#### 5. Hybrid controller

Compose:

```text
gait generator
  + steering
  + posture stabilization
  + safety limiter
```

Do not create a general behavior-tree framework. A small, explicit composition model is enough.

### P1 controllers

#### 6. Waypoint follower

- ordered target list
- waypoint radius
- final stop radius
- optional timeout per waypoint
- path completion metrics

#### 7. Push-recovery reflex

- detect impulse or rapid angular velocity
- widen stance or reduce gait
- corrective joint posture
- return to normal gait when stable

#### 8. Contact-adaptive CPG

- reset or adjust oscillator phases based on foot contact
- reduce slipping
- improve irregular-terrain behavior
- remain deterministic

#### 9. Scripted finite-state controller

Support a deliberately small state machine:

```text
stand → walk → turn → stop → recover
```

This should be a physical-controller utility, not a generic agent workflow engine.

### P2 controller adapters

#### 10. Learned-policy adapter

Allow an externally trained policy to plug into `CreatureEnv`:

- Python callable
- NumPy checkpoint format
- optional ONNX inference
- optional Stable-Baselines3 adapter

Creature Lab should evaluate, compare, diagnose, and qualify such policies. It should not become a large-scale RL training platform.

---

## 6. Controller configuration

Create `ControllerSpec` as a discriminated union.

### Example

```json
{
  "schema_version": "1",
  "name": "quadruped_target_seek",
  "type": "hybrid",
  "action": {
    "mode": "position",
    "joints": ["fl_hip", "fr_hip", "rl_hip", "rr_hip"],
    "clip_range": [-1.0, 1.0]
  },
  "observation": {
    "root_orientation": true,
    "root_linear_velocity": true,
    "root_angular_velocity": true,
    "gravity_body": true,
    "joint_angles": true,
    "joint_velocities": true,
    "contacts": true,
    "target_body_vector": true,
    "target_distance": true,
    "heading_error": true
  },
  "gait": {
    "type": "cpg",
    "frequency": 1.5,
    "amplitude": 0.8,
    "phase_lag": 2.0,
    "coupling": 6.0
  },
  "steering": {
    "enabled": true,
    "turn_gain": 0.75,
    "max_turn_scale": 0.6,
    "slow_radius": 1.0,
    "stop_radius": 0.2
  },
  "posture": {
    "enabled": true,
    "roll_kp": 0.5,
    "pitch_kp": 0.5,
    "angular_damping": 0.1,
    "instability_slowdown": 0.6
  },
  "safety": {
    "command_rate_limit": 8.0,
    "joint_limit_margin": 0.05,
    "stop_on_fall": true
  }
}
```

### Backward compatibility

Existing commands must continue to work:

```bash
creature-lab run creature.json --task task.json --controller sinusoid
creature-lab run creature.json --task task.json --controller cpg
```

Internally, these should resolve to built-in controller presets.

Existing `MotorSpec` gait fields should remain readable for `0.2.x`. Add a migration/export command:

```bash
creature-lab controller extract creature.json --out controller.json
```

The output becomes an explicit legacy-sinusoid controller.

Do not silently change old scores or baselines.

---

## 7. Observation and action upgrades

## 7.1 Observation upgrades

Extend the current observation contract with:

- root orientation quaternion
- root forward vector
- gravity vector expressed in the body frame
- root angular velocity
- target vector expressed in the body frame
- target distance
- target bearing / heading error
- normalized joint positions
- joint-limit proximity
- contact duration, not only contact boolean
- optional terrain height beneath each foot
- optional terrain slope beneath the root
- actuator saturation flags

Keep all signals backend-neutral.

### Coordinate convention

Document one convention and test it across both backends:

- world +X = nominal forward
- world +Z = up
- body-forward axis defined by the root part
- positive heading error direction
- quaternion order
- angle units in radians
- length in meters
- force in newtons
- torque in newton-meters

This is essential for controller portability.

## 7.2 Action and actuator upgrades

Expand actuator configuration.

Recommended actuator fields:

```json
{
  "joint": "front_left_hip",
  "max_force": 8.0,
  "max_torque": 8.0,
  "max_velocity": 5.0,
  "position_kp": 0.4,
  "velocity_kd": 0.05,
  "command_deadband": 0.01
}
```

The backends should consume these values consistently.

Remove the single hidden global maximum-force behavior as the long-term default. Preserve it only as a legacy fallback.

### Safety normalization

- clamp commands to joint limits
- expose saturation in traces
- rate-limit abrupt command changes
- reject non-finite actions
- define torque and velocity ranges explicitly
- record applied command after clipping, not only requested command

---

## 8. Unify the run path

The normal simulation path and `CreatureEnv` should converge.

### Target state

```text
CLI / build editor / benchmark / qualification
              ↓
        ControllerRunner
              ↓
         CreatureEnv
              ↓
     backend-neutral commands
              ↓
      PyBullet or MuJoCo
              ↓
      observations + trace
```

### Required change

Replace the separate `_simulate()` control loop with a shared runner that can execute:

- built-in named controller
- `controller.json`
- Python policy adapter
- learned-policy adapter later

The existing simple controller path can remain as a wrapper over the new runner.

This prevents:

- duplicated stepping logic
- different trace contents
- different fall termination behavior
- controller features working only through the API
- editor/CLI disagreement

---

## 9. CLI redesign

Keep beginners on one clear path.

## 9.1 Primary commands

```bash
creature-lab build
creature-lab run creature.json --task task.json
creature-lab diagnose latest
creature-lab improve latest
creature-lab qualify creature.json --task task.json
creature-lab export latest
```

## 9.2 Controller commands

```bash
creature-lab controller list
creature-lab controller show target_seek
creature-lab controller scaffold target_seek --out controller.json
creature-lab controller validate controller.json --creature creature.json --task task.json
creature-lab controller extract creature.json --out controller.json
```

Run examples:

```bash
creature-lab run creature.json \
  --task reach_target.json \
  --controller target_seek

creature-lab run creature.json \
  --task reach_target.json \
  --controller controller.json
```

### Presets

Ship a small set:

- `stand`
- `crawl_forward`
- `target_seek`
- `push_recovery`
- `stability_hold`

Do not expose every numerical field during onboarding.

## 9.3 Comparison

```bash
creature-lab compare-controller \
  creature.json \
  --task reach_target.json \
  --controllers sinusoid,cpg,target_seek \
  --html controller-comparison.html
```

Show:

- final score
- target progress
- completion time
- falls
- energy
- command saturation
- robustness mean/std
- sim-to-sim gap

---

## 10. Build editor redesign

Keep Viser. Do not introduce a separate frontend stack.

## 10.1 Simplified top-level workflow

Use tabs or clearly separated sections:

1. **Build**
2. **Movement**
3. **Task**
4. **Run**
5. **Diagnose**
6. **Qualify**
7. **Export**

Avoid a long nested folder wall.

## 10.2 Movement tab

### Simple mode

Show intent-level choices:

- Stand
- Move forward
- Move to target
- Recover from push
- Custom

For `Move to target`, show only:

- gait speed
- turning strength
- stop distance
- balance assistance

### Advanced mode

Expose:

- controller type
- controlled joints
- CPG frequency/amplitude/coupling/phase lag
- per-joint overrides
- steering gain
- posture gains
- actuator limits
- observation signals
- command mode

## 10.3 Target interaction

- render the target in the 3D scene
- allow dragging it
- show target distance
- show target bearing
- draw robot-forward arrow
- draw target-direction arrow
- show when the controller considers the target reached

## 10.4 Editor P0 usability

Implement before adding more panels:

- undo
- redo
- reset current section
- named snapshots
- hierarchy tree for body parts and joints
- copy/paste or duplicate limb
- mirror operation with preview
- grid/angle snapping
- safe confirmation for destructive edits
- incremental preview updates
- asynchronous simulation
- progress indicator
- cancellation
- separate simulation execution from replay playback
- keyboard shortcuts
- clear unsaved/external-change state

## 10.5 Beginner behavior

The editor should automatically choose:

- PyBullet
- a valid controller preset
- reasonable actuator defaults
- a compatible task preset
- a short simulation duration

Do not force new users to understand backend differences, CPG coupling, action spaces, or torque control before the first run.

---

## 11. Controller-aware diagnosis

Diagnosis should answer:

> Is the failure caused by the body, actuator capability, controller, task setup, terrain, or simulator sensitivity?

### New diagnostic categories

#### Actuation

- no controlled joints
- command always near zero
- actuator saturation
- insufficient maximum force/torque
- excessive speed demand
- joint repeatedly hitting limits
- command discontinuity
- unstable high-frequency oscillation

#### Gait

- phase cancellation
- asymmetric gait
- backward gait
- excessive lateral drift
- insufficient stride amplitude
- excessive stride amplitude
- contact timing mismatch
- slipping rather than stepping

#### Steering

- target not visible in observations
- heading error not decreasing
- steering gain too low
- steering gain too high
- unstable turn oscillation
- correct heading but no forward progress
- target overshoot
- stop radius never satisfied
- robot circles target

#### Posture

- pitch instability
- roll instability
- root height collapse
- corrective controller saturation
- controller fights the base gait
- recovery never re-enters locomotion

#### Task/configuration

- target reward but non-target-aware controller
- unreachable target beyond terrain extent
- episode too short for target distance
- target behind robot but reverse disabled
- actuator capability incompatible with body mass
- controller references missing joints
- observation requested but unavailable

#### Portability

- controller works in one backend only
- applied-command clipping differs materially
- contact-dependent controller is backend-sensitive
- high sim-to-sim trajectory divergence

### Design Autopsy

Create a single report section that reconstructs failure:

```text
Observed
  Robot turned only 4° while target bearing was 38°.

Controller evidence
  Left/right gait amplitude differed by only 3%.

Physical evidence
  Rear-left actuator saturated during 72% of the turn.

Most likely cause
  Steering gain is too low and rear actuator force is insufficient.

Recommended A/B tests
  A: increase turn_gain 0.75 → 1.05
  B: increase rear actuator max_force 8 N → 10 N
```

Recommendations must be evidence-backed and bounded. Avoid vague advice.

---

## 12. Improvement loop

Unify body and controller improvement without hiding what changed.

## 12.1 Improvement goals

Add an explicit `ImprovementGoal`:

```json
{
  "primary_metric": "target_success",
  "constraints": {
    "fall": false,
    "energy_max": 4.0,
    "sim2sim_gap_max": 0.2
  },
  "editable_domains": [
    "controller.steering",
    "controller.gait",
    "actuator.max_force"
  ]
}
```

## 12.2 Search order

Use the cheapest and most explainable sequence:

1. diagnose
2. test one bounded controller change
3. test one bounded actuator change
4. test morphology only when controller/actuator fixes are insufficient
5. run robustness
6. run sim-to-sim
7. qualify

This prevents unnecessary body mutation when the actual problem is controller configuration.

## 12.3 A/B hypothesis tests

Add:

```bash
creature-lab improve latest --goal target_success --max-tests 12
```

Each candidate should record:

- hypothesis
- edited fields
- expected effect
- measured effect
- accepted/rejected
- resulting score and constraints
- body/controller hashes

## 12.4 LLM role

The optional LLM may:

- read diagnosis
- propose bounded edits
- explain its hypothesis
- select from allowed editable domains

It must not:

- output raw real-time joint actions
- bypass schema validation
- alter tasks unless explicitly requested
- become the default controller

---

## 13. Qualification as the flagship feature

Create:

```bash
creature-lab qualify creature.json \
  --task reach_target.json \
  --controller controller.json \
  --profile target-mobile-quadruped
```

### Qualification profile contents

- required tasks
- success threshold
- fall limit
- target completion radius
- completion-time limit
- energy limit
- actuator saturation limit
- robustness trial count
- mass/friction jitter
- allowed failure rate
- maximum sim-to-sim gap
- required export checks
- optional hardware-feasibility limits

### Output

```text
QUALIFICATION: FAIL

PASS  Reach target: 4/5 trials
PASS  Median completion time: 6.2 s ≤ 8.0 s
FAIL  Actuator saturation: 41% > 20%
PASS  Robustness failure rate: 10% ≤ 15%
FAIL  PyBullet–MuJoCo score gap: 0.31 > 0.20

Primary blocker:
  Rear hip actuators saturate during turns.

Recommended next test:
  Increase rear hip max_force from 8 N to 10 N,
  then rerun the target-turn subset.
```

Qualification should combine existing capabilities rather than creating a new isolated feature.

### Built-in profiles

P0:

- `basic-locomotion`
- `target-reach`
- `push-recovery`
- `backend-portable`

P1:

- `rough-terrain-quadruped`
- `energy-conscious-locomotion`
- `hardware-feasible-prototype`

---

## 14. Reports and visual artifacts

The current HTML report system should become controller-aware.

Add:

- controller summary
- controller configuration diff
- target bearing over time
- heading error over time
- desired vs. applied joint command
- command saturation
- joint-limit proximity
- contact timing plot
- mode/state timeline
- target path and stopping radius
- controller-specific diagnosis
- qualification result

### Visual morphology and controller diff

A before/after report should show:

- changed body parts
- changed joint limits
- changed actuator properties
- changed controller fields
- changed root path
- changed score components
- changed failure modes

Use a structured diff, not only raw JSON.

### Failure Zoo

Package a small educational set:

- motorless robot
- backward phase
- excessive frequency
- insufficient torque
- unstable steering
- target overshoot
- too-short episode
- controller/body joint mismatch
- backend-overfit gait

Each failure should include:

- broken spec
- trace
- diagnosis
- corrected spec
- comparison report

This improves onboarding and regression testing at the same time.

---

## 15. Hardware feasibility

This should be P1, not P0, but it is strategically valuable.

### Add optional hardware metadata

- actuator model
- rated torque
- stall torque
- no-load speed
- mass
- gear ratio
- joint range
- voltage
- rough power estimate

### Feasibility checks

- requested torque vs. actuator limit
- requested velocity vs. actuator speed
- duty-cycle saturation
- estimated mechanical power
- total robot mass
- center-of-mass margin
- joint range violations
- unrealistic stiffness/gain settings

Keep it lightweight and transparent. This is not a full electrical CAD system.

---

## 16. Packaging, compatibility, and release trust

The repository is currently version `0.1.0`. The controller architecture should define `0.2.0`.

### P0 release work

- publish `creature-lab` to PyPI
- add `studio` and `all` convenience extras, while retaining existing extras
- add Windows CI
- add macOS CI
- preserve Linux CI
- test wheel installation on all supported OSes
- run a target-seeking smoke test from the installed wheel
- validate packaged controller presets
- generate versioned documentation
- regenerate demo GIF and zoo/controller gallery
- add migration notes for legacy `MotorSpec`
- verify project-mode editor file synchronization
- keep all tests network-free by default

### Extras proposal

```toml
studio = ["pybullet", "numpy", "viser", "trimesh", "matplotlib"]
all = ["sim", "viz", "export", "evolve", "mujoco", "llm"]
```

The exact dependency duplication can be implemented with the packaging approach that best fits `pyproject.toml`; the user-facing goal is a simple install choice.

### Documentation site

Create a proper versioned docs site, but keep it static.

Recommended navigation:

1. Start
2. Build a robot
3. Make it move
4. Reach a target
5. Diagnose a failure
6. Improve it
7. Qualify it
8. Export it
9. Reference

---

## 17. Streamlined roadmap

The current completed improvement plan should be treated as historical evidence, not an active backlog.

### Documentation cleanup

1. Keep `docs/IMPROVEMENT_PLAN_2026.md`, but mark it **Completed / Archived**.
2. Replace the active `docs/ROADMAP.md` with a short summary pointing to this consolidated plan.
3. Save this file as:

```text
docs/CONTROLLER_AND_PRODUCT_ROADMAP.md
```

4. Keep only one active priority table.
5. Move old speculative plans under `docs/archive/`.
6. Update `KNOWN_ISSUES.md` in the same PR that closes each roadmap gap.

### Do not maintain multiple competing roadmaps.

---

## 18. Implementation sequence

## Phase 0 — Roadmap and contract freeze

**Goal:** Stop feature sprawl and establish the controller artifact.

Deliver:

- approve artifact boundaries
- add architecture decision record
- define coordinate conventions
- define `ControllerSpec`
- define controller protocol
- define backward-compatibility policy
- archive completed plans
- update active roadmap

Acceptance:

- one authoritative roadmap
- generated JSON schema for `ControllerSpec`
- old creatures still validate
- old `run --controller sinusoid/cpg` behavior remains unchanged

---

## Phase 1 — Shared controller runner

**Goal:** Make all simulation entry points use one execution path.

Deliver:

- `ControllerRunner`
- controller registry
- built-in legacy sinusoid adapter
- configurable CPG
- normal `run` routed through `CreatureEnv`
- traces include requested and applied commands
- identical deterministic regression tests for legacy runs

Acceptance:

- existing baseline scores remain within declared tolerance
- CLI, editor, benchmark, and qualification use the same stepping loop
- controller metadata appears in run manifests and reports

---

## Phase 2 — Target-directed control

**Goal:** Make a target an input to behavior, not only scoring.

Deliver:

- body-frame target vector
- heading error
- target distance
- target-seeking CPG wrapper
- slowing and stopping behavior
- target-aware CLI preset
- target controls in the editor
- target-aware diagnosis

Acceptance:

- a packaged quadruped reaches targets in front-left, front, and front-right scenarios
- target distance decreases over time in successful runs
- robot stops within the configured radius
- behavior is deterministic for a fixed seed/backend
- both PyBullet and MuJoCo execute the controller

---

## Phase 3 — Balance and actuator realism

**Goal:** Make failures physically interpretable.

Deliver:

- root orientation/gravity observations
- angular velocity
- posture controller
- per-actuator force/torque/velocity/gain fields
- applied-command clipping and saturation recording
- controller safety limiter
- actuator-aware diagnosis

Acceptance:

- actuator limits affect both backends
- reports distinguish requested from applied commands
- saturation and joint-limit diagnoses are test-covered
- push-recovery preset outperforms uncontrolled gait on its packaged task

---

## Phase 4 — Editor usability and workflow integration

**Goal:** Make the complete loop usable without understanding the architecture.

Deliver:

- Movement tab
- simple/advanced controller modes
- draggable target
- forward/bearing visualization
- undo/redo
- snapshots
- hierarchy tree
- snapping
- safe destructive confirmations
- asynchronous simulation
- progress and cancellation
- separate playback and simulation

Acceptance:

- beginner can create a quadruped, select Move to target, drag a target, simulate, diagnose, and save without editing JSON
- simulation does not freeze the editor UI
- undo/redo covers body and controller changes
- project-mode writes valid `creature.json`, `task.json`, and `controller.json`

---

## Phase 5 — Diagnosis, improvement, and qualification

**Goal:** Turn controller support into the core differentiator.

Deliver:

- controller-aware Design Autopsy
- bounded A/B improvement tests
- `ImprovementGoal`
- `qualify`
- built-in qualification profiles
- controller comparison HTML
- visual body/controller diff
- Failure Zoo

Acceptance:

- failed qualification identifies a primary blocker
- recommended tests cite measured evidence
- qualification is reproducible from the run manifest
- before/after report shows exactly what changed
- all qualification profiles have calibrated baselines

---

## Phase 6 — Release `0.2.0`

**Goal:** Make the product installable, credible, and easy to understand.

Deliver:

- PyPI release
- Windows/macOS/Linux CI
- installed-wheel target-seeking smoke test
- static versioned docs
- updated README
- refreshed demo
- migration guide
- changelog
- release checklist

Acceptance:

```bash
pip install creature-lab[studio]
creature-lab build
```

must open a working editor where a user can create a robot, select a target-directed controller, run it, diagnose it, and save all three JSON artifacts.

---

## 19. Priority table

| Priority | Item | Why it is prioritized |
| --- | --- | --- |
| **P0** | `ControllerSpec` and controller protocol | Missing contract blocks every other controller improvement |
| **P0** | Shared `CreatureEnv`-based runner | Prevents duplicate execution paths and inconsistent traces |
| **P0** | Configurable CPG | Existing controller is useful but under-configured |
| **P0** | Target-seeking controller | Fixes the central mismatch between target tasks and actual behavior |
| **P0** | Posture/balance layer | Makes locomotion and recovery materially more robust |
| **P0** | Per-actuator limits and gains | Replaces hidden global assumptions with physical configuration |
| **P0** | Controller-aware diagnosis | Maintains Creature Lab's differentiation |
| **P0** | Qualification profiles | Converts many existing tools into one flagship outcome |
| **P0** | Editor Movement workflow | Makes the architecture understandable to normal users |
| **P0** | Undo/redo, snapshots, hierarchy, async runs | Resolves the largest editor usability gaps |
| **P0** | Publish `0.2.0`, docs, multi-OS CI | Adoption and trust |
| **P1** | Design Autopsy | Best-in-class failure explanation |
| **P1** | Visual body/controller diff | Git-native engineering workflow |
| **P1** | Failure Zoo | Onboarding plus regression coverage |
| **P1** | Push recovery and contact-adaptive CPG | Deeper physical capability |
| **P1** | Hardware feasibility packs | Bridges simulation design to prototypes |
| **P1** | Creature Lab GitHub Action | Automated design regression qualification |
| **P1** | Waypoint controller | Extends target behavior without becoming a world system |
| **P2** | Controller plugin interface | Ecosystem growth after core contracts stabilize |
| **P2** | External learned-policy adapters | Compatibility without becoming an RL platform |
| **P2** | MJCF import | Completes bridge functionality |
| **P2** | Portable design packs | Shareable creature/task/controller/report bundle |

---

## 20. Suggested file-level work

```text
creature_lab/
  schema/
    controller.py              # new
    control.py                 # extend observations/actions
    creature.py                # actuator capability fields
    task.py                    # success/termination/waypoints later
    manifest.py                # controller provenance

  controllers/
    base.py                    # protocol and common types
    registry.py                # named controller resolution
    legacy_sinusoid.py         # backward-compatible adapter
    cpg.py                     # make fully spec-driven
    target_seek.py             # steering wrapper
    posture.py                 # balance feedback
    hybrid.py                  # explicit composition
    scripted.py                # small physical state machine
    presets.py                 # built-in specs

  control/
    observations.py            # backend-neutral signal assembly
    transforms.py              # world/body coordinate transforms
    safety.py                  # clipping, rate limits, saturation
    runner.py                  # shared execution loop

  backends/
    pybullet_backend.py        # actuator fields and applied commands
    mujoco_backend.py          # parity implementation

  editor/
    movement_panel.py          # or current equivalent module
    controller_state.py
    history.py                 # undo/redo/snapshots
    async_runs.py

  diagnosis/
    controller_findings.py
    actuator_findings.py
    target_findings.py
    autopsy.py

  qualification/
    profiles.py
    runner.py
    result.py

  reports/
    controller_sections.py
    qualification_sections.py
    diff.py

  data/
    controllers/
      stand.json
      crawl_forward.json
      target_seek.json
      push_recovery.json
    qualification/
      basic_locomotion.json
      target_reach.json
      backend_portable.json
```

Adapt names to the current module structure rather than forcing a large directory rewrite. The important point is separation of responsibility, not maximum file count.

---

## 21. Test strategy

### Unit tests

- controller schema validation
- registry resolution
- world-to-body transforms
- heading error sign
- steering modulation
- CPG determinism
- posture correction sign
- action clipping
- actuator saturation
- rate limiting
- migration from legacy motors

### Backend contract tests

Run the same tests for PyBullet and MuJoCo:

- position command
- velocity command
- torque command
- actuator force limit
- joint limit
- target observation
- gravity/body orientation
- applied-command trace
- deterministic reset

### Scenario tests

- target directly ahead
- target to left
- target to right
- target behind
- target inside stop radius
- insufficient actuator torque
- high-friction terrain
- low-friction terrain
- push recovery
- slope
- rough terrain
- damaged limb
- backend divergence

### Product smoke tests

- fresh wheel install
- first-run editor
- legacy sinusoid run
- target-seeking run
- HTML report
- controller comparison
- qualification
- export/replay
- Windows, macOS, Linux

### Regression principle

Do not rewrite all historical baselines immediately.

Maintain:

- legacy controller baselines
- new target-controller baselines
- per-backend baselines
- declared tolerance and reason for any change

---

## 22. Definition of done

Creature Lab's controller/product roadmap is complete when a new user can:

1. install the package
2. open the build editor
3. choose a robot preset
4. choose **Move to target**
5. drag a target in the scene
6. run the simulation
7. see the robot actively steer
8. receive a controller/body-specific failure explanation
9. apply or test a bounded recommendation
10. run robustness and sim-to-sim checks
11. receive a qualification pass/fail result
12. save:
    - `creature.json`
    - `task.json`
    - `controller.json`
    - trace
    - run manifest
    - HTML report
13. reproduce the result with one command

At that point, Creature Lab is no longer merely a body editor with an oscillating gait. It becomes a coherent articulated-robot design, control, diagnosis, and qualification tool—without overlapping with Agentarium.
