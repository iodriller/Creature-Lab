"""Process and port helpers shared by start.py and browser_smoke.py.

Both scripts launch a `uv run creature-lab ...` subprocess and need to know whether
a local port is open. On Windows, both also need to force-kill that subprocess's
full process tree (uv -> creature-lab.exe -> the viser server): a plain terminate()
only signals the immediate child, and an orphaned grandchild keeps an exclusive lock
on files under `.venv`, breaking the next `uv sync`.

This module holds only the pieces that are identical between the two scripts. Each
script keeps its own process-launch and POSIX shutdown logic, since a foreground
viewer (start.py, single process, plain terminate/kill) and a background server
driven by a browser (browser_smoke.py, its own process group, SIGTERM/SIGKILL) shut
down differently there by design - forcing them through one shape would change
behavior, not just remove duplication.
"""

from __future__ import annotations

import socket
import subprocess
import time


def taskkill_tree(pid: int) -> None:
    """Windows only: force-kill a process and everything it spawned.

    No-op (fails silently, via ``check=False``) if the process is already gone or
    this isn't run on Windows - callers only invoke it behind a `sys.platform ==
    "win32"` check, since POSIX has no equivalent orphaning risk without a shell.
    """
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        capture_output=True,
        check=False,
    )


def port_is_open(port: int, *, host: str = "127.0.0.1", timeout: float = 0.2) -> bool:
    """True if something is listening on ``host:port`` right now."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


def wait_for_port(port: int, *, open_state: bool, timeout: float, host: str = "127.0.0.1") -> bool:
    """Poll until ``port`` becomes open/closed, instead of a fixed sleep."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if port_is_open(port, host=host) == open_state:
            return True
        time.sleep(0.1)
    return False


def free_port() -> int:
    """Ask the OS for an unused local port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
