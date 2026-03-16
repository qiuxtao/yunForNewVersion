from apscheduler.schedulers.background import BackgroundScheduler
import datetime
import logging
from sqlalchemy.orm import Session
import configparser
import os
import json
import random
import time

from web.database import SessionLocal
from web.models import Schedule, User, RunLog
from core.auth import AuthManager
from core.yun import YunCore
from notifications.qq_bot import notify_run_success, notify_run_failed

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()

# 为了避免在数据库里存所有的学校秘钥，目前从统一的config.ini读取学校API静态配置并供所有用户共用
# (如果系统要支持多个学校，这部分需要迁入数据库或者做个school_config表)
def load_app_config():
    conf = configparser.ConfigParser()
    conf_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.ini')
    conf.read(conf_path, encoding="utf-8")
    return conf

def run_job_for_user(user_id: int, schedule_id: int):
    logger.info(f"Starting schedule execution for user_id={user_id}, schedule_id={schedule_id}")
    db: Session = SessionLocal()
    user = db.query(User).filter(User.id == user_id).first()
    sched = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    
    if not user or not sched:
        db.close()
        return
        
    conf = load_app_config()
    
    # 提取公共APP参数
    school_host = conf.get("Yun", "school_host", fallback="")
    school_id = conf.get("Yun", "school_id", fallback="195")
    app_edition = conf.get("Yun", "app_edition", fallback="3.5.1")
    md5key = conf.get("Yun", "md5key", fallback="")
    platform = conf.get("Yun", "platform", fallback="android")
    school_name = conf.get("Yun", "school_name", fallback="")
    school_login_url = conf.get("Yun", "school_login_url", fallback="appLogin")
    
    public_key = conf.get("Yun", "PublicKey", fallback="")
    private_key = conf.get("Yun", "PrivateKey", fallback="")
    cipherkey = conf.get("Yun", "cipherkey", fallback="")
    cipherkeyencrypted = conf.get("Yun", "cipherkeyencrypted", fallback="")
    
    run_config = {
        "strides": conf.get("Run", "strides", fallback="0.8"),
        "single_mileage_min_offset": conf.get("Run", "single_mileage_min_offset", fallback="0.5"),
        "single_mileage_max_offset": conf.get("Run", "single_mileage_max_offset", fallback="-0.5"),
        "cadence_min_offset": conf.get("Run", "cadence_min_offset", fallback="30"),
        "cadence_max_offset": conf.get("Run", "cadence_max_offset", fallback="-150")
    }
    split_count = int(conf.get("Run", "split_count", fallback="10"))

    # Auth check & refresh validation 
    auth = AuthManager(user.device_id, user.device_name, user.sys_edition, app_edition, md5key, platform, cipherkey, cipherkeyencrypted)
    utc = str(int(time.time()))
    
    # 尝试登录以获取最新 Token 确保有效
    try:
        login_res = auth.login(user.yun_username, user.yun_password, school_id, school_host, school_login_url, user.uuid, utc)
        user.yun_token = login_res['token']
        db.commit()
    except Exception as e:
        error_msg = f"登录失败: {e}"
        logger.error(error_msg)
        add_log(db, user, "Failed", error_msg, sched)
        if user.qq_number:
            # 假设一个群可以绑定，目前暂时发到 qq_number (当做一个内部群处理或者私聊)
            notify_run_failed(user.qq_number, user.username, error_msg)
        return

    # 初始化 Yun Core
    core = YunCore(
        user.yun_token, user.device_id, user.device_name, user.uuid, "", utc, 
        school_host, school_id, app_edition, md5key, platform,
        public_key, private_key, cipherkey, cipherkeyencrypted, run_config
    )
    
    success, msg = core.init_run_info()
    if not success:
        error_msg = f"初始化运行参数失败: {msg}"
        add_log(db, user, "Failed", error_msg, sched)
        if user.qq_number: notify_run_failed(user.qq_number, user.username, error_msg)
        return

    success, msg = core.start_run()
    if not success:
        error_msg = f"创建跑步记录失败: {msg}"
        add_log(db, user, "Failed", error_msg, sched)
        if user.qq_number: notify_run_failed(user.qq_number, user.username, error_msg)
        return

    # Load Tasks Map
    path_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), sched.route_type)
    if not os.path.exists(path_dir):
        error_msg = f"找不到打卡路线文件夹: {path_dir}"
        add_log(db, user, "Failed", error_msg, sched)
        if user.qq_number: notify_run_failed(user.qq_number, user.username, error_msg)
        return

    files = [f for f in os.listdir(path_dir) if f.endswith('.json')]
    if not files:
        error_msg = f"文件夹 {path_dir} 中没有可用路线"
        add_log(db, user, "Failed", error_msg, sched)
        if user.qq_number: notify_run_failed(user.qq_number, user.username, error_msg)
        return

    # Randomly pick route
    file = os.path.join(path_dir, random.choice(files))
    with open(file, 'r', encoding='utf-8') as f:
        task_map = json.loads(f.read())
        
    # Apply coordinate drift (hardcoded true for bot automation for safety)
    from tools.drift import add_drift
    task_map = add_drift(task_map)

    # Begin Simulation points loop
    points = []
    count = 0
    total_points = len(task_map['data']['pointsList'])
    sleep_time = task_map['data']['duration'] / total_points * split_count

    logger.info(f"User {user.username} beginning automated run loop over {total_points} points.")
    for point in task_map['data']['pointsList']:
        points.append({
            'point': point['point'],
            'runStatus': '1',
            'speed': point['speed'],
            'isFence': 'Y',
            'isMock': False,
            "runMileage": point['runMileage'],
            "runTime": point['runTime'],
            "ts": str(int(time.time()))
        })
        count += 1
        if count == split_count:
            core.split_by_points_map(points, task_map['data']['recodePace'])
            time.sleep(sleep_time)
            count = 0
            points = []

    if count != 0:
        core.split_by_points_map(points, task_map['data']['recodePace'])

    # Finalize record
    res = core.finish_by_points_map(task_map)
    try:
        final_info = json.loads(res)
        if final_info.get("code") == 200:
            success_msg = f"结算响应: {res}"
            mileage = float(task_map['data']['recordMileage'])
            duration = float(task_map['data']['duration']) / 60.0
            add_log(db, user, "Success", success_msg, sched)
            if user.qq_number:
                notify_run_success(user.qq_number, user.username, mileage, duration)
        else:
            raise Exception(res)
    except Exception as e:
        error_msg = f"结算跑步成绩失败: {e}"
        add_log(db, user, "Failed", error_msg, sched)
        if user.qq_number: notify_run_failed(user.qq_number, user.username, error_msg)

def add_log(db: Session, user: User, status: str, message: str, sched: Schedule = None):
    log = RunLog(user_id=user.id, status=status, message=message[:500])
    db.add(log)
    if sched:
        sched.last_run_status = status
        sched.last_run_time = datetime.datetime.now()
    db.commit()
    db.close()

def scan_and_run_schedules():
    """
    Cron Job scheduled every minute. Scans Schedules for matches to current HH:MM.
    """
    now = datetime.datetime.now()
    current_time_str = now.strftime("%H:%M")
    
    db: Session = SessionLocal()
    # Find active users with due schedules
    due_schedules = db.query(Schedule).join(User).filter(
        User.is_active == True,
        Schedule.target_time == current_time_str
    ).all()
    
    for sched in due_schedules:
        # Prevent running twice in the same minute
        if sched.last_run_time and sched.last_run_time.strftime("%Y-%m-%d %H:%M") == now.strftime("%Y-%m-%d %H:%M"):
            continue
            
        logger.info(f"Triggering automated run for User {sched.user.username} at {current_time_str}")
        # Run in background via apscheduler executor
        scheduler.add_job(
            run_job_for_user,
            args=[sched.user_id, sched.id],
            misfire_grace_time=300
        )
    db.close()

def init_scheduler():
    scheduler.add_job(scan_and_run_schedules, 'cron', minute='*')
    scheduler.start()
