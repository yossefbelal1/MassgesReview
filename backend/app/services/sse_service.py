import asyncio
import json
import logging
from typing import Dict, Set

logger = logging.getLogger("reviewflow.sse")

class SSEBroadcaster:
    """
    In-memory asynchronous pub/sub broadcaster for pushing real-time
    membership events and winback updates to connected client dashboards via Server-Sent Events (SSE).
    """

    def __init__(self):
        # channel_id -> set of asyncio.Queue
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, channel_id: str, queue: asyncio.Queue):
        """Registers a new SSE client queue for a specific channel."""
        async with self._lock:
            if channel_id not in self._subscribers:
                self._subscribers[channel_id] = set()
            self._subscribers[channel_id].add(queue)
            logger.debug(f"[SSE] Client subscribed to channel {channel_id}. Active: {len(self._subscribers[channel_id])}")

    async def unsubscribe(self, channel_id: str, queue: asyncio.Queue):
        """Removes a disconnected SSE client queue."""
        async with self._lock:
            if channel_id in self._subscribers:
                self._subscribers[channel_id].discard(queue)
                if not self._subscribers[channel_id]:
                    del self._subscribers[channel_id]
            logger.debug(f"[SSE] Client unsubscribed from channel {channel_id}")

    def broadcast(self, channel_id: str, event_type: str, data: dict):
        """
        Dispatches an event non-blockingly to all active subscribers for the channel.
        Can be called safely from synchronous or asynchronous code.
        """
        if channel_id not in self._subscribers:
            return

        payload = {
            "type": event_type,
            "data": data
        }

        # Schedule emission to all queues
        for queue in list(self._subscribers.get(channel_id, set())):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                logger.warning(f"[SSE] Queue full for subscriber on channel {channel_id}, dropping frame")
            except Exception as e:
                logger.warning(f"[SSE] Error queuing event for channel {channel_id}: {e}")

sse_broadcaster = SSEBroadcaster()
