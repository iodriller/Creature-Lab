"""Optional reinforcement-learning support (Grand Plan Phase 5, Tier 3).

Everything here needs the ``rl`` extra (``uv sync --extra rl`` - gymnasium +
Stable-Baselines3 + torch) and is imported lazily by callers (``cli.py``'s ``train``
command, ``creature_lab.controllers.policy``), never at package import time, so the
rest of Creature Lab works without it installed.
"""

from __future__ import annotations
