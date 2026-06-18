"""Agent design loop: validated tools, policies, and the hill-climbing loop.

Agents act only through validated tools that return a fresh, validated
``CreatureSpec`` — they never touch a backend or unvalidated state.
"""
