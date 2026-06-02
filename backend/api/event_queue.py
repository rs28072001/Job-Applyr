"""
Sync → Async event bridge.

The Selenium session runs in a ThreadPoolExecutor (blocking, sync).
tracker._emit() puts JSON events into a threading.Queue (thread-safe, sync).
A background asyncio task drains that queue into an asyncio.Queue every 50ms.
The WebSocket handler awaits the asyncio.Queue and forwards to the browser.
"""
import asyncio
import queue
from typing import Optional

# Written by the sync Selenium thread via tracker._emit()
sync_q: queue.Queue = queue.Queue(maxsize=2000)

# Read by the async WebSocket handler
_async_q: Optional[asyncio.Queue] = None
_relay_task: Optional[asyncio.Task] = None


async def start_relay() -> None:
    """Called once at server startup to begin the relay loop."""
    global _async_q, _relay_task
    _async_q = asyncio.Queue(maxsize=2000)

    async def _relay():
        while True:
            try:
                item = sync_q.get_nowait()
                await _async_q.put(item)
            except queue.Empty:
                pass
            await asyncio.sleep(0.05)

    _relay_task = asyncio.create_task(_relay())


async def get_event() -> dict:
    """Await the next event from the relay queue."""
    if _async_q is None:
        raise RuntimeError("Event queue not started — call start_relay() first")
    return await _async_q.get()


async def get_event_timeout(timeout: float = 1.0) -> Optional[dict]:
    """Return next event or None if timeout elapses (for polling WS loops)."""
    if _async_q is None:
        return None
    try:
        return await asyncio.wait_for(_async_q.get(), timeout=timeout)
    except asyncio.TimeoutError:
        return None
