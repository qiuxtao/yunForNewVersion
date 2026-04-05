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
from scheduler.tasks import init_scheduler, run_job_for_user

from fastapi import WebSocket, WebSocketDisconnect
from notifications.qq_bot import manager
import sys
import os
import logging

# ================= 极简日志初始化：核心必须最先运行 =================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "logs")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

SYSTEM_LOG_PATH = os.path.join(LOG_DIR, "system.log")

class Tee(object):
    def __init__(self, name, mode, stream):
        self.file = open(name, mode, encoding='utf-8')
        self.stream = stream
    def write(self, data):
        self.file.write(data)
        self.file.flush()
        self.stream.write(data)
        self.stream.flush()
    def flush(self):
        self.file.flush()
        self.stream.flush()

# 先重定向标准流，保证在 logging 初始化之前生效
sys.stdout = Tee(SYSTEM_LOG_PATH, 'a', sys.stdout)
sys.stderr = Tee(SYSTEM_LOG_PATH, 'a', sys.stderr)

# 全局日志格式
LOG_FORMAT = '[%(asctime)s] [%(threadName)s/%(levelname)s]: %(message)s'
DATE_FORMAT = '%H:%M:%S'

# Tee 已将 stdout 重定向至 system.log，因此只需 StreamHandler(stdout) 即可实现
# 控制台输出 + 文件落盘的双写效果，无需额外 FileHandler（否则会导致日志双写）
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=DATE_FORMAT,
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)

# 屏蔽 APScheduler 每分钟生成的冗余执行日志状况+3
logging.getLogger('apscheduler').setLevel(logging.WARNING)

# 自定义过滤器，极致精简日志
class AccessLogFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        # 如果是 HTTP 请求记录（通常包含方法名）
        if any(m in msg for m in ["GET ", "POST ", "PUT ", "DELETE "]):
            # 仅保留登录相关的请求记录，其余全部静默
            return "/login" in msg
        # 非网络请求记录（如业务 INFO/ERROR）全部保留
        return True

class UvicornErrorFilter(logging.Filter):
    def filter(self, record):
        if "Invalid HTTP request received" in record.getMessage() or "Invalid HTTP request received." in record.getMessage():
            return False
        return True

for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
    l = logging.getLogger(name)
    l.handlers = []
    l.propagate = True
    if name == "uvicorn.access":
        l.addFilter(AccessLogFilter())
    elif name == "uvicorn.error":
        l.addFilter(UvicornErrorFilter())
# =============================================================

# Ensure templates and static dirs exist
os.makedirs("templates", exist_ok=True)
os.makedirs("static", exist_ok=True)

app = FastAPI(title="云运动 Web 控制台")

templates = Jinja2Templates(directory="templates")

active_sessions = set()

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
    l = logging.getLogger("uvicorn")
    l.info("Database initialized.")
    init_scheduler()
    l.info("APScheduler started.")
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

@app.get("/api/schools")
async def get_schools_api(_: bool = Depends(check_admin)):
    load_schools_cache()
    from fastapi.responses import JSONResponse
    return JSONResponse({"success": True, "data": GLOBAL_SCHOOLS_CACHE})

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
    push_groups = db.query(models.PushGroup).all()
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "users": users,
        "schedules": schedules,
        "logs": logs,
        "push_groups": push_groups
    })

@app.post("/users/add")
async def add_user(
    username: str = Form(...),
    yun_username: str = Form(...),
    yun_password: str = Form(...),
    school_id: str = Form("195"),
    db: Session = Depends(get_db),
    _: bool = Depends(check_admin)
):
    device_id = str(random.randint(1000000000000000, 9999999999999999))
    uuid_str = device_id
    
    school_name = "未知学校"
    school_host = "http://47.99.163.239:8080"
    load_schools_cache()
    for s in GLOBAL_SCHOOLS_CACHE:
        if str(s.get("schoolId", "")) == str(school_id):
            school_name = s.get("schoolName", "")
            school_host = s.get("schoolUrl", "").rstrip("/")
            break

    # 强制校验
    if not _validate_yun_sync(yun_username, yun_password, school_id, school_host):
        from fastapi.responses import HTMLResponse
        return HTMLResponse("<script>alert('【强制校验失败】账号或密码错误，或服务器网络异常。'); history.back();</script>")

    new_user = models.User(
        username=username,
        yun_username=yun_username,
        yun_password=yun_password,
        school_id=school_id,
        school_host=school_host,
        school_name=school_name,
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
    school_id: str = Form("195"),
    db: Session = Depends(get_db),
    _: bool = Depends(check_admin)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        school_name = "未知学校"
        school_host = "http://47.99.163.239:8080"
        load_schools_cache()
        for s in GLOBAL_SCHOOLS_CACHE:
            if str(s.get("schoolId", "")) == str(school_id):
                school_name = s.get("schoolName", "")
                school_host = s.get("schoolUrl", "").rstrip("/")
                break
                
        # 强制校验
        pwd_to_check = yun_password if yun_password else user.yun_password
        if not _validate_yun_sync(yun_username, pwd_to_check, school_id, school_host):
            from fastapi.responses import HTMLResponse
            return HTMLResponse("<script>alert('【强制校验失败】账号或密码错误，或服务器网络异常。'); history.back();</script>")
            
        user.username = username
        user.yun_username = yun_username
        user.school_id = school_id
        user.school_host = school_host
        user.school_name = school_name
        if yun_password:
            user.yun_password = yun_password
            
        db.commit()
    return RedirectResponse(url="/", status_code=303)

def _validate_yun_sync(yun_username, yun_password, school_id, school_host):
    import time as _time
    conf = configparser.ConfigParser()
    conf.read("config.ini", encoding="utf-8")
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
    school_id = Form("195"),
    _: bool = Depends(check_admin)
):
    """在添加/编辑用户前，实时验证云运动学号密码是否能正常登录"""
    import time as _time
    from fastapi.responses import JSONResponse
    
    school_name = "未知学校"
    school_host = "http://47.99.163.239:8080"
    load_schools_cache()
    for s in GLOBAL_SCHOOLS_CACHE:
        if str(s.get("schoolId", "")) == str(school_id):
            school_host = s.get("schoolUrl", "").rstrip("/")
            break

    conf = configparser.ConfigParser()
    conf.read("config.ini", encoding="utf-8")
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

@app.post("/test_qq_notify")
async def test_qq_notify(
    qq_number: str = Form(...),
    qq_notify_type: str = Form("private"),
    _: bool = Depends(check_admin)
):
    from fastapi.responses import JSONResponse
    from notifications.qq_bot import notify_run_success
    
    if not qq_number:
        return JSONResponse({"success": False, "message": "无 QQ 号"})
        
    try:
        notify_run_success(qq_number, qq_notify_type, "测试连通性账户", 1.23, 10.5)
        return JSONResponse({"success": True, "message": "测试推送信号已提交，请注意查收"})
    except Exception as e:
        return JSONResponse({"success": False, "message": f"测试推送失败: {e}"})

@app.post("/schedules/add")
async def add_schedule(
    request: Request,
    group_name: str = Form("未命名任务组"),
    target_time: str = Form(...),
    route_type: str = Form(...),
    random_delay_minutes: int = Form(0),
    db: Session = Depends(get_db),
    _: bool = Depends(check_admin)
):
    form_data = await request.form()
    user_ids = form_data.getlist("user_ids")
    run_days_list = form_data.getlist("run_days")
    run_days_str = ",".join(run_days_list) if run_days_list else "1,2,3,4,5,6,7"
    import uuid
    group_id = str(uuid.uuid4())[:8]
    
    for uid_str in user_ids:
        sched = models.Schedule(
            user_id=int(uid_str),
            group_id=group_id,
            group_name=group_name,
            target_time=target_time,
            route_type=route_type,
            run_days=run_days_str,
            random_delay_minutes=random_delay_minutes,
            last_run_status="Pending",
            is_active=True
        )
        db.add(sched)
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.post("/schedules/edit")
async def edit_schedule_group(
    request: Request,
    group_id: str = Form(...),
    group_name: str = Form("未命名任务组"),
    target_time: str = Form(...),
    route_type: str = Form(...),
    random_delay_minutes: int = Form(0),
    db: Session = Depends(get_db),
    _: bool = Depends(check_admin)
):
    form_data = await request.form()
    new_user_ids = set([int(uid) for uid in form_data.getlist("user_ids")])
    run_days_list = form_data.getlist("run_days")
    run_days_str = ",".join(run_days_list) if run_days_list else "1,2,3,4,5,6,7"
    
    existing_scheds = db.query(models.Schedule).filter(models.Schedule.group_id == group_id).all()
    existing_user_ids = set([s.user_id for s in existing_scheds])
    
    for s in existing_scheds:
        if s.user_id not in new_user_ids:
            db.delete(s)
        else:
            s.group_name = group_name
            s.target_time = target_time
            s.route_type = route_type
            s.run_days = run_days_str
            s.random_delay_minutes = random_delay_minutes
            
    for uid in new_user_ids - existing_user_ids:
        new_sched = models.Schedule(
            user_id=uid,
            group_id=group_id,
            group_name=group_name,
            target_time=target_time,
            route_type=route_type,
            run_days=run_days_str,
            random_delay_minutes=random_delay_minutes,
            last_run_status="Pending",
            is_active=True
        )
        db.add(new_sched)
        
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.post("/runs/manual_trigger")
async def manual_trigger_single(
    schedule_id: int = Form(...),
    db: Session = Depends(get_db),
    _: bool = Depends(check_admin)
):
    from scheduler.tasks import scheduler, run_job_for_user
    s = db.query(models.Schedule).filter(models.Schedule.id == schedule_id).first()
    if s:
        scheduler.add_job(
            run_job_for_user,
            args=[s.user_id, s.id],
            misfire_grace_time=300
        )
    return RedirectResponse(url="/", status_code=303)

@app.post("/schedules/run")
async def run_schedule(
    user_id: int = Form(...),
    group_id: str = Form(""),
    db: Session = Depends(get_db),
    _: bool = Depends(check_admin)
):
    from scheduler.tasks import run_job_for_user
    import threading
    t = threading.Thread(target=run_job_for_user, args=(user_id, group_id))
    t.start()
    return RedirectResponse(url="/", status_code=303)

# ================= Push Groups Management APIs =================
from typing import List

class PushGroupSchema(BaseModel):
    name: str
    qq_number: str
    qq_notify_type: str
    user_ids: List[int] = []

@app.post("/api/push_groups")
async def create_push_group(data: PushGroupSchema, db: Session = Depends(get_db), _: bool = Depends(check_admin)):
    group = models.PushGroup(name=data.name, qq_number=data.qq_number, qq_notify_type=data.qq_notify_type)
    db.add(group)
    db.flush()
    if data.user_ids:
        db.query(models.User).filter(models.User.id.in_(data.user_ids)).update({models.User.push_group_id: group.id}, synchronize_session=False)
    db.commit()
    return {"success": True}

@app.put("/api/push_groups/{group_id}")
async def update_push_group(group_id: int, data: PushGroupSchema, db: Session = Depends(get_db), _: bool = Depends(check_admin)):
    group = db.query(models.PushGroup).filter(models.PushGroup.id == group_id).first()
    if not group: return {"success": False, "msg": "未找到"}
    group.name = data.name
    group.qq_number = data.qq_number
    group.qq_notify_type = data.qq_notify_type
    
    # Update foreign keys
    db.query(models.User).filter(models.User.push_group_id == group.id).update({models.User.push_group_id: None}, synchronize_session=False)
    if data.user_ids:
        db.query(models.User).filter(models.User.id.in_(data.user_ids)).update({models.User.push_group_id: group.id}, synchronize_session=False)
        
    db.commit()
    return {"success": True}
    
@app.delete("/api/push_groups/{group_id}")
async def delete_push_group(group_id: int, db: Session = Depends(get_db), _: bool = Depends(check_admin)):
    group = db.query(models.PushGroup).filter(models.PushGroup.id == group_id).first()
    if group:
        # 解绑相关用户
        db.query(models.User).filter(models.User.push_group_id == group_id).update({models.User.push_group_id: None})
        db.delete(group)
        db.commit()
    return {"success": True}

class TestPushSchema(BaseModel):
    qq_number: str
    qq_notify_type: str

@app.post("/api/push_groups/test")
async def test_push_group(data: TestPushSchema, _: bool = Depends(check_admin)):
    try:
        if data.qq_notify_type == "tgbot":
            from notifications.tg_bot import _send_tg_message, get_tg_config
            tg_token, tg_proxy = get_tg_config()
            if not tg_token:
                return {"success": False, "msg": "config.ini 中未配置 [TGBot] token"}
            _send_tg_message(data.qq_number, tg_token, "✅ 这是一条来自云运动控制台的测试推送消息。", tg_proxy)
        else:
            from notifications.qq_bot import send_private_msg, send_group_msg
            msg = "✅ 这是一条来自云运动控制台的测试推送消息。"
            if data.qq_notify_type == "group":
                send_group_msg(data.qq_number, msg)
            else:
                send_private_msg(data.qq_number, msg)
        return {"success": True}
    except Exception as e:
        return {"success": False, "msg": str(e)}
# ==============================================================

@app.post("/users/delete")
async def delete_user(user_id: int = Form(...), db: Session = Depends(get_db), _: bool = Depends(check_admin)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        db.delete(user)
        db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.post("/schedules/delete_group")
async def delete_schedule_group(group_id: str = Form(...), db: Session = Depends(get_db), _: bool = Depends(check_admin)):
    scheds = db.query(models.Schedule).filter(models.Schedule.group_id == group_id).all()
    for s in scheds:
        db.delete(s)
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.post("/api/schedules/{schedule_id}/toggle_active")
async def toggle_schedule_active(schedule_id: int, db: Session = Depends(get_db), _: bool = Depends(check_admin)):
    from fastapi.responses import JSONResponse
    sched = db.query(models.Schedule).filter(models.Schedule.id == schedule_id).first()
    if sched:
        sched.is_active = not sched.is_active
        db.commit()
        return JSONResponse({"success": True, "new_state": sched.is_active})
    return JSONResponse({"success": False, "message": "Task not found"})

@app.get("/api/schedules")
async def get_schedules_json(db: Session = Depends(get_db), _: bool = Depends(check_admin)):
    """获取所有定时任务的 JSON 列表"""
    from fastapi.responses import JSONResponse
    try:
        schedules = db.query(models.Schedule).all()
        results = []
        for s in schedules:
            results.append({
                "id": s.id,
                "user_id": s.user_id,
                "username": s.user.username if s.user else "Unknown",
                "target_time": s.target_time,
                "route_type": s.route_type,
                "random_delay_minutes": s.random_delay_minutes,
                "last_run_status": s.last_run_status,
                "last_run_time": s.last_run_time.strftime('%Y-%m-%d %H:%M:%S') if s.last_run_time else '-',
                "group_id": s.group_id,
                "group_name": getattr(s, 'group_name', '未命名任务组'),
                "run_days": getattr(s, 'run_days', '1,2,3,4,5,6,7'),
                "is_active": s.is_active
            })
        return JSONResponse({"success": True, "data": results})
    except Exception as e:
        return JSONResponse({"success": False, "message": f"加载任务数据失败: {e}"})


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
        "school_id": getattr(user, "school_id", "195"),
    })

@app.post("/api/logs/clear")
async def clear_system_logs(_: bool = Depends(check_admin)):
    import os
    from fastapi.responses import JSONResponse
    try:
        log_path = SYSTEM_LOG_PATH
        if os.path.exists(log_path):
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("")
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)})

@app.post("/api/users/{user_id}/logs/clear")
async def clear_local_user_logs(user_id: int, db: Session = Depends(get_db), _: bool = Depends(check_admin)):
    from fastapi.responses import JSONResponse
    try:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if user:
            for log in user.run_logs:
                db.delete(log)
            db.commit()
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)})

@app.get("/api/users/{user_id}/terms")
async def get_user_terms_json(user_id: int, db: Session = Depends(get_db), _: bool = Depends(check_admin)):
    import time as _time
    import configparser
    from fastapi.responses import JSONResponse
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return JSONResponse({"success": False, "message": "账户不存在"})
        
    conf = configparser.ConfigParser()
    conf.read("config.ini", encoding="utf-8")
    
    school_host = getattr(user, "school_host", conf.get("Yun", "school_host", fallback=""))
    school_id = getattr(user, "school_id", conf.get("Yun", "school_id", fallback="195"))
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
            return JSONResponse({"success": False, "message": "云运动登录获取Token失败"})
            
        token = login_res["token"]
        yun = YunCore(token, user.device_id, user.device_name, user.uuid, "", utc,
                     school_host, school_id, app_edition, md5key, platform_str,
                     public_key, private_key, cipherkey, cipherkeyencrypted, {})
                     
        success, data = yun.get_terms()
        if not success:
            return JSONResponse({"success": False, "message": data})
            
        return JSONResponse({"success": True, "data": data, "token": token}) # optionally return token so the frontend doesn't login twice!
        
    except Exception as e:
        return JSONResponse({"success": False, "message": f"内部服务器异常: {str(e)}"})

@app.get("/api/users/{user_id}/history_by_term")
async def get_user_history_by_term_json(user_id: int, term_value: str, token: str, db: Session = Depends(get_db), _: bool = Depends(check_admin)):
    import time as _time
    import configparser
    from fastapi.responses import JSONResponse
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return JSONResponse({"success": False, "message": "账户不存在"})
        
    conf = configparser.ConfigParser()
    conf.read("config.ini", encoding="utf-8")
    
    school_host = getattr(user, "school_host", conf.get("Yun", "school_host", fallback=""))
    school_id = getattr(user, "school_id", conf.get("Yun", "school_id", fallback="195"))
    app_edition = conf.get("Yun", "app_edition", fallback="3.5.1")
    md5key = conf.get("Yun", "md5key", fallback="")
    platform_str = conf.get("Yun", "platform", fallback="android")
    
    public_key = conf.get("Yun", "PublicKey", fallback="")
    private_key = conf.get("Yun", "PrivateKey", fallback="")
    cipherkey = conf.get("Yun", "cipherkey", fallback="")
    cipherkeyencrypted = conf.get("Yun", "cipherkeyencrypted", fallback="")
    
    try:
        from core.yun import YunCore
        yun = YunCore(token, user.device_id, user.device_name, user.uuid, "", str(int(_time.time())),
                     school_host, school_id, app_edition, md5key, platform_str,
                     public_key, private_key, cipherkey, cipherkeyencrypted, {})
                     
        success, data = yun.get_term_history(term_value)
        if not success:
            return JSONResponse({"success": False, "message": data})
            
        return JSONResponse({"success": True, "data": data})
        
    except Exception as e:
        return JSONResponse({"success": False, "message": f"内部服务器异常: {str(e)}"})

@app.get("/api/users/{user_id}/history_detail")
async def get_user_history_detail(user_id: int, term_value: str, run_id: str, token: str, db: Session = Depends(get_db), _: bool = Depends(check_admin)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return JSONResponse({"success": False, "message": "User not found."})
        
    conf = configparser.ConfigParser()
    conf.read("config.ini", encoding="utf-8")
    school_host = getattr(user, "school_host", conf.get("Yun", "school_host", fallback=""))
    school_id = getattr(user, "school_id", conf.get("Yun", "school_id", fallback="195"))
    app_edition = conf.get("Yun", "app_edition", fallback="3.5.1")
    md5key = conf.get("Yun", "md5key", fallback="")
    platform_str = conf.get("Yun", "platform", fallback="android")
    public_key = conf.get("Yun", "PublicKey", fallback="")
    private_key = conf.get("Yun", "PrivateKey", fallback="")
    cipherkey = conf.get("Yun", "cipherkey", fallback="")
    cipherkeyencrypted = conf.get("Yun", "cipherkeyencrypted", fallback="")
    
    try:
        from core.yun import YunCore
        import time as _time
        yun = YunCore(token, user.device_id, user.device_name, user.uuid, "", str(int(_time.time())),
                     school_host, school_id, app_edition, md5key, platform_str,
                     public_key, private_key, cipherkey, cipherkeyencrypted, {})
                     
        success, data = yun.get_run_detail(run_id, term_value)
        if not success:
            return JSONResponse({"success": False, "message": str(data)})
            
        return JSONResponse({"success": True, "data": data})
        
    except Exception as e:
        return JSONResponse({"success": False, "message": f"内部服务器异常: {str(e)}"})

@app.get("/api/route_groups")
async def list_route_groups(_: bool = Depends(check_admin)):
    try:
        groups = []
        base_dir = "data/tasks"
        os.makedirs(base_dir, exist_ok=True)
        for item in os.listdir(base_dir):
            item_path = os.path.join(base_dir, item)
            # 实时检查路径是否存在且为目录，防止手动删除引发 FileNotFoundError
            if os.path.exists(item_path) and os.path.isdir(item_path):
                files_info = []
                try:
                    for f in os.listdir(item_path):
                        if f.endswith('.json'):
                            path = os.path.join(item_path, f)
                            if not os.path.exists(path):
                                continue
                            size = os.path.getsize(path)
                            duration = 0
                            recode_pace = 0
                            try:
                                with open(path, 'r', encoding='utf-8') as jf:
                                    jdata = json.load(jf)
                                    res_data = jdata.get("data", {})
                                    duration = float(res_data.get("duration", 0)) / 60.0
                                    recode_pace = float(res_data.get("recodePace", 0))
                            except Exception:
                                pass
                            files_info.append({
                                "filename": f,
                                "size_kb": round(size / 1024, 2),
                                "duration": duration,
                                "recode_pace": recode_pace
                            })
                except (OSError, IOError):
                    # 如果读取子目录失败（例如权限或并在循环中被删除），跳过该组
                    continue
                    
                groups.append({
                    "name": item, 
                    "count": len(files_info),
                    "routes": files_info
                })
        return JSONResponse({"success": True, "data": groups})
    except Exception as e:
        return JSONResponse({"success": False, "message": f"获取路线组失败: {str(e)}"})

class RouteGroupCreate(BaseModel):
    name: str

@app.post("/api/route_groups")
async def create_route_group(req: RouteGroupCreate, _: bool = Depends(check_admin)):
    name = req.name.strip()
    if ".." in name or "/" in name or "\\" in name:
        return JSONResponse({"success": False, "message": "非法名称"})
    
    group_path = os.path.join("data/tasks", name)
    if os.path.exists(group_path):
        return JSONResponse({"success": False, "message": "该线路组已存在"})
    os.makedirs(group_path)
    return JSONResponse({"success": True})

@app.get("/api/route_groups/{group_name}")
async def list_routes_in_group(group_name: str, _: bool = Depends(check_admin)):
    if ".." in group_name:
        return JSONResponse({"success": False, "message": "非法的线路组名"})
    group_path = os.path.join("data/tasks", group_name)
    if not os.path.exists(group_path):
        return JSONResponse({"success": False, "message": "线路组不存在"})
        
    files = []
    for f in os.listdir(group_path):
        if f.endswith(".json"):
            path = os.path.join(group_path, f)
            size = os.path.getsize(path)
            
            duration = 0
            recode_pace = 0
            try:
                with open(path, 'r', encoding='utf-8') as jf:
                    jdata = json.load(jf)
                    res_data = jdata.get("data", {})
                    duration = float(res_data.get("duration", 0)) / 60.0
                    recode_pace = float(res_data.get("recodePace", 0))
            except Exception:
                pass
                
            files.append({
                "filename": f, 
                "size_kb": round(size / 1024, 2),
                "duration": duration,
                "recode_pace": recode_pace
            })
    return JSONResponse({"success": True, "data": files})

@app.get("/api/route_groups/{group_name}/{filename}")
async def get_route_file_detail(group_name: str, filename: str, _: bool = Depends(check_admin)):
    if ".." in group_name or ".." in filename:
        return JSONResponse({"success": False, "message": "非法路径"})
    group_path = os.path.join("data/tasks", group_name)
    path = os.path.join(group_path, filename)
    if not os.path.exists(path):
        return JSONResponse({"success": False, "message": "线路不存在"})
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return JSONResponse({"success": True, "data": data})
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)})

class RouteSaveReq(BaseModel):
    filename: str
    content: dict

@app.post("/api/route_groups/{group_name}/save")
async def save_route_to_group(group_name: str, req: RouteSaveReq, _: bool = Depends(check_admin)):
    if ".." in group_name or ".." in req.filename:
        return JSONResponse({"success": False, "message": "非法路径"})
    group_path = os.path.join("data/tasks", group_name)
    if not os.path.exists(group_path):
        os.makedirs(group_path)
    fname = req.filename if req.filename.endswith('.json') else f"{req.filename}.json"
    path = os.path.join(group_path, fname)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(req.content, f, ensure_ascii=False, indent=2)
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)})

class RouteRenameReq(BaseModel):
    new_name: str

class GroupRenameReq(BaseModel):
    new_name: str

@app.post("/api/route_groups/{group_name}/rename_group")
async def rename_route_group(group_name: str, req: GroupRenameReq, db: Session = Depends(get_db), _: bool = Depends(check_admin)):
    import urllib.parse
    old_path = os.path.join("data/tasks", urllib.parse.unquote(group_name))
    new_name = req.new_name.strip()
    if ".." in group_name or ".." in new_name or "/" in new_name or "\\" in new_name:
        return JSONResponse({"success": False, "message": "非法名称"})
    
    new_path = os.path.join("data/tasks", new_name)
    if not os.path.exists(old_path):
        return JSONResponse({"success": False, "message": "原线路组不存在"})
    if os.path.exists(new_path):
        return JSONResponse({"success": False, "message": "目标名称已存在"})
        
    try:
        os.rename(old_path, new_path)
        db.query(models.Schedule).filter(models.Schedule.route_type == group_name).update({"route_type": new_name})
        db.commit()
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)})

@app.post("/api/route_groups/{group_name}/{filename}/rename")
async def rename_route_in_group(group_name: str, filename: str, req: RouteRenameReq, _: bool = Depends(check_admin)):
    if ".." in group_name or ".." in filename or ".." in req.new_name:
        return JSONResponse({"success": False, "message": "非法路径"})
    group_path = os.path.join("data/tasks", group_name)
    old_path = os.path.join(group_path, filename)
    new_fname = req.new_name if req.new_name.endswith('.json') else f"{req.new_name}.json"
    new_path = os.path.join(group_path, new_fname)
    if not os.path.exists(old_path):
        return JSONResponse({"success": False, "message": "原线路不存在"})
    try:
        os.rename(old_path, new_path)
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)})

@app.delete("/api/route_groups/{group_name}/{filename}")
async def delete_route_in_group(group_name: str, filename: str, _: bool = Depends(check_admin)):
    if ".." in group_name or ".." in filename:
        return JSONResponse({"success": False, "message": "非法路径"})
    group_path = os.path.join("data/tasks", group_name)
    path = os.path.join(group_path, filename)
    if os.path.exists(path):
        os.remove(path)
        return JSONResponse({"success": True})
    return JSONResponse({"success": False, "message": "线路不存在"})

@app.delete("/api/route_groups/{group_name}")
async def delete_route_group_entire(group_name: str, _: bool = Depends(check_admin)):
    if ".." in group_name:
        return JSONResponse({"success": False, "message": "非法路径"})
    import shutil
    group_path = os.path.join("data/tasks", group_name)
    if os.path.exists(group_path):
        try:
            shutil.rmtree(group_path)
            return JSONResponse({"success": True})
        except OSError:
            # Fallback for protected directories if any
            try:
                for f in os.listdir(group_path):
                    path = os.path.join(group_path, f)
                    if os.path.isfile(path):
                        os.remove(path)
                return JSONResponse({"success": True})
            except Exception as e2:
                return JSONResponse({"success": False, "message": f"清空线路组内容失败: {e2}"})
        except Exception as e:
            return JSONResponse({"success": False, "message": f"删除失败: {e}"})
    return JSONResponse({"success": False, "message": "线路组不存在"})

@app.get("/logs", response_class=HTMLResponse)
async def view_logs(request: Request, db: Session = Depends(get_db), _: bool = Depends(check_admin)):
    return templates.TemplateResponse("logs.html", {"request": request})

@app.get("/api/logs/stream")
async def stream_logs_json(_: bool = Depends(check_admin)):
    log_path = SYSTEM_LOG_PATH
    if not os.path.exists(log_path):
        return {"success": True, "data": "暂无系统日志..."}
        
    try:
        # 读取最后 1000 行，提供更充裕的网页端查看量
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            return {"success": True, "data": "".join(lines[-1000:])}
    except Exception as e:
        return {"success": False, "data": f"读取日志错误: {e}"}

@app.get("/api/users/{user_id}/local_logs")
async def get_user_local_logs(user_id: int, limit: int = 50, db: Session = Depends(get_db), _: bool = Depends(check_admin)):
    logs = db.query(models.RunLog).filter(models.RunLog.user_id == user_id).order_by(models.RunLog.id.desc()).limit(limit).all()
    data = []
    for l in logs:
        data.append({
            "id": l.id,
            "status": l.status,
            "run_time": l.run_time.strftime("%Y-%m-%d %H:%M:%S") if l.run_time else "",
            "message": l.message
        })
    return {"success": True, "data": data}
