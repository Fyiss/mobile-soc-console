"""
Log Monitor — tails arbitrary log files and fires events on regex matches.
Configure rules in config.yaml under monitors.log.rules.
"""

import asyncio
import logging
import re
from pathlib import Path
from typing import Any, Dict, List

from core.event_bus import EventBus, SecurityEvent

log = logging.getLogger("log_monitor")

DEFAULT_RULES = [
    {
        "name": "sudo_failure",
        "pattern": r"sudo:.*authentication failure",
        "severity": "medium",
        "description": "sudo authentication failure detected",
    },
    {
        "name": "su_attempt",
        "pattern": r"su\[.*\]: FAILED",
        "severity": "medium",
        "description": "su privilege escalation failure",
    },
    {
        "name": "oom_kill",
        "pattern": r"Out of memory: Killed process (\d+)",
        "severity": "low",
        "description": "OOM killer fired",
    },
    {
        "name": "kernel_exploit_attempt",
        "pattern": r"ptrace|/proc/kallsyms|/dev/kmem",
        "severity": "critical",
        "description": "Possible kernel exploit attempt",
    },
]


class LogMonitor:
    def __init__(self, bus: EventBus, config: Dict[str, Any]):
        self.bus = bus
        self.logfile = config.get("file", "/var/log/auth.log")
        rules_raw = config.get("rules", DEFAULT_RULES)
        self.rules = [
            (r["name"], re.compile(r["pattern"], re.IGNORECASE),
             r["severity"], r["description"])
            for r in rules_raw
        ]

    async def start(self):
        path = Path(self.logfile)
        if not path.exists():
            log.warning(f"Log file not found: {self.logfile} — using journald fallback")
            await self._tail_journald()
            return

        log.info(f"Log monitor watching: {self.logfile} ({len(self.rules)} rules)")
        await self._tail_file(path)

    async def _tail_file(self, path: Path):
        with open(path, "r") as f:
            f.seek(0, 2)  # Seek to end
            while True:
                line = f.readline()
                if line:
                    await self._check(line.strip())
                else:
                    await asyncio.sleep(0.2)

    async def _tail_journald(self):
        """Fallback: tail the system journal."""
        proc = await asyncio.create_subprocess_exec(
            "journalctl", "-f", "-n", "0", "--output=short",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        async for line in proc.stdout:
            await self._check(line.decode(errors="replace").strip())

    async def _check(self, line: str):
        for name, pattern, severity, description in self.rules:
            if pattern.search(line):
                await self.bus.publish_event(SecurityEvent(
                    type=f"log_{name}",
                    severity=severity,
                    description=description,
                    raw={"rule": name, "line": line},
                ))
                break  # One event per line max
