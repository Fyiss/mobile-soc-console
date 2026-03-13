"""
Commands API — mobile app POSTs response actions here.
Verifies JWT then forwards command to agent via MQTT.
"""

import logging
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional
from api.auth import verify_token

log = logging.getLogger("commands")
router = APIRouter()

VALID_ACTIONS = {"block_ip", "unblock_ip", "kill_process", "isolate", "dismiss"}


class CommandRequest(BaseModel):
    action: str
    target: str = ""
    event_id: str = ""


async def get_current_user(authorization: Optional[str] = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ")[1]
    return verify_token(token)


@router.post("/send")
async def send_command(
    req: CommandRequest,
    username: str = Depends(get_current_user),
):
    if req.action not in VALID_ACTIONS:
        raise HTTPException(status_code=400, detail=f"Invalid action: {req.action}")

    from main import bridge
    command = {
        "action": req.action,
        "target": req.target,
        "event_id": req.event_id,
        "authorized_by": username,
    }

    try:
        await bridge.publish_command(command)
        log.info(f"Command sent by {username}: {req.action} → {req.target}")
        return {"status": "sent", "command": command}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
