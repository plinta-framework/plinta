"""The four signals a write passes through, and the one function that sends them.

Core emits; anything installed listens; nobody imports anybody. A third party with a signal of
its own calls `emit()` with it and gets the same behaviour.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from django.dispatch import Signal

logger = logging.getLogger(__name__)


def _named(name: str) -> Signal:
    """A Signal that knows its own name, so a log line can say which one's listener failed."""
    signal = Signal()
    signal.plinta_name = name
    return signal


#: After validation, before save. A listener may set a field or raise to refuse.
object_writing = _named("object_writing")
#: After save, with the diff. A listener that raises is logged; the write stands.
object_written = _named("object_written")
#: Before delete. A listener may raise to refuse.
object_deleting = _named("object_deleting")
#: After delete. `pk` is passed because Django has cleared `obj.pk`.
object_deleted = _named("object_deleted")


def emit(signal: Signal, obj: Any, *, robust: bool = True, **payload: Any) -> None:
    """Send `signal` for `obj` to every receiver.

    `sender` is the model class, so a receiver can connect to one model (`sender=Sale`) or to all.

    Robust: every receiver runs, and one that raises is logged with its module and name.
    Not robust: the first receiver to raise stops the rest and the exception reaches the caller,
    which is how `object_writing` and `object_deleting` let a listener veto.
    """
    sender = type(obj)
    if not robust:
        signal.send(sender=sender, obj=obj, **payload)
        return
    for receiver, response in signal.send_robust(sender=sender, obj=obj, **payload):
        if isinstance(response, Exception):
            logger.error(
                "%s listener %s.%s failed",
                getattr(signal, "plinta_name", "signal"),
                getattr(receiver, "__module__", "?"),
                getattr(receiver, "__qualname__", receiver),
                exc_info=response,
            )


def emit_writing(
    obj,
    *,
    mode: Literal["create", "update"],
    fields: list[str],
    actor=None,
    via: str = "",
) -> None:
    """Announce a row about to be saved. A listener may adjust `obj` or raise to refuse.

    `fields` names what the caller is writing, as **field names** (`store`), never as column
    attnames (`store_id`) — a listener asking "did `store` change?" must not have to know which
    it was given.
    """
    emit(object_writing, obj, robust=False, mode=mode, fields=fields, actor=actor, via=via)


def emit_written(
    obj,
    *,
    mode: Literal["create", "update"],
    changes: dict[str, tuple[Any, Any]],
    actor=None,
    via: str = "",
) -> None:
    """Announce a row that was saved. `changes` is `{field: (before, after)}`, keyed by field name;
    on a create every `before` is `None`. A listener that raises here is logged; the write stands.
    """
    emit(object_written, obj, mode=mode, changes=changes, actor=actor, via=via)


def emit_deleting(obj, *, actor=None, via: str = "") -> None:
    """Announce a row about to be deleted. A listener may raise to refuse."""
    emit(object_deleting, obj, robust=False, actor=actor, via=via)


def emit_deleted(obj, *, pk, actor=None, via: str = "") -> None:
    """Announce a row that was deleted. `pk` is passed separately because Django has set
    `obj.pk` to None by the time this runs."""
    emit(object_deleted, obj, pk=pk, actor=actor, via=via)


def has_listeners(signal: Signal, sender: type | None = None) -> bool:
    """Whether anything would receive this. Lets a caller skip work that only fills a payload —
    `write()` builds no diff when nothing listens to `object_written`."""
    return signal.has_listeners(sender)
