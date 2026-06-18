"""Tests for the agent tools, design loop, offline policy, and prompt parser."""

import pytest

from creature_lab.agents.baseline import RandomToolPolicy
from creature_lab.agents.loop import Observation, Proposal, design_loop
from creature_lab.agents.prompts import build_prompt, parse_proposal
from creature_lab.agents.tools import ToolError, apply_tool, resize_limb, set_joint_limit, set_motor
from creature_lab.schema import AgentTrace, CreatureSpec

SEED = {
    "name": "worm",
    "parts": [
        {"id": "torso", "shape": "box", "size": [0.4, 0.2, 0.1], "mass": 1.0},
        {"id": "tail", "shape": "capsule", "length": 0.3, "radius": 0.04, "mass": 0.2},
    ],
    "joints": [
        {"id": "hinge", "parent": "torso", "child": "tail", "type": "hinge", "axis": [0, 1, 0]}
    ],
    "motors": [{"joint": "hinge", "amplitude": 0.5, "frequency": 1.0, "phase": 0.0}],
}


def _seed() -> CreatureSpec:
    return CreatureSpec.model_validate(SEED)


# --- tools ---------------------------------------------------------------


def test_set_motor_updates_only_given_fields():
    out = set_motor(_seed(), joint="hinge", amplitude=1.2)
    motor = out.motors[0]
    assert motor.amplitude == 1.2
    assert motor.frequency == 1.0  # unchanged


def test_set_motor_unknown_joint_raises():
    with pytest.raises(ToolError, match="no motor"):
        set_motor(_seed(), joint="nope", amplitude=1.0)


def test_resize_limb_changes_length():
    out = resize_limb(_seed(), part="tail", length=0.5)
    assert out.parts[1].length == 0.5


def test_resize_limb_rejects_non_length_shape():
    with pytest.raises(ToolError, match="no length"):
        resize_limb(_seed(), part="torso", length=0.5)


def test_set_joint_limit_applies_and_validates():
    out = set_joint_limit(_seed(), joint="hinge", lower=-1.0, upper=1.0)
    assert out.joints[0].limit == (-1.0, 1.0)
    # invalid (min >= max) is rejected by re-validation
    with pytest.raises(ToolError):
        set_joint_limit(_seed(), joint="hinge", lower=1.0, upper=-1.0)


def test_apply_tool_unknown_and_bad_args():
    with pytest.raises(ToolError, match="unknown tool"):
        apply_tool(_seed(), "fly", {})
    with pytest.raises(ToolError, match="bad arguments"):
        apply_tool(_seed(), "set_motor", {"nope": 1})


# --- loop ----------------------------------------------------------------


def test_design_loop_keeps_best_and_traces():
    # Fitness rewards larger amplitude; a fixed policy keeps raising it.
    def evaluate(creature: CreatureSpec) -> float:
        return sum(m.amplitude for m in creature.motors)

    def policy(obs: Observation) -> Proposal:
        amp = obs.creature.motors[0].amplitude
        return Proposal("set_motor", {"joint": "hinge", "amplitude": amp + 0.1}, "grow")

    result = design_loop(_seed(), evaluate, policy, attempts=3, goal="bigger")
    assert result.best_score == pytest.approx(0.8)  # 0.5 + 3 * 0.1
    assert isinstance(result.trace, AgentTrace)
    assert [s.accepted for s in result.trace.steps] == [True, True, True, True]


def test_design_loop_records_invalid_proposals():
    def policy(obs: Observation) -> Proposal:
        return Proposal("set_motor", {"joint": "ghost", "amplitude": 1.0}, "bad")

    result = design_loop(_seed(), lambda c: 0.0, policy, attempts=2)
    invalid = [s for s in result.trace.steps if not s.valid]
    assert len(invalid) == 2
    assert result.best == _seed()  # nothing valid was accepted


def test_offline_policy_proposes_valid_tool_calls():
    policy = RandomToolPolicy(seed=0)
    creature = _seed()
    for _ in range(25):
        proposal = policy(Observation(creature, 0.0, 1))
        # Every proposal applies cleanly through the validated tool layer.
        apply_tool(creature, proposal.tool, proposal.args)


def test_offline_policy_is_deterministic():
    a = RandomToolPolicy(seed=7)(Observation(_seed(), 0.0, 1))
    b = RandomToolPolicy(seed=7)(Observation(_seed(), 0.0, 1))
    assert (a.tool, a.args) == (b.tool, b.args)


# --- prompt / parsing ----------------------------------------------------


def test_build_prompt_mentions_tools_and_goal():
    prompt = build_prompt(Observation(_seed(), 0.0, 1, goal="crawl far"))
    assert "crawl far" in prompt
    assert "set_motor" in prompt and "resize_limb" in prompt


def test_parse_proposal_extracts_json_amid_prose():
    text = (
        "Sure! ```json\n"
        '{"tool": "set_motor", "args": {"joint": "hinge", "amplitude": 1.0}, "note": "x"}\n'
        "```"
    )
    proposal = parse_proposal(text)
    assert proposal.tool == "set_motor"
    assert proposal.args == {"joint": "hinge", "amplitude": 1.0}


@pytest.mark.parametrize("text", ["no json here", '{"args": {}}', "{bad json}"])
def test_parse_proposal_rejects_bad_responses(text):
    with pytest.raises(ValueError):
        parse_proposal(text)


def test_offline_policy_round_trips_through_loop_deterministically():
    def evaluate(creature: CreatureSpec) -> float:
        return sum(m.frequency for m in creature.motors)

    first = design_loop(_seed(), evaluate, RandomToolPolicy(3), attempts=10)
    second = design_loop(_seed(), evaluate, RandomToolPolicy(3), attempts=10)
    assert first.best == second.best
    assert [s.action for s in first.trace.steps] == [s.action for s in second.trace.steps]
