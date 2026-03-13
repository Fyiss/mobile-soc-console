"""
Network Monitor — detects port scans and unexpected outbound connections
using /proc/net or psutil. No root required for basic detection.
"""

import asyncio
import logging
import psutil
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Set, Tuple

from core.event_bus import EventBus, SecurityEvent

log = logging.getLogger("network_monitor")

# Ports that should never have inbound connections in most environments
SENSITIVE_PORTS = {22, 23, 3306, 5432, 6379, 27017, 2375, 2376}

# Known bad destination ports (C2, mining pools, etc.)
SUSPICIOUS_DEST_PORTS = {4444, 1337, 31337, 6666, 6667, 6668, 6669}


class NetworkMonitor:
    def __init__(self, bus: EventBus, config: Dict[str, Any]):
        self.bus = bus
        self.interval = config.get("poll_interval", 3)
        self.scan_threshold = config.get("scan_threshold", 15)  # unique ports/IP in window
        self.window = config.get("scan_window_seconds", 10)

        # ip -> list of (timestamp, port) for scan detection
        self._scan_tracker: Dict[str, list] = defaultdict(list)
        self._alerted_connections: Set[Tuple] = set()
        self._alerted_scanners: Set[str] = set()

    async def start(self):
        log.info(f"Network monitor started (poll every {self.interval}s)")
        while True:
            await self._scan()
            await asyncio.sleep(self.interval)

    async def _scan(self):
        try:
            connections = psutil.net_connections(kind="inet")
            now = datetime.now(timezone.utc).timestamp()

            for conn in connections:
                laddr = conn.laddr
                raddr = conn.raddr
                status = conn.status

                if not raddr:
                    continue

                remote_ip = raddr.ip
                remote_port = raddr.port
                local_port = laddr.port if laddr else 0

                # Skip loopback
                if remote_ip.startswith("127.") or remote_ip == "::1":
                    continue

                key = (remote_ip, remote_port, local_port)

                # Detect connections to suspicious destination ports
                if remote_port in SUSPICIOUS_DEST_PORTS and key not in self._alerted_connections:
                    self._alerted_connections.add(key)
                    await self.bus.publish_event(SecurityEvent(
                        type="suspicious_connection",
                        severity="high",
                        source_ip=remote_ip,
                        description=(f"Outbound connection to suspicious port "
                                     f"{remote_ip}:{remote_port} (local port {local_port})"),
                        raw={"remote_ip": remote_ip, "remote_port": remote_port,
                             "local_port": local_port, "status": status},
                    ))

                # Track for port scan detection (many unique local ports from same IP)
                self._scan_tracker[remote_ip].append((now, local_port))
                self._scan_tracker[remote_ip] = [
                    (t, p) for t, p in self._scan_tracker[remote_ip]
                    if now - t <= self.window
                ]

                unique_ports = len({p for _, p in self._scan_tracker[remote_ip]})
                if (unique_ports >= self.scan_threshold
                        and remote_ip not in self._alerted_scanners):
                    self._alerted_scanners.add(remote_ip)
                    await self.bus.publish_event(SecurityEvent(
                        type="port_scan",
                        severity="high",
                        source_ip=remote_ip,
                        description=(f"Port scan detected from {remote_ip}: "
                                     f"{unique_ports} unique ports in {self.window}s"),
                        raw={"remote_ip": remote_ip, "unique_ports": unique_ports},
                    ))

        except Exception as e:
            log.error(f"Network scan error: {e}")
