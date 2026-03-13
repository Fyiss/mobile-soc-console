"""
Response Dispatcher — listens for ResponseCommands from the bus
and executes the appropriate action on the host.

Actions:
  block_ip     → adds iptables DROP rule
  unblock_ip   → removes iptables DROP rule
  kill_process → sends SIGKILL to PID
  isolate      → blocks all traffic except SSH from trusted IP
  dismiss      → no-op acknowledgement
"""

import asyncio
import logging
import subprocess
import shlex
from typing import Optional

from core.event_bus import EventBus, ResponseCommand

log = logging.getLogger("dispatcher")


class ResponseDispatcher:
    def __init__(self, bus: EventBus, trusted_ip: Optional[str] = None):
        self.bus = bus
        self.trusted_ip = trusted_ip  # Used during isolation to keep SSH alive

    async def listen(self):
        log.info("Response dispatcher listening for commands...")
        while True:
            cmd = await self.bus.next_command()
            await self._dispatch(cmd)

    async def _dispatch(self, cmd: ResponseCommand):
        action = cmd.action
        target = cmd.target

        log.info(f"Executing: {action} on '{target}' (event={cmd.event_id}, "
                 f"auth={cmd.authorized_by})")

        handlers = {
            "block_ip": self._block_ip,
            "unblock_ip": self._unblock_ip,
            "kill_process": self._kill_process,
            "isolate": self._isolate,
            "dismiss": self._dismiss,
        }

        handler = handlers.get(action)
        if handler:
            try:
                await handler(target)
            except Exception as e:
                log.error(f"Action '{action}' failed: {e}")
        else:
            log.warning(f"Unknown action: {action}")

    async def _block_ip(self, ip: str):
        """Drop all traffic from IP using iptables."""
        self._validate_ip(ip)
        await self._run(f"iptables -I INPUT -s {ip} -j DROP")
        await self._run(f"iptables -I OUTPUT -d {ip} -j DROP")
        log.info(f"Blocked IP: {ip}")

    async def _unblock_ip(self, ip: str):
        """Remove iptables block for IP."""
        self._validate_ip(ip)
        await self._run(f"iptables -D INPUT -s {ip} -j DROP", check=False)
        await self._run(f"iptables -D OUTPUT -d {ip} -j DROP", check=False)
        log.info(f"Unblocked IP: {ip}")

    async def _kill_process(self, target: str):
        """Send SIGKILL to a process by PID."""
        try:
            pid = int(target)
        except ValueError:
            log.error(f"Invalid PID: {target}")
            return

        # Safety: don't kill PID 1 or ourselves
        if pid <= 1:
            log.error(f"Refusing to kill PID {pid}")
            return

        await self._run(f"kill -9 {pid}", check=False)
        log.info(f"Killed PID: {pid}")

    async def _isolate(self, _target: str):
        """
        Network isolation: block everything except established connections
        and optionally SSH from trusted IP. Use with caution.
        """
        log.warning("ISOLATING HOST — blocking all new connections!")
        cmds = [
            "iptables -P INPUT DROP",
            "iptables -P FORWARD DROP",
            "iptables -P OUTPUT DROP",
            "iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT",
            "iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT",
            "iptables -A INPUT -i lo -j ACCEPT",
            "iptables -A OUTPUT -o lo -j ACCEPT",
        ]
        if self.trusted_ip:
            cmds += [
                f"iptables -A INPUT -s {self.trusted_ip} -p tcp --dport 22 -j ACCEPT",
                f"iptables -A OUTPUT -d {self.trusted_ip} -p tcp --sport 22 -j ACCEPT",
            ]
        for cmd in cmds:
            await self._run(cmd)
        log.warning("Host isolated. Run 'iptables -F' to restore connectivity.")

    async def _dismiss(self, _target: str):
        log.info("Alert dismissed (no action taken).")

    @staticmethod
    def _validate_ip(ip: str):
        """Prevent command injection in iptables calls."""
        parts = ip.split(".")
        if len(parts) != 4:
            raise ValueError(f"Invalid IP: {ip}")
        for part in parts:
            if not part.isdigit() or not 0 <= int(part) <= 255:
                raise ValueError(f"Invalid IP: {ip}")

    @staticmethod
    async def _run(cmd: str, check: bool = True):
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if check and proc.returncode != 0:
            raise RuntimeError(f"Command failed [{cmd}]: {stderr.decode().strip()}")
        return stdout.decode().strip()
