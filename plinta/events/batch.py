"""A window around many writes, so a listener can act once instead of once per row."""

from __future__ import annotations

import contextvars
import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from .after import on_committed

logger = logging.getLogger(__name__)

#: A separate value per request, thread or async task — two users importing at once each see
#: only their own batch. A module-level variable would be shared by both.
_current: contextvars.ContextVar["Batch | None"] = contextvars.ContextVar("plinta_batch", default=None)


class Buffer:
    """What `Batch.buffer()` hands a listener: somewhere to put an item for the flush.

    An item appended inside a transaction joins the flush only if that transaction commits. A row
    written in a savepoint that rolls back — one failed row of an import — takes its item with it.
    """

    def __init__(self, items: list, using: str | None) -> None:
        self._items = items
        self._using = using

    def append(self, item: Any) -> None:
        on_committed(lambda: self._items.append(item), using=self._using)


@dataclass
class Batch:
    via: str
    using: str | None = None
    _on_exit: list[Callable[[], None]] = field(default_factory=list, init=False, repr=False)
    _buffers: dict[str, Buffer] = field(default_factory=dict, init=False, repr=False)

    def on_exit(self, fn: Callable[[], None]) -> None:
        """Call `fn` once when the outermost batch ends."""
        self._on_exit.append(fn)

    def buffer(self, key: str, flush: Callable[[list], None]) -> Buffer:
        """A buffer that lives exactly as long as this batch.

        The first call under `key` creates it and registers `flush(items)` to run once at exit;
        later calls return the same buffer. It lives on the batch rather than at module level,
        where every concurrent batch would share it.
        """
        if key not in self._buffers:
            items: list = []
            self._buffers[key] = Buffer(items, self.using)
            self.on_exit(lambda: flush(items))
        return self._buffers[key]


def current_batch() -> Batch | None:
    """The batch in progress, or None. A listener asks to decide between acting now and buffering."""
    return _current.get()


@contextmanager
def batch(via: str = "", *, using: str | None = None) -> Iterator[Batch]:
    """A window around many writes. Nests: an inner block joins the outer one, so an action that
    opens a batch and calls a service that opens another gets one batch and one flush.

    Opens no transaction of its own — a five-thousand-row import inside one `atomic()` is the
    caller's choice — but it looks at whether one is open on `using` when it exits. Outside a
    transaction each write committed on its own, so the flush runs at once and an exception at
    row 3,000 still records the 2,999 that are in the database. Inside one, the flush waits for
    the commit, so a rollback records nothing rather than a trail of rows that never existed. A
    row rolled back on its own, in a savepoint, is left out of the flush the same way.
    """
    existing = _current.get()
    if existing is not None:
        yield existing
        return
    current = Batch(via=via, using=using)
    token = _current.set(current)

    def run_on_exit() -> None:
        """Every function registered with `on_exit`, each in its own try. Not to be confused with
        the `flush` a buffer is given: that one takes the accumulated list, this one takes nothing."""
        for fn in current._on_exit:
            try:
                fn()
            except Exception:                 # one listener failing must not lose the others
                logger.exception("batch exit %r failed", getattr(fn, "__qualname__", fn))

    try:
        yield current
    finally:
        _current.reset(token)
        # Inside a transaction: only if it commits. Outside: now. Registered after every
        # buffered append, so on commit the items are all in place before the flush reads them.
        on_committed(run_on_exit, using=using)
