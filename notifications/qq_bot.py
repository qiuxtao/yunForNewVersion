import asyncio
import logging
import json
import configparser
import os
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_websockets = []
        self._loop = None

    def set_loop(self, loop):
        self._loop = loop

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_websockets.append(websocket)
        logger.info(f"OneBot Reverse WS connected! Total active: {len(self.active_websockets)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_websockets:
            self.active_websockets.remove(websocket)
            logger.info(f"OneBot Reverse WS disconnected. Remaining: {len(self.active_websockets)}")

    async def _send_action_async(self, action: str, params: dict):
        if not self.active_websockets:
            logger.warning("Attempted to send QQ message, but no OneBot WS clients are connected.")
            return False
            
        payload = {
            "action": action,
            "params": params
        }
        
        # Send to all connected clients (typically just 1)
        # Using a copy of the list in case of disconnects during iteration
        for ws in list(self.active_websockets):
            try:
                await ws.send_json(payload)
                logger.debug(f"Successfully pushed {action} to WS client.")
            except Exception as e:
                logger.error(f"Failed to send payload to WS: {e}")
                self.disconnect(ws)
        return True

    def send_action_sync(self, action: str, params: dict):
        """
        供非异步线程 (如 APScheduler 任务) 调用的同步壳
        会将异步发送挂载到 FastAPI启动的全局 event loop 中
        """
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._send_action_async(action, params), self._loop)
            return True
        else:
            logger.error("Event loop not set or not running in manager. Cannot send message.")
            return False

manager = ConnectionManager()

def send_group_msg(group_id: str, message: str):
    return manager.send_action_sync("send_group_msg", {
        "group_id": int(group_id),
        "message": message
    })

def send_private_msg(user_id: str, message: str):
    return manager.send_action_sync("send_private_msg", {
        "user_id": int(user_id),
        "message": message
    })

def notify_run_success(qq_number: str, notify_type: str, username: str, mileage: float, time_minutes: float):
    msg = f"✅ 云运动打卡成功\n👤 用户: {username}\n🏃 距离: {mileage} 公里\n⏱️ 用时: {time_minutes:.1f} 分钟\n🎉 辛苦了！"
    if notify_type == "group":
        send_group_msg(qq_number, msg)
    else:
        send_private_msg(qq_number, msg)

def notify_run_failed(qq_number: str, notify_type: str, username: str, reason: str):
    msg = f"❌ 云运动打卡失败\n👤 用户: {username}\n⚠️ 原因: {reason}\n请登录 Web 面板检查。"
    if notify_type == "group":
        send_group_msg(qq_number, msg)
    else:
        send_private_msg(qq_number, msg)
