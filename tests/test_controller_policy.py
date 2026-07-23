"""Tests for PolicyController (creature_lab.controllers.policy).

Trains one tiny real policy once per module (module-scoped fixture) and reuses it
across tests - PPO's rollout batch (2048 steps by default) is the practical cost
floor for any real training call, so re-training per test would make this file slow
for no extra coverage.
"""

from __future__ import annotations

import pytest

from creature_lab.scaffold import generate_quadruped
from creature_lab.schema import TaskSpec


def _task(duration: float = 0.3) -> TaskSpec:
    return TaskSpec.model_validate(
        {
            "name": "policy_test",
            "duration": duration,
            "timestep": 1 / 60,
            "terrain": {"type": "plane", "friction": 1.0},
            "reward": {"forward_distance": 1.0},
        }
    )


@pytest.fixture(scope="module")
def trained_policy_path(tmp_path_factory):
    pytest.importorskip("stable_baselines3")
    pytest.importorskip("pybullet")
    from creature_lab.rl.train import train_ppo

    creature = generate_quadruped()
    result = train_ppo(creature, _task(), timesteps=256, seed=0, eval_episodes=1)
    path = tmp_path_factory.mktemp("policy") / "policy.zip"
    result.model.save(str(path))
    return path


def test_policy_controller_covers_every_controlled_joint(trained_policy_path):
    from creature_lab.controllers.policy import PolicyController

    creature = generate_quadruped()
    task = _task()
    controller = PolicyController(creature, task, trained_policy_path)
    targets = controller(0.0, None)  # no prev_frame yet
    assert set(targets) == {m.joint for m in creature.motors}


def test_policy_controller_produces_targets_from_a_real_frame(trained_policy_path):
    pytest.importorskip("pybullet")
    from creature_lab.backends.pybullet_backend import PyBulletBackend
    from creature_lab.controllers.policy import PolicyController

    creature = generate_quadruped()
    task = _task()
    controller = PolicyController(creature, task, trained_policy_path)

    backend = PyBulletBackend()
    backend.build(creature, task)
    try:
        prev = backend.step(task.timestep)
        targets = controller(task.timestep, prev)
        assert set(targets) == {m.joint for m in creature.motors}
        assert all(isinstance(v, float) for v in targets.values())
    finally:
        backend.close()


def test_policy_controller_is_deterministic_given_the_same_frame(trained_policy_path):
    pytest.importorskip("pybullet")
    from creature_lab.backends.pybullet_backend import PyBulletBackend
    from creature_lab.controllers.policy import PolicyController

    creature = generate_quadruped()
    task = _task()
    backend = PyBulletBackend()
    backend.build(creature, task)
    try:
        frame = backend.step(task.timestep)
    finally:
        backend.close()

    a = PolicyController(creature, task, trained_policy_path)
    b = PolicyController(creature, task, trained_policy_path)
    assert a(task.timestep, frame) == b(task.timestep, frame)


def test_policy_controller_reset_clears_frame_history(trained_policy_path):
    from creature_lab.controllers.policy import PolicyController

    creature = generate_quadruped()
    controller = PolicyController(creature, _task(), trained_policy_path)
    controller.reset()
    assert controller._prev_prev_frame is None


def test_policy_controller_missing_rl_extra_gives_a_clear_error(trained_policy_path, monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "stable_baselines3":
            raise ImportError("simulated missing extra")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    from creature_lab.controllers.policy import PolicyController

    creature = generate_quadruped()
    with pytest.raises(ImportError, match="rl.*extra"):
        PolicyController(creature, _task(), trained_policy_path)
