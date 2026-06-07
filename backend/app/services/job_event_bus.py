"""In-memory async event bus for broadcasting job status changes.

Uses asyncio.Queue per subscriber — no Redis needed for a single-process
backend.  Subscribers register with a job_id and receive events until the
job reaches a terminal state (``completed`` or ``failed``).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("manga_api.job_event_bus")


@dataclass(frozen=True, slots=True)
class JobEvent:
    """A single status-change event for a pipeline job."""

    job_id: str
    status: str
    detail: str | None = None
    payload: dict[str, Any] | None = None


class JobEventBus:
    """Broadcast hub that fans out ``JobEvent``s to per-subscriber queues."""

    def __init__(self) -> None:
        # job_id → set of subscriber queues
        self._subscribers: dict[str, set[asyncio.Queue[JobEvent]]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, job_id: str) -> asyncio.Queue[JobEvent]:
        """Create a new subscriber queue for *job_id*."""
        queue: asyncio.Queue[JobEvent] = asyncio.Queue()
        async with self._lock:
            self._subscribers.setdefault(job_id, set()).add(queue)
        logger.debug("subscriber added for job %s (total=%d)", job_id, len(self._subscribers.get(job_id, set())))
        return queue

    async def unsubscribe(self, job_id: str, queue: asyncio.Queue[JobEvent]) -> None:
        """Remove a subscriber queue and clean up if empty."""
        async with self._lock:
            subs = self._subscribers.get(job_id)
            if subs is not None:
                subs.discard(queue)
                if not subs:
                    del self._subscribers[job_id]
        logger.debug("subscriber removed for job %s", job_id)

    async def publish(self, event: JobEvent) -> None:
        """Push *event* to every subscriber listening for its ``job_id``."""
        async with self._lock:
            subs = self._subscribers.get(event.job_id)
            if not subs:
                return
            for queue in subs:
                queue.put_nowait(event)
        logger.debug("published %s for job %s to %d subscribers", event.status, event.job_id, len(subs) if subs else 0)


# Module-level singleton — imported from dependencies / lifespan.
job_event_bus = JobEventBus()
