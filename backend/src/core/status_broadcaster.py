import asyncio
import json
import logging
from typing import Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class StatusBroadcaster:
    """Thread-safe WebSocket broadcaster.

    broadcast() can be called from ANY thread (sync worker threads or the
    asyncio event loop). It schedules the actual send onto the event loop via
    run_coroutine_threadsafe, so it never blocks the caller.
    """

    def __init__(self):
        self._clients: Set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.add(ws)
        try:
            await ws.send_text(json.dumps({"type": "connected", "message": "实时状态流已连接"}, ensure_ascii=False))
        except Exception:
            pass

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    def broadcast(self, message: dict) -> None:
        """Thread-safe: callable from sync worker threads."""
        if not self._loop or not self._clients:
            return
        try:
            asyncio.run_coroutine_threadsafe(self._do_broadcast(message), self._loop)
        except Exception as e:
            logger.debug(f"broadcast skipped: {e}")

    def has_clients(self) -> bool:
        return bool(self._clients)

    async def _do_broadcast(self, message: dict) -> None:
        payload = json.dumps(message, ensure_ascii=False)
        dead = []
        for ws in list(self._clients):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)


status_broadcaster = StatusBroadcaster()
