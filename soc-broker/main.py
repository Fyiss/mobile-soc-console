#!/usr/bin/env python3
"""
Mobile SOC Console - Backend Broker
Bridges the Linux agent (MQTT) and the mobile app (WebSocket + REST).
"""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import Config
from core.mqtt_bridge import MQTTBridge
from core.connection_manager import ConnectionManager
from api.auth import router as auth_router
from api.commands import router as commands_router
from api.websocket import router as ws_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("broker")

config = Config.load("config.yaml")
manager = ConnectionManager()
bridge = MQTTBridge(config, manager)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting SOC Broker...")
    task = asyncio.create_task(bridge.start())
    yield
    log.info("Shutting down...")
    task.cancel()


app = FastAPI(title="Mobile SOC Broker", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth")
app.include_router(commands_router, prefix="/commands")
app.include_router(ws_router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "connected_clients": manager.count(),
        "mqtt": bridge.connected,
    }
