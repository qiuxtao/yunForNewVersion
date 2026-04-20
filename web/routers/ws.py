from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from notifications.qq_bot import manager

router = APIRouter()

@router.websocket("/ws/qqbot")
async def qqbot_ws(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
