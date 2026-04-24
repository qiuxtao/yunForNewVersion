from fastapi import FastAPI, Depends, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session
import os
import random
import configparser
import uuid
import asyncio
import json

from web.database import engine, get_db, init_db
from web import models
from jobs.tasks import init_scheduler, run_job_for_user

import sys
import os
from loguru import logger
from fastapi import WebSocket, WebSocketDisconnect
from notifications.qq_bot import manager

# ================= 极简日志初始化：核心必须最先运行 =================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "logs")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

SYSTEM_LOG_PATH = os.path.join(LOG_DIR, "system.log")

# 移除所有的标准库 logging 处理器，统一交由 loguru 接管
logger.remove()
# 终端输出保留彩色，过滤器剔除掉 APScheduler 无用信息和单纯的页面访问
logger.add(
    sys.stdout, 
    colorize=True, 
    format="<green>[{time:HH:mm:ss}]</green> <level>[{thread.name}/{level}]: {message}</level>",
    filter=lambda record: "apscheduler" not in record["name"] and "/login" not in record["message"]
)
# 文件落盘每日轮转，保留 30 天
logger.add(
    SYSTEM_LOG_PATH, 
    rotation="00:00", 
    retention="30 days", 
    format="[{time:YYYY-MM-DD HH:mm:ss}] [{thread.name}/{level}]: {message}",
    filter=lambda record: "apscheduler" not in record["name"]
)

import logging

# 拦截 uvicorn 和 fastapi 的默认日志输出到 loguru
class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"):
    l = logging.getLogger(name)
    l.handlers = [InterceptHandler()]
    l.propagate = False
# =============================================================



app = FastAPI(title="云运动 Web 控制台")
app.mount("/static", StaticFiles(directory="web/static"), name="static")

templates = Jinja2Templates(directory="web/templates")

# 中间件：尝试从请求头中获取真实真实公网 IP (兼容 Docker/代理环境)
@app.middleware("http")
async def get_real_ip_middleware(request: Request, call_next):
    # 优先检查常见的代理头
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        # X-Forwarded-For 可能包含多个 IP，取第一个
        real_ip = x_forwarded_for.split(",")[0].strip()
        # 猴子补丁修改 request.scope 里的 client，以便后续及日志调用能读取到真实 IP
        new_scope = request.scope.copy()
        new_scope["client"] = (real_ip, request.scope["client"][1])
        request._scope = new_scope
    else:
        x_real_ip = request.headers.get("x-real-ip")
        if x_real_ip:
            new_scope = request.scope.copy()
            new_scope["client"] = (x_real_ip, request.scope["client"][1])
            request._scope = new_scope
            
    response = await call_next(request)
    return response

from core.security import create_access_token, verify_token
from web.dependencies import NotAuthenticatedException

@app.exception_handler(NotAuthenticatedException)
async def auth_exception_handler(request: Request, exc: NotAuthenticatedException):
    return RedirectResponse(url="/login")

def check_admin(request: Request):
    token = request.cookies.get("admin_session")
    if not token or not verify_token(token):
        raise NotAuthenticatedException()
    return True

@app.on_event("startup")
def on_startup():
    init_db()
    l = logging.getLogger("uvicorn")
    l.info("Database initialized.")
    init_scheduler()
    l.info("APScheduler started.")
    try:
        manager.set_loop(asyncio.get_running_loop())
    except RuntimeError:
        pass

# WS router extracted
    
GLOBAL_SCHOOLS_CACHE = []

def load_schools_cache():
    global GLOBAL_SCHOOLS_CACHE
    if GLOBAL_SCHOOLS_CACHE: return
    import configparser
    conf = configparser.ConfigParser()
    conf.read("config.ini", encoding="utf-8")
    app_edition = conf.get("Yun", "app_edition", fallback="3.5.1")
    cipherkey = conf.get("Yun", "cipherkey", fallback="")
    cipherkeyencrypted = conf.get("Yun", "cipherkeyencrypted", fallback="")
    md5key = conf.get("Yun", "md5key", fallback="")
    from core.yun import YunCore
    suc, res = YunCore.get_global_schools(app_edition, cipherkey, cipherkeyencrypted, md5key)
    if suc:
        GLOBAL_SCHOOLS_CACHE = res


from web.routers import api, pages, ws

app.include_router(pages.router)
app.include_router(api.router)
app.include_router(ws.router)

