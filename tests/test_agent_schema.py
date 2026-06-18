"""Tests for the AgentTrace / AgentStep schema."""

import pytest
from pydantic import ValidationError

from creature_lab.schema import AgentStep, AgentTrace


def test_agent_trace_round_trips():
    trace = AgentTrace(
        creature_name="tripod",
        task_name="crawl_forward",
        goal="crawl farther",
        best_score=1.2,
        steps=[
            AgentStep(attempt=0, action="seed", valid=True, score=0.1, accepted=True),
            AgentStep(attempt=1, action="set_motor({})", valid=True, score=1.2, accepted=True),
            AgentStep(attempt=2, action="set_motor({})", valid=False, note="no motor"),
        ],
    )
    assert AgentTrace.model_validate_json(trace.model_dump_json()) == trace


def test_agent_trace_requires_at_least_one_step():
    with pytest.raises(ValidationError):
        AgentTrace(creature_name="c", task_name="t", best_score=0.0, steps=[])


def test_agent_step_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        AgentStep(attempt=0, action="seed", valid=True, bogus=1)
