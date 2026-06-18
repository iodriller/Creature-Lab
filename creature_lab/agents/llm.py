"""LiteLLM-backed policy (optional ``llm`` extra).

Imports litellm lazily so the rest of the agent stack works without it. The
prompt building and response parsing live in ``prompts.py`` and are tested
without any network call.
"""

from __future__ import annotations

from creature_lab.agents.loop import Observation, Proposal
from creature_lab.agents.prompts import SYSTEM_PROMPT, build_prompt, parse_proposal


class LLMPolicy:
    """Ask a model (via LiteLLM) for the next tool call."""

    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.3) -> None:
        self.model = model
        self.temperature = temperature

    def __call__(self, observation: Observation) -> Proposal:
        import litellm

        response = litellm.completion(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_prompt(observation)},
            ],
        )
        text = response.choices[0].message.content or ""
        return parse_proposal(text)
