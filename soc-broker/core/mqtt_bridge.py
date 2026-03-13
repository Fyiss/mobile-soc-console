"""
MQTT Bridge — subscribes to agent alerts and forwards them
to connected mobile clients via WebSocket.
"""
import asyncio
import logging
import json
from datetime import datetime, timezone
from typing import Dict, Tuple
from core.config import Config
from core.connection_manager import ConnectionManager

log = logging.getLogger("mqtt_bridge")

try:
    import aiomqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False

class MQTTBridge:
    DEDUP_WINDOW = 60  # seconds

    def __init__(self, config: Config, manager: ConnectionManager):
        self.config = config
        self.manager = manager
        self.connected = False
        self._client = None
        self._seen: Dict[Tuple[str, str], datetime] = {}

    def _is_duplicate(self, payload: str) -> bool:
        try:
            data = json.loads(payload)
        except Exception:
            return False
        key = (data.get("type", ""), data.get("source_ip", ""))
        now = datetime.now(timezone.utc)
        last_seen = self._seen.get(key)
        if last_seen is not None:
            elapsed = (now - last_seen).total_seconds()
            if elapsed < self.DEDUP_WINDOW:
                log.info(
                    f"[DEDUP] Suppressed '{key[0]}' from '{key[1]}' "
                    f"(seen {elapsed:.0f}s ago, window={self.DEDUP_WINDOW}s)"
                )
                return True
        self._seen[key] = now
        return False

    async def start(self):
        if not MQTT_AVAILABLE:
            log.error("aiomqtt not installed")
            return
        while True:
            try:
                log.info(f"Connecting to MQTT at {self.config.mqtt.host}:{self.config.mqtt.port}")
                async with aiomqtt.Client(
                    hostname=self.config.mqtt.host,
                    port=self.config.mqtt.port,
                ) as client:
                    self._client = client
                    self.connected = True
                    await client.subscribe(self.config.mqtt.topic_alerts)
                    log.info(f"Subscribed to {self.config.mqtt.topic_alerts}")
                    async for message in client.messages:
                        payload = message.payload.decode()
                        if self._is_duplicate(payload):
                            continue
                        log.info(f"Alert received → forwarding to {self.manager.count()} client(s)")
                        await self.manager.broadcast(payload)
            except Exception as e:
                self.connected = False
                self._client = None
                log.error(f"MQTT error: {e} — retrying in 5s")
                await asyncio.sleep(5)

    async def publish_command(self, command: dict):
        if not self._client:
            raise RuntimeError("Not connected to MQTT broker")
        payload = json.dumps(command)
        await self._client.publish(self.config.mqtt.topic_commands, payload, qos=1)
        log.info(f"Command published: {command['action']} → {command['target']}")
