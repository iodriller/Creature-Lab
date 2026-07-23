"""Undo/redo and named snapshots for the build editor.

Deliberately dumb and serialisable: the editor hands this class opaque *snapshot*
dictionaries (see :meth:`EditorSession._snapshot`) and asks for them back. It knows
nothing about creatures, tasks, or Viser, so it stays trivially unit-testable and can
never pull a physics/GUI import into the pure session layer.

The undo/redo model is the usual two-stack one:

- ``push(current)`` records ``current`` as an undo point and forgets any redo history
  (a fresh edit invalidates the redo branch).
- ``undo(current)`` returns the previous snapshot to restore, and stashes ``current`` so
  ``redo`` can return to it.
- ``redo(current)`` is the mirror image.

``current`` is always passed in rather than stored, so the session stays the single
owner of live state and the history holds only inert copies.
"""

from __future__ import annotations

from collections import deque
from typing import Any

Snapshot = dict[str, Any]

DEFAULT_LIMIT = 100


class EditorHistory:
    """A bounded undo/redo stack plus a bag of named snapshots."""

    def __init__(self, limit: int = DEFAULT_LIMIT) -> None:
        self._limit = limit
        self._undo: deque[Snapshot] = deque(maxlen=limit)
        self._redo: deque[Snapshot] = deque(maxlen=limit)
        self._named: dict[str, Snapshot] = {}

    # -- undo / redo ------------------------------------------------------------

    def push(self, current: Snapshot) -> None:
        """Record ``current`` as an undo point; a new edit clears the redo branch."""
        self._undo.append(current)
        self._redo.clear()

    def undo(self, current: Snapshot) -> Snapshot | None:
        """Return the snapshot to restore, or ``None`` if there is nothing to undo."""
        if not self._undo:
            return None
        self._redo.append(current)
        return self._undo.pop()

    def redo(self, current: Snapshot) -> Snapshot | None:
        """Return the snapshot to restore, or ``None`` if there is nothing to redo."""
        if not self._redo:
            return None
        self._undo.append(current)
        return self._redo.pop()

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def clear(self) -> None:
        """Drop all undo/redo history (used when a whole new document is loaded)."""
        self._undo.clear()
        self._redo.clear()

    # -- named snapshots --------------------------------------------------------

    def save_named(self, name: str, snapshot: Snapshot) -> None:
        self._named[name] = snapshot

    def get_named(self, name: str) -> Snapshot | None:
        return self._named.get(name)

    def named_names(self) -> list[str]:
        return sorted(self._named)

    def delete_named(self, name: str) -> bool:
        return self._named.pop(name, None) is not None
