"""
SSH Monitor — detects brute force attempts by tailing auth logs
or querying journald. Fires an event after N failures from same IP.
"""

import asyncio
import logging
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Any

from core.event_bus import EventBus, SecurityEvent

log = logging.getLogger("ssh_monitor")

# Matches: Failed password for root from 192.168.1.5 port 54321 ssh2
FAILED_RE = re.compile(
    r"Failed (?:password|publickey) for (?:invalid user )?(\S+) from ([\d.:\w]+)"
)
# Matches: Disconnected from authenticating user root 192.168.1.5
DISCONNECT_RE = re.compile(
    r"Disconnected from (?:authenticating user \S+ )?([\d.]+)"
)


class SSHMonitor:
    def __init__(self, bus: EventBus, config: Dict[str, Any]):
        self.bus = bus
        self.threshold = config.get("bruteforce_threshold", 5)
        self.window_seconds = config.get("window_seconds", 60)
        self._failures: Dict[str, list] = defaultdict(list)

    async def start(self):
        log.info(f"SSH monitor started (threshold={self.threshold} in {self.window_seconds}s)")
        await self._tail_journald()

    async def _tail_journald(self):
        """Stream SSH-related journal entries in real time."""
        proc = await asyncio.create_subprocess_exec(
            "journalctl", "-u", "sshd", "-u", "sshd-session", "-f", "-n", "0", "--output=short-unix",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )

        log.info("Tailing sshd journal...")
        async for line in proc.stdout:
            await self._process_line(line.decode(errors="replace").strip())

    async def _process_line(self, line: str):
        match = FAILED_RE.search(line)
        if not match:
            return

        user, ip = match.group(1), match.group(2)
        now = datetime.now(timezone.utc).timestamp()

        # Sliding window
        self._failures[ip].append(now)
        self._failures[ip] = [
            t for t in self._failures[ip]
            if now - t <= self.window_seconds
        ]

        count = len(self._failures[ip])
        log.debug(f"SSH fail from {ip} (user={user}, count={count})")

        if count == self.threshold:
            await self.bus.publish_event(SecurityEvent(
                type="ssh_bruteforce",
                severity="high",
                source_ip=ip,
                description=f"SSH brute force: {count} failures from {ip} (targeting '{user}')",
                raw={"user": user, "ip": ip, "count": count, "line": line},
            ))
        elif count > self.threshold and count % 10 == 0:
            # Re-alert every 10 additional failures to avoid spam
            await self.bus.publish_event(SecurityEvent(
                type="ssh_bruteforce_ongoing",
                severity="critical",
                source_ip=ip,
                description=f"SSH brute force ongoing: {count} failures from {ip}",
                raw={"user": user, "ip": ip, "count": count},
            ))
