#!/usr/bin/env python3
"""
Mobile SOC Console - Linux Agent
Monitors security events and executes response actions on command.
"""

import asyncio
import logging
import signal
import sys
from core.config import Config
from core.event_bus import EventBus
from core.broker_client import BrokerClient
from monitors.ssh_monitor import SSHMonitor
from monitors.process_monitor import ProcessMonitor
from monitors.network_monitor import NetworkMonitor
from monitors.log_monitor import LogMonitor
from responders.dispatcher import ResponseDispatcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/var/log/soc-agent.log"),
    ],
)
log = logging.getLogger("agent")


async def main():
    log.info("Starting Mobile SOC Agent...")

    config = Config.load("config.yaml")
    bus = EventBus()
    broker = BrokerClient(config.broker, bus)
    dispatcher = ResponseDispatcher(bus)

    monitors = [
        SSHMonitor(bus, config.monitors.get("ssh", {})),
        ProcessMonitor(bus, config.monitors.get("process", {})),
        NetworkMonitor(bus, config.monitors.get("network", {})),
        LogMonitor(bus, config.monitors.get("log", {})),
    ]

    # Graceful shutdown
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def _shutdown():
        log.info("Shutdown signal received.")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown)

    # Start all components concurrently
    tasks = [
        asyncio.create_task(broker.connect()),
        asyncio.create_task(dispatcher.listen()),
        *[asyncio.create_task(m.start()) for m in monitors],
    ]

    log.info(f"Agent running — {len(monitors)} monitors active.")
    await stop_event.wait()

    log.info("Stopping all tasks...")
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    log.info("Agent stopped.")


if __name__ == "__main__":
    asyncio.run(main())
