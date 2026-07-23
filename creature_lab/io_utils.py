"""Small, backend-neutral helpers for safe durable-artifact I/O."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path, PurePath


def atomic_write_text(path: Path, text: str) -> None:
    """Atomically replace ``path`` with UTF-8 ``text`` on the same filesystem."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def safe_bundle_filename(value: str, *, field: str = "artifact") -> str:
    """Validate a manifest/controller filename that must stay in one directory."""
    path = PurePath(value)
    if path.is_absolute() or len(path.parts) != 1 or path.name in {"", ".", ".."}:
        raise ValueError(f"{field} must be a filename contained in its bundle")
    return path.name


def contained_child(directory: Path, name: str, *, field: str = "artifact") -> Path:
    """Return a validated immediate child path of ``directory``."""
    return Path(directory) / safe_bundle_filename(name, field=field)
