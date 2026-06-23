"""A small PID controller utility.

Closed-loop building block: given a setpoint and a measurement each step, it returns
a control output that drives the error toward zero. Used to track a reference angle
(e.g. in torque mode), as opposed to the open-loop sinusoid/CPG generators.
"""

from __future__ import annotations


class PIDController:
    """Single-channel PID controller with anti-windup-free integral accumulation."""

    def __init__(self, kp: float, ki: float = 0.0, kd: float = 0.0) -> None:
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self._integral = 0.0
        self._prev_error: float | None = None

    def reset(self) -> None:
        self._integral = 0.0
        self._prev_error = None

    def step(self, setpoint: float, measurement: float, dt: float) -> float:
        """Return the control output for one timestep (dt > 0)."""
        if dt <= 0:
            raise ValueError("dt must be positive")
        error = setpoint - measurement
        self._integral += error * dt
        derivative = 0.0 if self._prev_error is None else (error - self._prev_error) / dt
        self._prev_error = error
        return self.kp * error + self.ki * self._integral + self.kd * derivative
