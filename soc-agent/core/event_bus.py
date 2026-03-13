"""
Async event bus — monitors publish events, broker/dispatcher subscribe.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Tuple
from datetime import datetime, timezone
import uuid

log = logging.getLogger("event_bus")

@dataclass
class SecurityEvent:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: str = ""
    severity: str = "medium"
    source_ip: str = ""
    pid: int = 0
    description: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "severity": self.severity,
            "source_ip": self.source_ip,
            "pid": self.pid,
            "description": self.description,
            "raw": self.raw,
            "timestamp": self.timestamp,
        }

@dataclass
class ResponseCommand:
    action: str = ""
    target: str = ""
    event_id: str = ""
    authorized_by: str = ""

class EventBus:
    DEDUP_WINDOW = 60  # seconds

    def __init__(self):
        self._alert_queue: asyncio.Queue = asyncio.Queue()
        self._command_queue: asyncio.Queue = asyncio.Queue()
        self._seen: Dict[Tuple[str, str], datetime] = {}

    def _is_duplicate(self, event: SecurityEvent) -> bool:
        key = (event.type, event.source_ip)
        now = datetime.now(timezone.utc)
        last_seen = self._seen.get(key)
        if last_seen is not None:
            elapsed = (now - last_seen).total_seconds()
            if elapsed < self.DEDUP_WINDOW:
                log.info(
                    f"[DEDUP] Suppressed '{event.type}' from '{event.source_ip}' "
                    f"(seen {elapsed:.0f}s ago, window={self.DEDUP_WINDOW}s)"
                )
                return True
        self._seen[key] = now
        return False

    async def publish_event(self, event: SecurityEvent):
        if self._is_duplicate(event):
            return
        log.info(f"[EVENT] {event.type} | {event.severity} | {event.description}")
        await self._alert_queue.put(event)

    async def next_event(self) -> SecurityEvent:
        return await self._alert_queue.get()

    async def publish_command(self, cmd: ResponseCommand):
        log.info(f"[CMD] {cmd.action} -> {cmd.target}")
        await self._command_queue.put(cmd)

    async def next_command(self) -> ResponseCommand:
        return await self._command_queue.get()
