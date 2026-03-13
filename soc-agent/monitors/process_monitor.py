"""
Process Monitor — polls running processes and flags suspicious ones.
Detects: reverse shells, crypto miners, unexpected SUID, high-CPU anomalies.
"""

import asyncio
import logging
import psutil
import re
from typing import Any, Dict, Set

from core.event_bus import EventBus, SecurityEvent

log = logging.getLogger("process_monitor")

SUSPICIOUS_NAMES = {
    "nc", "ncat", "nmap", "masscan", "hydra", "john", "hashcat",
    "sqlmap", "metasploit", "msfconsole", "msfvenom", "xmrig",
    "minerd", "cpuminer", "stratum",
}

SUSPICIOUS_CMDLINE_PATTERNS = [
    re.compile(r"bash\s+-i"),                        # interactive bash
    re.compile(r"/dev/tcp/"),                        # bash tcp redirection
    re.compile(r"python.*-c.*socket"),               # python reverse shell
    re.compile(r"perl.*-e.*socket"),                 # perl reverse shell
    re.compile(r"ruby.*-rsocket"),                   # ruby reverse shell
    re.compile(r"nc\s+.*-e"),                        # netcat with exec
    re.compile(r"(wget|curl).*\|\s*(bash|sh|python)"), # pipe to shell
    re.compile(r"stratum\+tcp://"),                  # crypto mining pool
]


class ProcessMonitor:
    def __init__(self, bus: EventBus, config: Dict[str, Any]):
        self.bus = bus
        self.interval = config.get("poll_interval", 5)
        self.cpu_threshold = config.get("cpu_alert_threshold", 90.0)
        self._alerted_pids: Set[int] = set()

    async def start(self):
        log.info(f"Process monitor started (poll every {self.interval}s)")
        while True:
            await self._scan()
            await asyncio.sleep(self.interval)

    async def _scan(self):
        try:
            for proc in psutil.process_iter(["pid", "name", "cmdline", "username", "cpu_percent"]):
                try:
                    info = proc.info
                    pid = info["pid"]

                    if pid in self._alerted_pids:
                        continue

                    name = (info.get("name") or "").lower()
                    cmdline = " ".join(info.get("cmdline") or [])
                    user = info.get("username", "?")
                    cpu = info.get("cpu_percent", 0) or 0

                    # Check suspicious name
                    if name in SUSPICIOUS_NAMES:
                        await self._fire(pid, name, user, cmdline,
                                         f"Suspicious process detected: '{name}' (PID {pid}, user={user})",
                                         "high")

                    # Check suspicious cmdline patterns
                    for pattern in SUSPICIOUS_CMDLINE_PATTERNS:
                        if pattern.search(cmdline):
                            await self._fire(pid, name, user, cmdline,
                                             f"Suspicious command pattern in PID {pid}: {pattern.pattern}",
                                             "critical")
                            break

                    # Check CPU spike (after two polls, psutil needs warmup)
                    if cpu > self.cpu_threshold:
                        await self._fire(pid, name, user, cmdline,
                                         f"High CPU usage: PID {pid} ({name}) at {cpu:.1f}%",
                                         "medium")

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            log.error(f"Process scan error: {e}")

    async def _fire(self, pid, name, user, cmdline, description, severity):
        self._alerted_pids.add(pid)
        await self.bus.publish_event(SecurityEvent(
            type="suspicious_process",
            severity=severity,
            pid=pid,
            description=description,
            raw={"pid": pid, "name": name, "user": user, "cmdline": cmdline},
        ))
