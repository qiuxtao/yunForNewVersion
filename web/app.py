from fastapi import FastAPI, Depends, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os
import random
import configparser
import uuid
import asyncio

from web.database import engine, get_db, init_db
from web import models
from scheduler.tasks import init_scheduler, run_job_for_user

from fastapi import WebSocket, WebSocketDisconnect
from notifications.qq_bot import manager

# Ensure templates and static dirs exist
os.makedirs("templates", exist_ok=True)
os.makedirs("static", exist_ok=True)

app = FastAPI(title="云运动 Web 控制台")

templates = Jinja2Templates(directory="templates")

active_sessions = set()

class NotAuthenticatedException(Exception):
    pass

@app.exception_handler(NotAuthenticatedException)
async def auth_exception_handler(request: Request, exc: NotAuthenticatedException):
    return RedirectResponse(url="/login")

def check_admin(request: Request):
    if request.cookies.get("admin_session") not in active_sessions:
        raise NotAuthenticatedException()
    return True

@app.on_event("startup")
def on_startup():
    init_db()
    print("Database initialized.")
    init_scheduler()
    print("APScheduler started.")
    try:
        manager.set_loop(asyncio.get_running_loop())
    except RuntimeError:
        pass

@app.websocket("/ws/qqbot")
async def qqbot_ws(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We must continuously receive messages to keep the connection alive
            # OneBot platforms will bounce heartbeats and API responses here
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": ""})

@app.post("/login")
async def do_login(request: Request, username: str = Form(...), password: str = Form(...)):
    conf = configparser.ConfigParser()
    conf_path = "config.ini"
    if os.path.exists(conf_path):
        conf.read(conf_path, encoding="utf-8")
        
    # Default admin credentials if not set in config.ini
    admin_u = conf.get("WebAdmin", "username", fallback="admin")
    admin_p = conf.get("WebAdmin", "password", fallback="admin")
    
    if username == admin_u and password == admin_p:
        session_token = uuid.uuid4().hex
        active_sessions.add(session_token)
        res = RedirectResponse(url="/", status_code=303)
        res.set_cookie(key="admin_session", value=session_token, httponly=True)
        return res
    else:
        return templates.TemplateResponse("login.html", {"request": request, "error": "用户名或密码错误。"})

@app.get("/logout")
async def logout(request: Request):
    token = request.cookies.get("admin_session")
    if token in active_sessions:
        active_sessions.remove(token)
    res = RedirectResponse(url="/login", status_code=303)
    res.delete_cookie("admin_session")
    return res

@app.get("/", response_class=HTMLResponse)
async def read_dashboard(request: Request, db: Session = Depends(get_db), _: bool = Depends(check_admin)):
    users = db.query(models.User).all()
    schedules = db.query(models.Schedule).all()
    logs = db.query(models.RunLog).order_by(models.RunLog.id.desc()).limit(20).all()
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "users": users,
        "schedules": schedules,
        "logs": logs
    })

@app.post("/users/add")
async def add_user(
    username: str = Form(...),
    yun_username: str = Form(...),
    yun_password: str = Form(...),
    qq_number: str = Form(""),
    db: Session = Depends(get_db),
    _: bool = Depends(check_admin)
):
    device_id = str(random.randint(1000000000000000, 9999999999999999))
    uuid_str = device_id
    
    new_user = models.User(
        username=username,
        yun_username=yun_username,
        yun_password=yun_password,
        qq_number=qq_number,
        device_id=device_id,
        device_name="Xiaomi",
        uuid=uuid_str,
        sys_edition="14",
        is_active=True
    )
    db.add(new_user)
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.post("/schedules/add")
async def add_schedule(
    user_id: int = Form(...),
    target_time: str = Form(...),
    route_type: str = Form(...),
    db: Session = Depends(get_db),
    _: bool = Depends(check_admin)
):
    new_sched = models.Schedule(
        user_id=user_id,
        target_time=target_time,
        route_type=route_type,
        last_run_status="Pending"
    )
    db.add(new_sched)
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.post("/runs/manual_trigger")
async def manual_trigger(
    user_id: int = Form(...),
    schedule_id: int = Form(...),
    _: bool = Depends(check_admin)
):
    from scheduler.tasks import scheduler
    scheduler.add_job(
        run_job_for_user,
        args=[user_id, schedule_id],
        misfire_grace_time=300
    )
    return RedirectResponse(url="/", status_code=303)

@app.post("/users/delete")
async def delete_user(user_id: int = Form(...), db: Session = Depends(get_db), _: bool = Depends(check_admin)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        db.delete(user)
        db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.post("/schedules/delete")
async def delete_schedule(schedule_id: int = Form(...), db: Session = Depends(get_db), _: bool = Depends(check_admin)):
    sched = db.query(models.Schedule).filter(models.Schedule.id == schedule_id).first()
    if sched:
        db.delete(sched)
        db.commit()
    return RedirectResponse(url="/", status_code=303)
