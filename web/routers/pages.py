from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import configparser
import os

from web.database import get_db
from web import models
from web.dependencies import check_admin
from core.security import create_access_token

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": ""})

@router.post("/login")
async def do_login(request: Request, username: str = Form(...), password: str = Form(...)):
    conf = configparser.ConfigParser()
    conf_path = "config.ini"
    if os.path.exists(conf_path):
        conf.read(conf_path, encoding="utf-8")
        
    admin_u = conf.get("WebAdmin", "username", fallback="admin")
    admin_p = conf.get("WebAdmin", "password", fallback="admin")
    
    if username == admin_u and password == admin_p:
        session_token = create_access_token({"sub": "admin"})
        res = RedirectResponse(url="/", status_code=303)
        res.set_cookie(key="admin_session", value=session_token, httponly=True)
        return res
    else:
        return templates.TemplateResponse("login.html", {"request": request, "error": "用户名或密码错误。"})

@router.get("/logout")
async def logout(request: Request):
    res = RedirectResponse(url="/login", status_code=303)
    res.delete_cookie("admin_session")
    return res

@router.get("/", response_class=HTMLResponse)
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

@router.get("/logs", response_class=HTMLResponse)
async def view_logs(request: Request, db: Session = Depends(get_db), _: bool = Depends(check_admin)):
    return templates.TemplateResponse("logs.html", {"request": request})
