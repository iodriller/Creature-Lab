# Creature Lab — Final Priority Roadmap

## Product Direction

**Position Creature Lab as:**

> A local robot-creature workbench where users design a body, simulate it, understand why it failed, improve it, and export a reproducible result—without writing URDF or simulator code.

The next phase should prioritize **adoption, usability, and trust**, not more simulation surface area.

---

## P0 — Adoption and Core Usability

### 1. Release and Distribution

- Publish **Creature Lab 0.2.0** to PyPI.
- Add automated GitHub releases with wheel and source artifacts.
- Move all current “Unreleased” improvements into the release changelog.
- Add a robotics-specific subtitle to avoid the existing “Creature Lab” name collision.
- Recommended public name: **Creature Lab — Robot Morphology Workbench**.

**Success criteria**

```bash
pip install creature-lab
creature-lab build
```

works from a clean environment without cloning the repository.

### 2. Guided Beginner Mode

Keep the current editor as **Advanced Mode**, but add a simplified first-run path:

1. Choose a creature.
2. Choose a goal: walk, climb, reach target, or survive a push.
3. Adjust a few understandable properties.
4. Click **Test Creature**.
5. Show the result, failure explanation, and recommended next edit.
6. Let the user apply the recommendation.

Hide file paths, individual joint phases, backend selection, robustness settings, and advanced physics parameters until requested.

**Success criteria**

A new user can create and test a modified creature in under five minutes without reading the documentation.

### 3. Responsive Simulation Workflow

Move simulation, evolution, and robustness sweeps out of the editor UI thread.

Add:

- Progress indicators
- Trial count and elapsed status
- Cancellation
- Partial results
- Current-best score during evolution
- Clear completion and failure states

**Success criteria**

The editor remains responsive during a 50-trial robustness run or evolution job.

### 4. Fix the Offline `ask` Experience

The current offline mode performs random validated edits but appears to understand natural-language goals.

Choose one:

- Rename it to **offline search** or **suggest heuristic edit**, or
- Implement rule-based intent mapping for goals such as stability, distance, speed, and energy.

Reserve `ask` for modes that genuinely interpret the user's instruction.

**Success criteria**

The command name and interface accurately describe what the offline system does.

### 5. True Gymnasium Compatibility

Convert `CreatureEnv` into a standard Gymnasium environment:

- Subclass `gymnasium.Env`
- Use `spaces.Box`
- Implement the modern `reset()` and `step()` signatures
- Properly apply seeds
- Return separate `terminated` and `truncated` values
- Add `check_env` tests
- Add one Stable-Baselines3 example

**Success criteria**

A standard RL trainer can use Creature Lab without a custom adapter.

---

## P1 — Complete the Design–Diagnose–Improve Loop

### 1. Apply Recommended Fix

Add an **Apply Suggested Edit** action after diagnosis.

The system should:

1. Identify the strongest failure pattern.
2. Propose a validated change.
3. Show the before/after parameter difference.
4. Let the user accept, reject, or simulate it.

### 2. Undo, Redo, and Checkpoints

Add:

- Undo and redo
- Named design checkpoints
- Restore previous design
- Automatic checkpoint before simulation or evolution
- Before/after comparison

### 3. Integrated Run History

Inside the editor, show:

- Recent runs
- Score and task
- Controller and backend
- Robustness status
- Open replay
- Compare with current design
- Restore creature specification

### 4. Better Task Editing

Expose the existing task capabilities visually:

- Terrain type and parameters
- Target placement
- Reward weights
- Damage event
- Push event
- Duration and friction

Use presets first and place raw numeric controls under an advanced section.

### 5. Parallel Evaluation

Parallelize independent:

- Evolution candidates
- Robustness trials
- Zoo benchmarks
- Cross-backend comparisons

Add a configurable worker limit to avoid overwhelming local machines.

### 6. Terrain-Aware Diagnosis

Correct diagnosis signals for local terrain elevation so healthy slope or step locomotion is not falsely classified as vertical instability.

Also warn users when open-ended locomotion approaches the finite terrain boundary.

---

## P2 — Ecosystem and Research Growth

### 1. Documentation Site

Publish versioned documentation with three clear entry paths:

- **I want to design a creature**
- **I want to run experiments**
- **I want to train a controller**

### 2. Canonical Tutorials

Create three reproducible tutorials:

1. Build and stabilize a quadruped.
2. Evolve a creature for slope climbing.
3. Train a controller through Gymnasium.

Each tutorial should produce a run, report, replay, and exportable creature.

### 3. Community Readiness

Add:

- Issue templates
- Feature request template
- GitHub Discussions
- Concrete `good first issue` tickets
- Contributor guide for adding creatures, tasks, diagnosis rules, and controllers

### 4. Maintainability Cleanup

- Split the large CLI into command modules.
- Add structured logging and a debug mode.
- Preserve technical tracebacks while showing friendly user errors.
- Use one source of truth for the package version.
- Expand CI to Windows and multiple supported Python versions.
- Add static type checking.

### 5. Carefully Expand the Physical Model

Only after the core workflow is polished, consider:

- Multiple timed damage and impulse events
- Per-part materials and friction
- Sensors
- Additional joint types
- Mesh visuals with primitive collision bodies
- First-class controller configuration files

Do not add these unless they support a documented user scenario.

---

## Recommended Execution Order

### Milestone 1 — Install and Understand

1. Publish 0.2.0.
2. Add the robotics subtitle and improved homepage messaging.
3. Build Guided Mode.
4. Fix offline `ask` semantics.

### Milestone 2 — Run Without Friction

1. Add background jobs, progress, and cancellation.
2. Add run history and checkpoints.
3. Add apply-recommendation workflow.
4. Improve task editing.

### Milestone 3 — Research Compatibility

1. Implement true Gymnasium support.
2. Add parallel evaluation.
3. Fix terrain-aware diagnosis.
4. Publish the RL tutorial.

### Milestone 4 — Grow the Ecosystem

1. Launch versioned docs.
2. Publish canonical tutorials.
3. Improve community contribution paths.
4. Refactor CLI and expand CI.

---

## Features to Avoid

Keep Creature Lab distinct from Agentarium and large simulation platforms.

Do **not** prioritize:

- Generic agent orchestration
- Multi-agent arenas
- Hosted dashboards
- Cloud execution
- Public leaderboards
- Real-time LLM motor control
- GPU-scale RL infrastructure
- Natural-language task or challenge generation

Creature Lab should remain a focused, local, reproducible **physical creature design workbench**.

---

## Final Priority Summary

| Priority | Goal |
|---|---|
| **P0** | Make Creature Lab easy to install, understand, and operate |
| **P1** | Make the design–diagnose–improve loop seamless |
| **P2** | Grow research compatibility, documentation, and community adoption |

The project already has enough technical capability. Its highest-value next step is to make the existing capability feel like one clear, approachable product.
