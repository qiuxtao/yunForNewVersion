from fastapi import FastAPI, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os
import random

from web.database import engine, get_db, init_db
from web import models
from scheduler.tasks import init_scheduler, run_job_for_user

# Ensure templates and static dirs exist
os.makedirs("templates", exist_ok=True)
os.makedirs("static", exist_ok=True)

app = FastAPI(title="云运动 Web 控制台")

templates = Jinja2Templates(directory="templates")

@app.on_event("startup")
def on_startup():
    init_db()
    print("Database initialized.")
    init_scheduler()
    print("APScheduler started.")
    
@app.get("/", response_class=HTMLResponse)
async def read_dashboard(request: Request, db: Session = Depends(get_db)):
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
    db: Session = Depends(get_db)
):
    # 生成安全的随机参数绑定
    device_id = str(random.randint(1000000000000000, 9999999999999999))
    uuid = device_id
    
    new_user = models.User(
        username=username,
        yun_username=yun_username,
        yun_password=yun_password,
        qq_number=qq_number,
        device_id=device_id,
        device_name="Xiaomi",
        uuid=uuid,
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
    db: Session = Depends(get_db)
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
):
    # 异步执行，不阻塞Web线程
    from scheduler.tasks import scheduler
    scheduler.add_job(
        run_job_for_user,
        args=[user_id, schedule_id],
        misfire_grace_time=300
    )
    return RedirectResponse(url="/", status_code=303)

@app.post("/users/delete")
async def delete_user(user_id: int = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        db.delete(user)
        db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.post("/schedules/delete")
async def delete_schedule(schedule_id: int = Form(...), db: Session = Depends(get_db)):
    sched = db.query(models.Schedule).filter(models.Schedule.id == schedule_id).first()
    if sched:
        db.delete(sched)
        db.commit()
    return RedirectResponse(url="/", status_code=303)
