"""Work that outlives the write: after the commit, or out of the request entirely."""

from __future__ import annotations

from collections.abc import Callable

from django.conf import settings
from django.db import connection, transaction
from django.utils.module_loading import import_string


def on_committed(fn: Callable[[], None]) -> None:
    """Run `fn` when the current transaction commits — or now, if there is none.

    The way a listener does anything the outside world can see: send an email, POST a webhook,
    write to another system. `object_written` fires inside `write()`'s transaction, so a listener
    that acts there is claiming a write that has not happened yet and may still roll back.

    It behaves sensibly in both cases, so a listener writes it unconditionally and never asks
    which situation it is in.
    """
    if connection.in_atomic_block:
        transaction.on_commit(fn)
    else:
        fn()


def defer(fn: Callable, *args, **kwargs) -> None:
    """Run `fn(*args, **kwargs)` out of the request if the deployment has somewhere to run it,
    else after the commit, in process.

    `PLINTA_DEFER = "myproject.queue.enqueue"` names a callable taking `(fn, args, kwargs)`;
    Celery, RQ, django-tasks and a thread pool all fit behind it. This is the whole of plinta's
    answer to background work: core ships no queue, but every package that needs one needs the
    same one, so there is an interface with a synchronous default.
    """
    runner = getattr(settings, "PLINTA_DEFER", "")
    if runner:
        on_committed(lambda: import_string(runner)(fn, args, kwargs))
    else:
        on_committed(lambda: fn(*args, **kwargs))
