"""Shared schema primitives.

These types are backend-neutral and must not import any physics engine.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

#: Right-handed 3D vector ``(x, y, z)``.
Vector3 = tuple[float, float, float]

#: RGB color with each channel in ``[0, 1]``.
ColorRGB = tuple[float, float, float]

#: Inclusive joint limit ``(min, max)`` in radians.
JointLimit = tuple[float, float]

#: Quaternion in ``(w, x, y, z)`` order (scalar first).
#:
#: Note: PyBullet uses ``(x, y, z, w)`` (scalar last). Backend adapters must
#: convert at the boundary; schema and traces always use scalar-first.
Quaternion = tuple[float, float, float, float]


class StrictModel(BaseModel):
    """Base model that rejects unknown fields."""

    # JSON numbers such as ``1e309`` are decoded as infinity by Python's JSON
    # parser.  Physics, step counts, hashes, and reports all require finite values,
    # so reject NaN/Infinity once at the durable-artifact boundary rather than
    # letting them fail later with backend-specific errors.
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
