"""Tests for trace rendering and GIF/MP4 export."""

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("imageio")

from creature_lab.viewers.video_exporter import write_animation  # noqa: E402


def _frames(count: int = 4):
    return [np.zeros((48, 64, 3), dtype=np.uint8) for _ in range(count)]


def test_write_gif(tmp_path):
    out = tmp_path / "clip.gif"
    result = write_animation(_frames(), out, fps=10)
    assert result == out
    assert out.exists() and out.stat().st_size > 0


def test_write_mp4(tmp_path):
    pytest.importorskip("imageio_ffmpeg")
    out = tmp_path / "clip.mp4"
    write_animation(_frames(), out, fps=10)
    assert out.exists() and out.stat().st_size > 0


def test_write_creates_parent_dirs(tmp_path):
    out = tmp_path / "nested" / "dir" / "clip.gif"
    write_animation(_frames(), out, fps=10)
    assert out.exists()


def test_empty_frames_raises(tmp_path):
    with pytest.raises(ValueError, match="no frames"):
        write_animation([], tmp_path / "clip.gif")


def test_render_trace_produces_rgb_frames():
    pytest.importorskip("pybullet")
    from creature_lab.backends.pybullet_backend import PyBulletBackend, render_trace
    from creature_lab.controllers.sinusoid import sinusoid_targets
    from creature_lab.schema import CreatureSpec, EpisodeTrace, TaskSpec

    creature = CreatureSpec.model_validate(
        {
            "name": "worm",
            "parts": [
                {"id": "torso", "shape": "box", "size": [0.4, 0.2, 0.1], "mass": 1.0},
                {"id": "tail", "shape": "capsule", "length": 0.3, "radius": 0.04, "mass": 0.2},
            ],
            "joints": [
                {"id": "j", "parent": "torso", "child": "tail", "type": "hinge", "axis": [0, 1, 0]}
            ],
            "motors": [{"joint": "j", "amplitude": 0.5, "frequency": 1.0}],
        }
    )
    task = TaskSpec.model_validate({"name": "t", "duration": 0.1, "timestep": 1 / 60})

    backend = PyBulletBackend()
    try:
        backend.build(creature, task)
        frames = []
        for step in range(task.step_count()):
            backend.apply_motor_targets(sinusoid_targets(creature, step * task.timestep))
            frames.append(backend.step(task.timestep))
    finally:
        backend.close()

    trace = EpisodeTrace(
        run_id="r1",
        creature_name=creature.name,
        task_name=task.name,
        backend="pybullet",
        score=frames[-1].score,
        frames=frames,
    )

    images = render_trace(creature, trace, width=64, height=48)
    assert len(images) == len(trace.frames)
    assert images[0].shape == (48, 64, 3)

    # Odd dimensions are rounded up to even so MP4 (libx264) stays valid.
    odd = render_trace(creature, trace, width=65, height=49)
    assert odd[0].shape == (50, 66, 3)


def test_render_is_driven_by_recorded_part_poses_not_joint_angles():
    # Rendering reads frame.parts directly (faithful to the trace), so a creature
    # with NO joints/motors and a hand-posed trace still renders correctly.
    pytest.importorskip("pybullet")
    from creature_lab.backends.pybullet_backend import render_trace
    from creature_lab.schema import CreatureSpec, EpisodeTrace

    creature = CreatureSpec.model_validate(
        {
            "name": "free",
            "parts": [
                {"id": "a", "shape": "box", "size": [0.3, 0.3, 0.3], "mass": 1.0},
                {"id": "b", "shape": "sphere", "radius": 0.15, "mass": 0.5},
            ],
            # A fixed joint would rigidly fix b to a under FK; the trace below poses them
            # independently, so a faithful (parts-driven) render must ignore the joint.
            "joints": [{"id": "j", "parent": "a", "child": "b", "type": "fixed"}],
        }
    )
    frames = [
        {
            "t": t,
            "parts": {
                "a": {"position": [t, 0.0, 1.0]},
                "b": {"position": [t, 0.5, 1.0]},
            },
            "score": 0.0,
        }
        for t in (0.1, 0.2, 0.3)
    ]
    trace = EpisodeTrace(
        run_id="r2",
        creature_name="free",
        task_name="t",
        backend="pybullet",
        score=0.0,
        frames=frames,
    )
    images = render_trace(creature, trace, width=64, height=48)
    assert len(images) == 3
    assert images[0].shape == (48, 64, 3)
    assert images[1].any()  # the creature is in view and drawn


def test_render_trace_draws_actual_terrain_not_a_flat_floor():
    # Regression test: a replay of a non-flat-terrain run must show that terrain, not a
    # flat floor the creature appears to float above or sink into.
    pytest.importorskip("pybullet")
    from creature_lab.backends.pybullet_backend import render_trace
    from creature_lab.schema import CreatureSpec, EpisodeTrace, TaskSpec

    creature = CreatureSpec.model_validate(
        {
            "name": "still",
            "parts": [{"id": "a", "shape": "box", "size": [0.3, 0.3, 0.3], "mass": 1.0}],
        }
    )
    trace = EpisodeTrace.model_validate(
        {
            "run_id": "r",
            "creature_name": "still",
            "task_name": "t",
            "backend": "pybullet",
            "score": 0.0,
            "frames": [{"t": 0.0, "parts": {"a": {"position": [0.0, 0.0, 3.0]}}, "score": 0.0}],
        }
    )
    # A camera looking straight down captures mostly ground, not the small creature,
    # so a terrain-shape difference dominates the image.
    kwargs = dict(width=200, height=200, camera_distance=8.0, camera_pitch=-89, camera_yaw=0)

    flat_task = TaskSpec.model_validate({"name": "t", "duration": 1.0})
    gaps_task = TaskSpec.model_validate(
        {
            "name": "t",
            "duration": 1.0,
            "terrain": {"type": "gaps", "gap_width": 0.4, "gap_period": 0.8},
        }
    )
    flat_images = render_trace(creature, trace, task=flat_task, **kwargs)
    gaps_images = render_trace(creature, trace, task=gaps_task, **kwargs)

    diff = np.abs(flat_images[0].astype(int) - gaps_images[0].astype(int))
    assert (diff.sum(axis=-1) > 10).mean() > 0.5  # most pixels differ

    # is_flat(terrain) plane still renders identically regardless of the `task` param.
    default_images = render_trace(creature, trace, task=None, **kwargs)
    assert np.array_equal(flat_images[0], default_images[0])


def test_render_trace_flat_terrain_matches_no_task_given():
    # A TerrainSpec() (plane) explicitly passed must render identically to task=None,
    # since both take the "flat plane" branch.
    pytest.importorskip("pybullet")
    from creature_lab.backends.pybullet_backend import render_trace
    from creature_lab.schema import CreatureSpec, EpisodeTrace, TaskSpec

    creature = CreatureSpec.model_validate(
        {
            "name": "still",
            "parts": [{"id": "a", "shape": "box", "size": [0.3, 0.3, 0.3], "mass": 1.0}],
        }
    )
    trace = EpisodeTrace.model_validate(
        {
            "run_id": "r",
            "creature_name": "still",
            "task_name": "t",
            "backend": "pybullet",
            "score": 0.0,
            "frames": [{"t": 0.0, "parts": {"a": {"position": [0.0, 0.0, 1.0]}}, "score": 0.0}],
        }
    )
    flat_task = TaskSpec.model_validate({"name": "t", "duration": 1.0})

    with_task = render_trace(creature, trace, task=flat_task, width=64, height=48)
    without_task = render_trace(creature, trace, task=None, width=64, height=48)
    assert np.array_equal(with_task[0], without_task[0])
