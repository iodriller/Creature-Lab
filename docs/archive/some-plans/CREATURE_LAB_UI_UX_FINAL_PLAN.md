# Creature Lab — Final UI/UX Streamlining Plan

## Product Goal

Transform Creature Lab from a powerful Viser control panel into a guided **creature-design workbench**:

> Choose a creature → design its body → design its movement → test it → understand failures → improve it → export the result.

Keep Creature Lab focused on one creature and one physical experiment at a time. Do not turn it into an Agentarium-style agent platform, cloud dashboard, or multi-user studio.

---

## Current Strengths to Preserve

- One-command local launch and browser-based workflow.
- Portable `CreatureSpec`, `TaskSpec`, and `EpisodeTrace` JSON.
- Live 3D preview and selectable creature parts.
- PyBullet and MuJoCo support.
- Built-in validation, diagnosis, robustness testing, evolution, reports, and export.
- Pure `EditorSession` logic separated from Viser and physics.
- Local-first, offline-friendly, backend-agnostic design.

---

## Core UX Problems

1. Too many equal-priority folders and controls in one narrow panel.
2. File paths and technical formats appear before creature creation.
3. Basic and advanced controls are mixed together.
4. Body slider changes rebuild too much UI and scene state.
5. Simulation and playback block interaction.
6. No undo, redo, snapshots, or safe recovery.
7. Delete, template replacement, mirroring, and reload actions are risky.
8. Motor amplitude, frequency, and phase are difficult for beginners to understand.
9. Metrics and diagnosis are presented mainly as Markdown text.
10. No integrated run history, comparison, or guided next action.
11. The editor does not visually teach the intended design–test–improve workflow.

---

# Priority Roadmap

## P0 — Workbench Foundation

**Objective:** Deliver the largest usability improvement without replacing Viser.

### P0.1 Replace the Vertical Folder Stack

Create three primary workflow tabs:

1. **Design**
   - Template and creature identity.
   - Global body proportions.
   - Part hierarchy.
   - Selected-part inspector.
   - Add, duplicate, mirror, and delete actions.

2. **Motion**
   - Gait preset.
   - Global speed and stride.
   - Motor groups and symmetry.
   - Motion preview.
   - Advanced individual motor controls.

3. **Test**
   - Task and terrain.
   - Simulation controls.
   - Playback.
   - Results and diagnosis.
   - Robustness.
   - Run history and comparison.

Move Open, Save, Import, Export, and project synchronization into a top **Project** menu.

### P0.2 Add Basic and Advanced Modes

Default mode should expose only the controls needed for a successful first experiment.

**Basic**
- Template.
- Important body proportions.
- Gait.
- Speed and stride.
- Task.
- Simulate.

**Advanced**
- Exact dimensions and mass.
- Individual joints and motors.
- Raw phase values.
- Joint limits.
- File formats.
- Backend selection.
- Robustness perturbation settings.

### P0.3 Add Undo, Redo, Reset, and Snapshots

Implement snapshot-based history in `EditorSession`.

Required actions:

- Undo and redo.
- Reset selected value.
- Reset selected part.
- Reset to current template.
- Save named snapshot.
- Restore last successful simulation design.
- Indicate unsaved changes.

Each structural change must create one atomic history entry.

### P0.4 Protect Destructive Actions

Require clear confirmations for:

- Template replacement.
- Part deletion.
- Recursive child deletion.
- Project reload.
- Overwriting files.
- Resetting a design.

Show the exact impact, such as:

> Delete Front Left Leg and its two child parts?

Project file conflicts must offer:

- Reload disk version.
- Keep editor version.
- Save editor version as a copy.
- Compare changes.

### P0.5 Make Preview Updates Incremental

Replace full scene recreation for normal edits with:

- `update_part_geometry(part_id)`
- `update_part_transform(part_id)`
- `update_part_material(part_id)`
- `update_selection(previous_id, current_id)`
- `rebuild_topology()` only for templates, add, delete, or major structural changes.

Debounce body sliders and preserve:

- Camera position.
- Current selection.
- Open tab.
- Playback state.
- Control focus.

### P0.6 Make Simulation Asynchronous

Add an `EditorJobManager` for simulation, robustness, evolution, and export.

Job states:

```text
queued → running → completed
                 → cancelled
                 → failed
```

Show:

- Current stage.
- Progress indicator.
- Elapsed time.
- Cancel action.
- Clear error state.
- Completion notification.

### P0.7 Separate Simulation from Playback

Simulation should produce a trace without immediately blocking the UI with replay.

Add:

- Play and pause.
- Timeline scrubber.
- Frame stepping.
- Playback speed.
- Loop toggle.
- Return to start pose.
- Camera follow toggle.
- Inspect parts during replay.

### P0.8 Establish a Product Visual System

Configure Viser with a consistent Creature Lab theme:

- Dark default appearance.
- Branded titlebar.
- Consistent spacing and typography.
- One primary action color.
- Clear success, warning, and error states.
- Larger primary simulation action.
- Icons paired with labels.
- Persistent project and save status.

---

## P1 — Guided Creature Design

**Objective:** Make creation understandable to non-robotics users.

### P1.1 Add First-Run Onboarding

Open with two guided choices.

**Choose a creature**
- Quadruped — easiest starting point.
- Hexapod — more stable, more complex.
- Worm — simple wave locomotion.
- Humanoid — advanced balance challenge.
- Open existing design.

**Choose a goal**
- Move forward.
- Reach a target.
- Climb a slope.
- Step over obstacles.
- Cross gaps.

Automatically choose a reasonable starting gait and task while still generating ordinary Creature Lab JSON.

### P1.2 Use Human-Readable Names

Display friendly labels while preserving stable IDs internally.

Examples:

- `leg_0l` → Front left leg.
- `hip_0l` → Front left hip.
- `limb_3` → New limb 3.

Allow optional renaming.

### P1.3 Add a Part Hierarchy

Replace the flat part dropdown with a tree:

```text
Torso
├── Front left hip
│   └── Front left leg
├── Front right hip
│   └── Front right leg
└── Rear assembly
```

Selecting a tree item must highlight the matching 3D part and vice versa.

### P1.4 Redesign the Part Inspector

Organize the selected part into:

**Transform**
- Position.
- Joint anchor.
- Joint axis.
- Focus camera.

**Shape**
- Shape type.
- Dimensions.
- Color.

**Physics**
- Mass.
- Joint limits.
- Advanced collision properties.

**Structure**
- Add child.
- Duplicate.
- Mirror.
- Delete.

### P1.5 Improve Limb Creation

Replace instant default creation with a guided form:

- Parent part.
- Shape.
- Length and radius.
- Joint type.
- Joint axis.
- Motor enabled.
- Add mirrored counterpart.

Show a ghost preview before committing.

Retain a **Quick Add Limb** action for fast experimentation.

### P1.6 Create a Visual Gait Composer

Default motion controls:

- Gait preset.
- Speed.
- Stride.
- Coordination.
- Left/right symmetry.
- Front/rear phase offset.

Advanced controls:

- Individual joint motor.
- Amplitude.
- Frequency.
- Phase.
- Motor type.

Add a phase-circle or waveform visualization showing which limbs move together.

### P1.7 Add Lightweight Motion Preview

Before full physics simulation:

- Animate joint targets kinematically.
- Preview two gait cycles.
- Support slow motion.
- Highlight active joints.
- Warn about obvious self-intersection or extreme joint motion.

### P1.8 Make Tasks Visual

For each task show:

- Terrain preview.
- Movement direction.
- Target marker.
- Relevant task parameters only.
- Difficulty indicator.
- Recommended creature types.
- Reset task action.

Do not expose slope, step, gap, or roughness settings when they are irrelevant.

---

## P2 — Test, Understand, and Improve

**Objective:** Make Creature Lab's diagnosis and experimentation capabilities its strongest differentiator.

### P2.1 Replace Text Metrics with a Scorecard

Show an immediate visual summary:

- Final score.
- Forward distance.
- Target progress.
- Fell or survived.
- Stability.
- Duration.
- Robustness confidence.

Add charts for:

- Root path.
- Center-of-mass height.
- Forward displacement.
- Joint motion or energy.
- Score breakdown.

### P2.2 Make Diagnosis Actionable

Each diagnosis card should contain:

- What happened.
- Why it probably happened.
- Evidence from the trace.
- Recommended edits.
- Severity.

Where possible, provide actions:

- Preview proposed fix.
- Apply fix.
- Simulate again.
- Undo.

Examples:

- Lower torso by 10%.
- Widen stance by 10%.
- Reduce stride.
- Reduce motor amplitude.
- Adjust left/right phase.

Keep these rule-based and deterministic. The optional LLM may explain or propose edits, but it should not control the simulation.

### P2.3 Add Integrated Run History

Store recent editor runs with:

- Run name.
- Score.
- Distance.
- Fall state.
- Backend.
- Timestamp.
- Creature snapshot.
- Task snapshot.

Actions:

- Replay.
- Compare.
- Restore design.
- Export report.
- Mark as best.
- Delete.

### P2.4 Add Before/After Comparison

Compare two runs with:

- Score delta.
- Distance delta.
- Stability delta.
- Root-path overlays.
- Signal charts.
- Changed body parameters.
- Changed motor parameters.
- Diagnosis differences.

Reuse the existing HTML comparison and report infrastructure.

### P2.5 Simplify Robustness Testing

Default choices:

- Quick — 5 trials.
- Standard — 10 trials.
- Thorough — 25 trials.

Summarize the result in plain language:

> Moderately robust — succeeded in 8 of 10 trials, with scores varying by approximately 14%.

Keep exact mass and friction jitter under Advanced settings.

### P2.6 Integrate Reports and Export

From the Test tab provide:

- Open run report.
- Export self-contained HTML.
- Export GIF or MP4.
- Save CreatureSpec JSON.
- Export URDF.
- Export MJCF.
- Copy reproducibility command.

### P2.7 Add Keyboard and Command-Palette Actions

Recommended shortcuts:

- `1` — Design.
- `2` — Motion.
- `3` — Test.
- `Space` — Play or pause.
- `R` — Simulate.
- `F` — Focus selected part.
- `Ctrl/Cmd+Z` — Undo.
- `Ctrl/Cmd+Shift+Z` — Redo.
- `Ctrl/Cmd+S` — Save snapshot.
- `Delete` — Delete selected part with confirmation.

---

# Recommended Editor Architecture

```text
creature_lab/editor/
├── live.py                 # Server lifecycle and connections
├── session.py              # Validated creature/task state
├── history.py              # Undo, redo, reset, snapshots
├── jobs.py                 # Simulation, robustness, export jobs
├── preview.py              # Incremental scene updates
├── playback.py             # Trace playback and timeline
├── shell.py                # Theme, titlebar, tabs, commands
├── project_controls.py     # Open, save, import, export, sync
├── design_controls.py      # Body and structural editing
├── motion_controls.py      # Gaits and motor editing
├── task_controls.py        # Task and terrain
├── result_controls.py      # Metrics, diagnosis, history
└── presets.py
```

Add an `EditorViewModel` exposing UI-ready state:

```text
can_undo
can_redo
is_dirty
active_job
selected_part_label
validation_summary
latest_run
best_run
recommended_actions
```

Keep physics, schemas, diagnosis, reporting, and backend adapters independent from the UI.

---

# Delivery Sequence

## Release 1 — Creature Lab Workbench

- Design, Motion, and Test tabs.
- Project menu.
- Basic and Advanced modes.
- Branded theme.
- Undo, redo, and reset.
- Safe destructive actions.
- Incremental scene updates.
- Async simulation.
- Playback controls.
- Visual scorecard.

## Release 2 — Guided Creature Design

- First-run onboarding.
- Friendly part names.
- Part hierarchy.
- Improved part inspector.
- Guided limb creation.
- Visual gait composer.
- Motion preview.
- Visual tasks and terrain.

## Release 3 — Experiment and Improve

- Actionable diagnosis.
- Run history.
- Run restoration.
- Before/after comparison.
- Simplified robustness.
- Integrated reports and exports.
- Command palette and shortcuts.

---

# UX Acceptance Criteria

The redesign is successful when:

1. A new user can launch and simulate a creature in under 60 seconds.
2. No raw file path is required for the first run.
3. The default view shows no more than 8–10 editable controls at once.
4. The main workflow requires no long vertical panel scrolling.
5. Every destructive change is confirmed or immediately undoable.
6. Slider changes update smoothly without rebuilding unrelated UI.
7. Simulation visibly starts within 200 ms.
8. Long operations can be cancelled.
9. Users can pause, scrub, replay, and inspect a trace.
10. Results are understandable without reading raw Markdown.
11. Diagnosis explains both the failure and the next recommended edit.
12. A diagnosis-driven edit can be previewed and applied in two clicks.
13. Recent runs can be replayed, restored, and compared inside the editor.
14. Advanced JSON, URDF, MJCF, backend, and robustness controls remain available without dominating onboarding.
15. All editor mutations remain validated and produce portable Creature Lab specs.

---

# Non-Goals

Do not prioritize:

- A separate React frontend.
- Cloud accounts or hosted simulations.
- Multi-user collaboration.
- Agent personas or memory systems.
- Real-time LLM torque control.
- Leaderboards.
- Generic workflow orchestration.
- New simulation backends before the current workflow is polished.

---

# Final Direction

Creature Lab should feel like a focused physical-design application, not a collection of simulator controls.

The final experience should communicate one clear loop:

> **Design → Move → Test → Understand → Improve**

Keep Viser for the first major redesign, use its richer layout and interaction capabilities, and invest engineering effort in workflow clarity, safe editing, responsiveness, playback, and actionable diagnosis before adding more features.
