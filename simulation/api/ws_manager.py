"""
WebSocket 连接管理器 — 广播推送
"""
from __future__ import annotations

import asyncio
import json

from fastapi import WebSocket


class WsManager:
    """管理所有 WebSocket 客户端连接，支持广播"""

    def __init__(self):
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(ws)

    async def broadcast(self, message: dict) -> None:
        """向所有已连接客户端广播 JSON 消息

        先对连接集合做快照再遍历，避免遍历期间 connect()/disconnect()
        并发修改集合导致 RuntimeError: Set changed size during iteration。
        """
        async with self._lock:
            connections = list(self._connections)
        dead: set[WebSocket] = set()
        payload = json.dumps(message, ensure_ascii=False)
        for ws in connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        if dead:
            async with self._lock:
                self._connections -= dead

    @property
    def connection_count(self) -> int:
        return len(self._connections)
