#!/usr/bin/env python3
"""Bootstrap and launch Creature Lab from a fresh checkout."""

from __future__ import annotations

import argparse
import shutil
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORT = 8080


def check_python() -> None:
    """Fail early with a clear message when Python is too old."""
    if sys.version_info < (3, 11):  # noqa: UP036 - friendly launcher error for old Python.
        version = ".".join(str(part) for part in sys.version_info[:3])
        raise SystemExit(
            f"Creature Lab needs Python 3.11 or newer. This launcher is using Python {version}."
        )


def command_text(command: list[str]) -> str:
    """Return a readable command line for logs."""
    return " ".join(str(part) for part in command)


def print_header(title: str) -> None:
    print(f"\n== {title} ==", flush=True)


def run_step(
    title: str,
    command: list[str],
    *,
    dry_run: bool = False,
    failure_hint: str,
) -> None:
    """Run one setup/launch step with readable context and failure hints."""
    print_header(title)
    print(f"$ {command_text(command)}", flush=True)
    if dry_run:
        return

    try:
        subprocess.run(command, cwd=ROOT, check=True)
    except FileNotFoundError as exc:
        print(f"\nCould not find executable: {command[0]}", file=sys.stderr)
        print(failure_hint, file=sys.stderr)
        raise SystemExit(127) from exc
    except subprocess.CalledProcessError as exc:
        print(f"\nThe '{title}' step failed with exit code {exc.returncode}.", file=sys.stderr)
        print(failure_hint, file=sys.stderr)
        raise SystemExit(exc.returncode) from exc


def uv_command(explicit: str | None) -> list[str]:
    """Resolve uv as either a PATH executable or a Python module."""
    if explicit:
        return [explicit]

    uv_path = shutil.which("uv")
    if uv_path:
        return [uv_path]

    probe = subprocess.run(
        [sys.executable, "-m", "uv", "--version"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if probe.returncode == 0:
        return [sys.executable, "-m", "uv"]

    raise SystemExit(
        "uv is required to install and run Creature Lab.\n\n"
        "Install uv, then rerun this script:\n"
        "  Windows PowerShell: irm https://astral.sh/uv/install.ps1 | iex\n"
        "  macOS/Linux:       curl -LsSf https://astral.sh/uv/install.sh | sh\n"
        "  pip fallback:      python -m pip install uv"
    )


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def choose_port(port: int, *, explicit: bool) -> int:
    """Choose a viewer port, avoiding stale local servers on the default port."""
    if port_is_free(port):
        return port

    if explicit:
        raise SystemExit(
            f"Port {port} is already in use. Stop the process using it or rerun with "
            f"`--port {port + 1}`."
        )

    for candidate in range(port + 1, port + 20):
        if port_is_free(candidate):
            print(
                f"Port {port} is already in use; using http://localhost:{candidate} instead.",
                flush=True,
            )
            return candidate

    raise SystemExit("No free viewer port found in the 8080-8099 range. Rerun with --port <port>.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Install the starter dependencies, check the environment, and launch "
            "Creature Lab in a browser."
        )
    )
    parser.add_argument(
        "--creature",
        default="quadruped",
        help="Built-in creature to demo: quadruped, worm, or tripod. Default: quadruped.",
    )
    parser.add_argument(
        "--creature-path",
        type=Path,
        help="Path to a CreatureSpec JSON file. Overrides --creature.",
    )
    parser.add_argument("--task", type=Path, help="Optional TaskSpec JSON path.")
    parser.add_argument("--port", type=int, help="Viser server port. Default: 8080.")
    parser.add_argument(
        "--once",
        "--no-hold",
        dest="hold",
        action="store_false",
        help="Run one pass, save the trace, and exit instead of keeping the viewer open.",
    )
    parser.add_argument(
        "--hold",
        dest="hold",
        action="store_true",
        default=True,
        help="Keep the viewer open and looping until Ctrl+C. This is the default.",
    )
    parser.add_argument(
        "--open-browser",
        dest="open_browser",
        action="store_true",
        default=True,
        help="Open the viewer URL in your default browser. This is the default.",
    )
    parser.add_argument(
        "--no-open-browser",
        dest="open_browser",
        action="store_false",
        help="Print the viewer URL but do not open a browser tab.",
    )
    parser.add_argument("--skip-sync", action="store_true", help="Do not run uv sync first.")
    parser.add_argument(
        "--skip-doctor", action="store_true", help="Do not run creature-lab doctor."
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Install all optional extras instead of only the demo extras.",
    )
    parser.add_argument("--uv", help="Path to a uv executable.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the commands without running them.",
    )

    args = parser.parse_args()
    if args.creature_path and args.creature != "quadruped":
        parser.error("--creature-path cannot be combined with --creature")
    if args.creature_path and not args.creature_path.exists():
        parser.error(f"--creature-path does not exist: {args.creature_path}")
    if args.task and not args.task.exists():
        parser.error(f"--task does not exist: {args.task}")
    return args


def main() -> None:
    check_python()
    args = parse_args()
    uv = uv_command(args.uv)
    requested_port = args.port is not None
    port = choose_port(args.port or DEFAULT_PORT, explicit=requested_port)
    url = f"http://localhost:{port}"

    print("Creature Lab starter")
    print(f"Repository: {ROOT}")
    print(f"Viewer URL: {url}")
    print("Press Ctrl+C in this terminal to stop the viewer.")

    if not args.skip_sync:
        sync_args = (
            ["sync", "--inexact", "--all-extras"]
            if args.full
            else [
                "sync",
                "--inexact",
                "--extra",
                "sim",
                "--extra",
                "viz",
            ]
        )
        run_step(
            "Install dependencies",
            [*uv, *sync_args],
            dry_run=args.dry_run,
            failure_hint=(
                "Dependency installation failed. Check your network connection and Python "
                "version, then try `uv sync --inexact --extra sim --extra viz` manually."
            ),
        )

    if not args.skip_doctor:
        run_step(
            "Check environment",
            [*uv, "run", "creature-lab", "doctor"],
            dry_run=args.dry_run,
            failure_hint=(
                "Environment checks failed. The table above should show which optional "
                "component is missing or broken."
            ),
        )

    demo_command = [*uv, "run", "creature-lab", "demo", "--port", str(port)]
    if args.open_browser:
        demo_command.append("--open-browser")
    else:
        print(f"Open this URL manually after launch: {url}")

    if args.creature_path:
        demo_command.append(str(args.creature_path))
    else:
        demo_command.extend(["--creature", args.creature])
    if args.task:
        demo_command.extend(["--task", str(args.task)])
    if not args.hold:
        demo_command.append("--no-hold")

    run_step(
        "Launch viewer",
        demo_command,
        dry_run=args.dry_run,
        failure_hint=(
            f"The viewer failed to launch. Try `python scripts/start.py --port {port + 1}` "
            "or run `uv run creature-lab doctor` for details."
        ),
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped Creature Lab.")
        sys.exit(130)
