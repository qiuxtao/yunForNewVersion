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
    qq_notify_type: str = Form("private"),
    db: Session = Depends(get_db),
    _: bool = Depends(check_admin)
):
    device_id = str(random.randint(1000000000000000, 9999999999999999))
    uuid_str = device_id
    

    # 强制校验
    if not _validate_yun_sync(yun_username, yun_password):
        from fastapi.responses import HTMLResponse
        return HTMLResponse("<script>alert('【强制校验失败】账号或密码错误，或服务器网络异常。'); history.back();</script>")

    new_user = models.User(
        username=username,
        yun_username=yun_username,
        yun_password=yun_password,
        qq_number=qq_number,
        qq_notify_type=qq_notify_type,
        device_id=device_id,
        device_name="Xiaomi",
        uuid=uuid_str,
        sys_edition="14",
        is_active=True
    )
    db.add(new_user)
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.post("/users/edit")
async def edit_user(
    user_id: int = Form(...),
    username: str = Form(...),
    yun_username: str = Form(...),
    yun_password: str = Form(""),
    qq_number: str = Form(""),
    qq_notify_type: str = Form("private"),
    db: Session = Depends(get_db),
    _: bool = Depends(check_admin)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        # 强制校验
        pwd_to_check = yun_password if yun_password else user.yun_password
        if not _validate_yun_sync(yun_username, pwd_to_check):
            from fastapi.responses import HTMLResponse
            return HTMLResponse("<script>alert('【强制校验失败】账号或密码错误，或服务器网络异常。'); history.back();</script>")
            
        user.username = username
        user.yun_username = yun_username
        if yun_password:
            user.yun_password = yun_password
        user.qq_number = qq_number
        user.qq_notify_type = qq_notify_type
        db.commit()
    return RedirectResponse(url="/", status_code=303)

def _validate_yun_sync(yun_username, yun_password):
    import time as _time
    conf = configparser.ConfigParser()
    conf.read("config.ini", encoding="utf-8")
    school_host = conf.get("Yun", "school_host", fallback="")
    school_id = conf.get("Yun", "school_id", fallback="195")
    app_edition = conf.get("Yun", "app_edition", fallback="3.5.1")
    md5key = conf.get("Yun", "md5key", fallback="")
    platform_str = conf.get("Yun", "platform", fallback="android")
    school_login_url = conf.get("Yun", "school_login_url", fallback="appLogin")
    cipherkey = conf.get("Yun", "cipherkey", fallback="")
    cipherkeyencrypted = conf.get("Yun", "cipherkeyencrypted", fallback="")
    temp_device_id = str(random.randint(1000000000000000, 9999999999999999))
    utc = str(int(_time.time()))
    try:
        from core.auth import AuthManager
        auth = AuthManager(temp_device_id, "Xiaomi", "14", app_edition, md5key, platform_str, cipherkey, cipherkeyencrypted)
        login_res = auth.login(yun_username, yun_password, school_id, school_host, school_login_url, temp_device_id, utc)
        return bool(login_res and login_res.get("token"))
    except:
        return False

@app.post("/users/validate")
async def validate_user_credentials(
    yun_username: str = Form(...),
    yun_password: str = Form(...),
    _: bool = Depends(check_admin)
):
    """在添加/编辑用户前，实时验证云运动学号密码是否能正常登录"""
    import time as _time
    from fastapi.responses import JSONResponse
    conf = configparser.ConfigParser()
    conf.read("config.ini", encoding="utf-8")
    
    school_host = conf.get("Yun", "school_host", fallback="")
    school_id = conf.get("Yun", "school_id", fallback="195")
    app_edition = conf.get("Yun", "app_edition", fallback="3.5.1")
    md5key = conf.get("Yun", "md5key", fallback="")
    platform_str = conf.get("Yun", "platform", fallback="android")
    school_login_url = conf.get("Yun", "school_login_url", fallback="appLogin")
    cipherkey = conf.get("Yun", "cipherkey", fallback="")
    cipherkeyencrypted = conf.get("Yun", "cipherkeyencrypted", fallback="")
    
    temp_device_id = str(random.randint(1000000000000000, 9999999999999999))
    utc = str(int(_time.time()))
    
    try:
        from core.auth import AuthManager
        auth = AuthManager(temp_device_id, "Xiaomi", "14", app_edition, md5key, platform_str, cipherkey, cipherkeyencrypted)
        login_res = auth.login(yun_username, yun_password, school_id, school_host, school_login_url, temp_device_id, utc)
        if login_res and login_res.get("token"):
            return JSONResponse({"success": True, "message": "登录验证通过"})
        else:
            return JSONResponse({"success": False, "message": f"登录返回异常: {login_res}"})
    except Exception as e:
        return JSONResponse({"success": False, "message": f"登录失败: {str(e)}"})

@app.post("/schedules/add")
async def add_schedule(
    request: Request,
    target_time: str = Form(...),
    route_type: str = Form(...),
    db: Session = Depends(get_db),
    _: bool = Depends(check_admin)
):
    form_data = await request.form()
    user_ids = form_data.getlist("user_ids")
    for uid in user_ids:
        new_sched = models.Schedule(
            user_id=int(uid),
            target_time=target_time,
            route_type=route_type,
            last_run_status="Pending"
        )
        db.add(new_sched)
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.post("/schedules/edit")
async def edit_schedule(
    request: Request,
    schedule_id: int = Form(...),
    target_time: str = Form(...),
    route_type: str = Form(...),
    db: Session = Depends(get_db),
    _: bool = Depends(check_admin)
):
    form_data = await request.form()
    user_ids = form_data.getlist("user_ids")
    
    sched = db.query(models.Schedule).filter(models.Schedule.id == schedule_id).first()
    if sched:
        sched.target_time = target_time
        sched.route_type = route_type
    
    if user_ids:
        for uid in user_ids:
            uid_int = int(uid)
            existing_sched = db.query(models.Schedule).filter(models.Schedule.user_id == uid_int).first()
            if existing_sched:
                existing_sched.target_time = target_time
                existing_sched.route_type = route_type
            else:
                new_sched = models.Schedule(
                    user_id=uid_int,
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

@app.get("/api/users/{user_id}")
async def get_user_json(user_id: int, db: Session = Depends(get_db), _: bool = Depends(check_admin)):
    """给前端编辑弹窗提供用户详情的 JSON 接口"""
    from fastapi.responses import JSONResponse
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return JSONResponse({"error": "用户不存在"}, status_code=404)
    return JSONResponse({
        "id": user.id,
        "username": user.username,
        "yun_username": user.yun_username,
        "qq_number": user.qq_number or "",
        "qq_notify_type": user.qq_notify_type or "private",
    })

@app.get("/api/users/{user_id}/history")
async def get_user_history_json(user_id: int, db: Session = Depends(get_db), _: bool = Depends(check_admin)):
    import time as _time
    import configparser
    from fastapi.responses import JSONResponse
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return JSONResponse({"success": False, "message": "账户不存在"})
        
    conf = configparser.ConfigParser()
    conf.read("config.ini", encoding="utf-8")
    
    school_host = conf.get("Yun", "school_host", fallback="")
    school_id = conf.get("Yun", "school_id", fallback="195")
    app_edition = conf.get("Yun", "app_edition", fallback="3.5.1")
    md5key = conf.get("Yun", "md5key", fallback="")
    platform_str = conf.get("Yun", "platform", fallback="android")
    school_login_url = conf.get("Yun", "school_login_url", fallback="appLogin")
    
    public_key = conf.get("Yun", "PublicKey", fallback="")
    private_key = conf.get("Yun", "PrivateKey", fallback="")
    cipherkey = conf.get("Yun", "cipherkey", fallback="")
    cipherkeyencrypted = conf.get("Yun", "cipherkeyencrypted", fallback="")
    
    utc = str(int(_time.time()))
    try:
        from core.auth import AuthManager
        from core.yun import YunCore
        
        auth = AuthManager(user.device_id, user.device_name, user.sys_edition, app_edition, md5key, platform_str, cipherkey, cipherkeyencrypted)
        login_res = auth.login(user.yun_username, user.yun_password, school_id, school_host, school_login_url, user.uuid, utc)
        
        if not login_res or not login_res.get("token"):
            return JSONResponse({"success": False, "message": "云运动登录获取Token失败，请检查账号密码是否失效"})
            
        token = login_res["token"]
        yun = YunCore(token, user.device_id, user.device_name, user.uuid, "", utc,
                     school_host, school_id, app_edition, md5key, platform_str,
                     public_key, private_key, cipherkey, cipherkeyencrypted, {})
                     
        success, data = yun.get_recent_history()
        
        if not success:
            return JSONResponse({"success": False, "message": data})
            
        return JSONResponse({"success": True, "data": data})
        
    except Exception as e:
        return JSONResponse({"success": False, "message": f"内部服务器异常: {str(e)}"})

@app.get("/logs", response_class=HTMLResponse)
async def view_logs(request: Request, db: Session = Depends(get_db), _: bool = Depends(check_admin)):
    logs = db.query(models.RunLog).order_by(models.RunLog.id.desc()).limit(500).all()
    return templates.TemplateResponse("logs.html", {"request": request, "logs": logs})
