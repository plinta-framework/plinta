"""A window around many writes, so a listener can act once instead of once per row."""

from __future__ import annotations

import contextvars
import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from django.db import connection, transaction

logger = logging.getLogger(__name__)

#: A separate value per request, thread or async task — two users importing at once each see
#: only their own batch. A module-level variable would be shared by both.
_current: contextvars.ContextVar["Batch | None"] = contextvars.ContextVar("plinta_batch", default=None)


@dataclass
class Batch:
    via: str
    _on_exit: list[Callable[[], None]] = field(default_factory=list, repr=False)
    _buffers: dict[str, list] = field(default_factory=dict, repr=False)

    def on_exit(self, fn: Callable[[], None]) -> None:
        """Call `fn` once when the outermost batch ends."""
        self._on_exit.append(fn)

    def buffer(self, key: str, flush: Callable[[list], None]) -> list:
        """A list that lives exactly as long as this batch.

        The first call under `key` creates it and registers `flush(items)` to run once at exit;
        later calls return the same list. It lives on the batch rather than at module level,
        where every concurrent batch would share it.
        """
        if key not in self._buffers:
            self._buffers[key] = items = []
            self.on_exit(lambda: flush(items))
        return self._buffers[key]


def current_batch() -> Batch | None:
    """The batch in progress, or None. A listener asks to decide between acting now and buffering."""
    return _current.get()


@contextmanager
def batch(via: str = "") -> Iterator[Batch]:
    """A window around many writes. Nests: an inner block joins the outer one, so an action that
    opens a batch and calls a service that opens another gets one batch and one flush.

    Opens no transaction of its own — a five-thousand-row import inside one `atomic()` is the
    caller's choice — but it looks at whether one is open when it exits. Outside a transaction
    each write committed on its own, so the flush runs at once and an exception at row 3,000
    still records the 2,999 that are in the database. Inside one, the flush waits for the commit,
    so a rollback records nothing rather than a trail of rows that never existed.
    """
    existing = _current.get()
    if existing is not None:
        yield existing
        return
    current = Batch(via=via)
    token = _current.set(current)

    def flush() -> None:
        for fn in current._on_exit:
            try:
                fn()
            except Exception:                 # one listener's flush failing must not lose the others
                logger.exception("batch flush %r failed", getattr(fn, "__qualname__", fn))

    try:
        yield current
    finally:
        _current.reset(token)
        if connection.in_atomic_block:
            transaction.on_commit(flush)      # inside someone's transaction: flush only if it commits
        else:
            flush()                           # each write committed on its own; flush now, exception or not
