from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import datetime
import logging
from sqlalchemy.orm import Session
import configparser
import os
import json
import random
import time
import sys

from web.database import SessionLocal
from web.models import Schedule, User, RunLog
from core.auth import AuthManager
from core.yun import YunCore
from notifications.qq_bot import notify_run_success as qq_notify_success, notify_run_failed as qq_notify_failed
from notifications.tg_bot import notify_run_success as tg_notify_success, notify_run_failed as tg_notify_failed

def _dispatch_notify_success(chat_id, notify_type, username, mileage, duration, stats_msg):
    if notify_type == "tgbot":
        tg_notify_success(chat_id, notify_type, username, mileage, duration, stats_msg)
    else:
        qq_notify_success(chat_id, notify_type, username, mileage, duration, stats_msg)

def _dispatch_notify_failed(chat_id, notify_type, username, error_msg):
    if notify_type == "tgbot":
        tg_notify_failed(chat_id, notify_type, username, error_msg)
    else:
        qq_notify_failed(chat_id, notify_type, username, error_msg)

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Shanghai'))

# 为了避免在数据库里存所有的学校秘钥，目前从统一的config.ini读取学校API静态配置并供所有用户共用
# (如果系统要支持多个学校，这部分需要迁入数据库或者做个school_config表)
def load_app_config():
    conf = configparser.ConfigParser()
    conf_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.ini')
    conf.read(conf_path, encoding="utf-8")
    return conf

def add_log(db: Session, user: User, status: str, message: str, sched: Schedule = None):
    log = RunLog(user_id=user.id, status=status, message=message)
    db.add(log)
    if sched:
        sched.last_run_status = status
        sched.last_run_time = datetime.datetime.now()
    db.commit()

def run_job_for_user(user_id: int, schedule_id: int):
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        sched = db.query(Schedule).filter(Schedule.id == schedule_id).first()
        
        if not user or not sched:
            return

        logger.info(f"[{user.yun_username}] 开始执行自动化跑步调度 (UserID: {user_id}, Name: {user.username})")
        conf = load_app_config()

        target_qq = user.qq_number
        target_notify_type = user.qq_notify_type
        if user.push_group_id and user.push_group:
            target_qq = user.push_group.qq_number
            target_notify_type = user.push_group.qq_notify_type
        
        # 提取公共APP参数
        school_host = getattr(user, "school_host", conf.get("Yun", "school_host", fallback=""))
        school_id = getattr(user, "school_id", conf.get("Yun", "school_id", fallback=""))
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
            "cadence_max_offset": conf.get("Run", "cadence_max_offset", fallback="-150"),
            "enable_coord_drift": conf.getboolean("Run", "enable_coord_drift", fallback=True),
            "enable_duration_random": conf.getboolean("Run", "enable_duration_random", fallback=True),
            "enable_cadence_random": conf.getboolean("Run", "enable_cadence_random", fallback=True)
        }
        split_count = int(conf.get("Run", "split_count", fallback="10"))

        # Auth check & refresh validation 
        auth = AuthManager(user.device_id, user.device_name, user.sys_edition, app_edition, md5key, platform, cipherkey, cipherkeyencrypted)
        utc = str(int(time.time()))
        
        try:
            login_res = auth.login(user.yun_username, user.yun_password, school_id, school_host, school_login_url, user.uuid, utc)
            user.yun_token = login_res['token']
            db.commit()
            logger.info(f"[{user.yun_username}] 登录云运动成功，Token: {user.yun_token[:8]}...")
        except Exception as e:
            error_msg = f"登录失败: {e}"
            logger.error(error_msg)
            add_log(db, user, "Failed", error_msg, sched)
            if target_qq:
                _dispatch_notify_failed(target_qq, target_notify_type, user.username, error_msg)
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
            logger.error(error_msg)
            add_log(db, user, "Failed", error_msg, sched)
            if target_qq: _dispatch_notify_failed(target_qq, target_notify_type, user.username, error_msg)
            return
        logger.info(f"[{user.yun_username}] 获取首页运行信息成功")

        success, msg = core.start_run()
        if not success:
            error_msg = f"创建跑步记录失败: {msg}"
            logger.error(error_msg)
            add_log(db, user, "Failed", error_msg, sched)
            if target_qq: _dispatch_notify_failed(target_qq, target_notify_type, user.username, error_msg)
            return
        start_run_time_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f"[{user.yun_username}] 开始跑步任务成功: {msg}")

        # Load Tasks Map
        path_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "tasks", sched.route_type)
        if not os.path.exists(path_dir):
            error_msg = f"找不到打卡路线文件夹: {path_dir}"
            logger.error(error_msg)
            add_log(db, user, "Failed", error_msg, sched)
            if target_qq: _dispatch_notify_failed(target_qq, target_notify_type, user.username, error_msg)
            return

        files = [f for f in os.listdir(path_dir) if f.endswith('.json')]
        if not files:
            error_msg = f"文件夹 {path_dir} 中没有可用路线"
            logger.error(error_msg)
            add_log(db, user, "Failed", error_msg, sched)
            if target_qq: _dispatch_notify_failed(target_qq, target_notify_type, user.username, error_msg)
            return

        file = os.path.join(path_dir, random.choice(files))
        with open(file, 'r', encoding='utf-8') as f:
            task_map = json.loads(f.read())
            
        from tools.drift import add_drift
        enable_coord_drift = run_config.get("enable_coord_drift", True)
        enable_duration_random = run_config.get("enable_duration_random", True)
        enable_cadence_random = run_config.get("enable_cadence_random", True)
        task_map = add_drift(task_map, enable_coord_drift, enable_duration_random, enable_cadence_random)

        points = []
        count = 0
        total_points = len(task_map['data']['pointsList'])
        sleep_time = task_map['data']['duration'] / total_points * split_count

        logger.info(f"[{user.yun_username}] 开始提交轨迹点... 共计 {total_points} 个点")
        
        start_t = time.time()
        for idx, point in enumerate(task_map['data']['pointsList']):
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
            # Checkpoint Progress Logger Without Terminal Clutter
            if (idx + 1) % max(1, total_points // 10) == 0 or (idx + 1) == total_points:
                pct = int((idx + 1) / total_points * 100)
                logger.info(f"[{user.yun_username}] 运行进度: {pct}% ({idx+1}/{total_points})")
                
            if count == split_count or (idx + 1) == total_points:
                try:
                    core.split_by_points_map(points, task_map['data']['recodePace'])
                except Exception as e:
                    pass
                if (idx + 1) < total_points:
                    time.sleep(sleep_time)
                count = 0
                points = []

        logger.info(f"[{user.yun_username}] 发送结束信号...")
        res = core.finish_by_points_map(task_map)
        try:
            final_info = json.loads(res)
            if final_info.get("code") == 200:
                end_run_time_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                logger.info(f"[{user.yun_username}] 结算成功: {res}")
                mileage = float(task_map['data']['recordMileage'])
                duration = float(task_map['data']['duration']) / 60.0
                # 获取该用户跑次统计数据
                total_runs = 0
                qualified_runs = 0
                try:
                    t_success, terms = core.get_terms()
                    if t_success and terms:
                        current_term = terms[0]['value']
                        h_success, h_data = core.get_term_history(current_term)
                        if h_success and isinstance(h_data, list):
                            total_runs = len(h_data)
                            qualified_runs = sum(1 for r in h_data if str(r.get('qualified', '')) == '1' or r.get('qualified') is True or str(r.get('isQualified', '')) == '1' or r.get('isQualified') is True or str(r.get('qualifiedStatus', '')) in ['1', '合格'])
                except Exception as e:
                    logger.warning(f"[{user.yun_username}] Failed to fetch history for notification: {e}")

                full_log_msg = f"开始时间: {start_run_time_str}\n结束时间: {end_run_time_str}\n结算数据: {res}"
                if total_runs > 0:
                    stats_msg = f"🏁 总计次数: {total_runs}次\n🎯 合格次数: {qualified_runs}次\n📅 开始时间: {start_run_time_str}\n⏳ 结束时间: {end_run_time_str}\n📄 结算数据: {res}"
                else:
                    stats_msg = f"📅 开始时间: {start_run_time_str}\n⏳ 结束时间: {end_run_time_str}\n📄 结算数据: {res}"

                add_log(db, user, "Success", full_log_msg, sched)
                if target_qq:
                    _dispatch_notify_success(target_qq, target_notify_type, user.username, mileage, duration, stats_msg)
            else:
                raise Exception(res)
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[{user.yun_username}] {error_msg}")
            add_log(db, user, "Failed", error_msg, sched)
            if target_qq: _dispatch_notify_failed(target_qq, target_notify_type, user.username, error_msg)
    finally:
        db.close()


def scan_and_run_schedules():
    """
    Cron Job scheduled every minute. Scans Schedules for matches to current HH:MM.
    """
    now = datetime.datetime.now()
    
    current_time_str = now.strftime("%H:%M")
    current_weekday = str(now.isoweekday())
    
    db: Session = SessionLocal()
    # Find active users with due and active schedules
    due_schedules = db.query(Schedule).join(User).filter(
        User.is_active == True,
        Schedule.is_active == True,
        Schedule.target_time == current_time_str
    ).all()
    
    for sched in due_schedules:
        # DB level Weekday filter validation
        if getattr(sched, 'run_days', None):
            allowed_days = [d.strip() for d in sched.run_days.split(',') if d.strip()]
            if allowed_days and current_weekday not in allowed_days:
                continue

        # Prevent running twice in the same minute
        if sched.last_run_time and sched.last_run_time.strftime("%Y-%m-%d %H:%M") == now.strftime("%Y-%m-%d %H:%M"):
            continue
            
        import random
        delay_secs = random.randint(0, sched.random_delay_minutes * 60) if sched.random_delay_minutes and sched.random_delay_minutes > 0 else 0
        
        if delay_secs > 0:
            import datetime as dt
            run_time = now + dt.timedelta(seconds=delay_secs)
            logger.info(f"Triggering automated run for User {sched.user.username} at {current_time_str} (Delayed randomly by {delay_secs//60}m {delay_secs%60}s to {run_time.strftime('%H:%M:%S')})")
            scheduler.add_job(
                run_job_for_user,
                'date',
                run_date=run_time,
                args=[sched.user_id, sched.id],
                misfire_grace_time=300 + delay_secs
            )
        else:
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
