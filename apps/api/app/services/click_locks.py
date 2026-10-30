from __future__ import annotations

import asyncio
import threading
from collections import deque
from collections.abc import AsyncIterator
from concurrent.futures import Future
from contextlib import asynccontextmanager


ClickLockKey = tuple[str, str, str]


class ClickLocks:
    """Serialize one debounce key without occupying a DB connection or worker.

    Queues contain only current holders/waiters; idle keys are removed. Futures
    are thread-safe so requests on different event loops still share the same
    process-local lock. Separate API processes need database-level coordination.
    """

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._queues: dict[ClickLockKey, deque[Future[None]]] = {}

    @asynccontextmanager
    async def hold(self, key: ClickLockKey) -> AsyncIterator[None]:
        waiter: Future[None] = Future()
        with self._guard:
            queue = self._queues.setdefault(key, deque())
            queue.append(waiter)
            if len(queue) == 1:
                waiter.set_result(None)

        try:
            # Shield keeps task cancellation from cancelling a handoff Future
            # behind another request's back. The finally block removes exactly
            # this reservation, including a cancelled waiter or newly granted one.
            await asyncio.shield(asyncio.wrap_future(waiter))
            yield
        finally:
            with self._guard:
                queue = self._queues[key]
                was_head = queue[0] is waiter
                queue.remove(waiter)
                if not waiter.done():
                    waiter.cancel()
                if not queue:
                    del self._queues[key]
                elif was_head:
                    queue[0].set_result(None)


click_locks = ClickLocks()
