"""
Manages all active WebSocket connections from mobile clients.
Broadcasts alerts to all connected phones.
"""

import logging
from typing import Dict
from fastapi import WebSocket

log = logging.getLogger("connection_manager")


class ConnectionManager:
    def __init__(self):
        self._clients: Dict[str, WebSocket] = {}

    async def connect(self, device_id: str, websocket: WebSocket):
        await websocket.accept()
        self._clients[device_id] = websocket
        log.info(f"Device connected: {device_id} ({len(self._clients)} total)")

    def disconnect(self, device_id: str):
        self._clients.pop(device_id, None)
        log.info(f"Device disconnected: {device_id} ({len(self._clients)} total)")

    async def broadcast(self, message: str):
        """Send alert to all connected mobile clients."""
        disconnected = []
        for device_id, ws in self._clients.items():
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(device_id)

        for device_id in disconnected:
            self.disconnect(device_id)

    def count(self) -> int:
        return len(self._clients)
