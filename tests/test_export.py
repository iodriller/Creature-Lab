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
