"""
MQTT client — forwards SecurityEvents to the broker,
receives ResponseCommands from the mobile app.
"""

import asyncio
import json
import logging
import socket
from core.config import BrokerConfig
from core.event_bus import EventBus, ResponseCommand

log = logging.getLogger("broker_client")

try:
    import aiomqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    log.warning("aiomqtt not installed — broker disabled. Run: pip install aiomqtt")


class BrokerClient:
    def __init__(self, config: BrokerConfig, bus: EventBus):
        self.config = config
        self.bus = bus
        self.hostname = socket.gethostname()

    async def connect(self):
        if not MQTT_AVAILABLE:
            log.warning("MQTT unavailable, running in local-only mode.")
            await self._drain_events_locally()
            return

        log.info(f"Connecting to MQTT broker at {self.config.host}:{self.config.port}")
        try:
            async with aiomqtt.Client(
                hostname=self.config.host,
                port=self.config.port,
                username=self.config.username or None,
                password=self.config.password or None,
            ) as client:
                await client.subscribe(self.config.topic_commands)
                log.info(f"Subscribed to {self.config.topic_commands}")

                # Run publisher and subscriber concurrently
                await asyncio.gather(
                    self._publish_loop(client),
                    self._subscribe_loop(client),
                )
        except Exception as e:
            log.error(f"Broker connection failed: {e}")

    async def _publish_loop(self, client):
        """Forward events from bus to MQTT."""
        while True:
            event = await self.bus.next_event()
            payload = json.dumps({
                "host": self.hostname,
                **event.to_dict()
            })
            await client.publish(self.config.topic_alerts, payload, qos=1)
            log.debug(f"Published alert: {event.type} [{event.id}]")

    async def _subscribe_loop(self, client):
        """Receive commands from mobile app via MQTT."""
        async for message in client.messages:
            try:
                data = json.loads(message.payload.decode())
                cmd = ResponseCommand(
                    action=data.get("action", ""),
                    target=data.get("target", ""),
                    event_id=data.get("event_id", ""),
                    authorized_by=data.get("authorized_by", "unknown"),
                )
                log.info(f"Received command: {cmd.action} on {cmd.target} "
                         f"(auth: {cmd.authorized_by})")
                await self.bus.publish_command(cmd)
            except Exception as e:
                log.error(f"Failed to parse command: {e}")

    async def _drain_events_locally(self):
        """Fallback: just log events when broker is unavailable."""
        while True:
            event = await self.bus.next_event()
            log.info(f"[LOCAL] Alert: {event.to_dict()}")
