"""
WebSocket endpoint — mobile app connects here to receive real-time alerts.
"""

import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from api.auth import verify_token

log = logging.getLogger("websocket")
router = APIRouter()


@router.websocket("/ws/{device_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    device_id: str,
    token: str = Query(...),
):
    # Verify token before accepting connection
    try:
        username = verify_token(token)
    except Exception:
        await websocket.close(code=4001)
        return

    from main import manager
    await manager.connect(device_id, websocket)
    log.info(f"WebSocket open: {device_id} (user={username})")

    try:
        while True:
            # Keep connection alive, wait for client messages
            data = await websocket.receive_text()
            log.debug(f"WS message from {device_id}: {data}")
    except WebSocketDisconnect:
        manager.disconnect(device_id)
        log.info(f"WebSocket closed: {device_id}")
