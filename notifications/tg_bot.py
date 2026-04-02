import logging
import requests
import configparser
import os

logger = logging.getLogger(__name__)

def get_tg_token():
    conf = configparser.ConfigParser()
    conf_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.ini')
    conf.read(conf_path, encoding="utf-8")
    return conf.get("TGBot", "token", fallback="")

def notify_run_success(chat_id: str, notify_type: str, username: str, mileage: float, time_minutes: float, raw_res: str = ""):
    tg_token = get_tg_token()
    if not tg_token:
        logger.warning("Telegram Bot Token is not configured in config.ini [TGBot].")
        return
    text = f"✅ 【云运动打卡成功】\n👤 账号: {username}\n🏃 距离: {mileage} 公里\n⏱️ 用时: {time_minutes:.1f} 分钟\n{raw_res}"
    _send_tg_message(chat_id, tg_token, text)

def notify_run_failed(chat_id: str, notify_type: str, username: str, msg: str):
    tg_token = get_tg_token()
    if not tg_token:
        logger.warning("Telegram Bot Token is not configured in config.ini [TGBot].")
        return
    text = f"❌ 【云运动打卡失败】\n👤 账号: {username}\n{msg}"
    _send_tg_message(chat_id, tg_token, text)
    
def _send_tg_message(chat_id: str, tg_token: str, text: str):
    url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            logger.info(f"Telegram notification sent successfully to {chat_id}")
        else:
            logger.error(f"Telegram API Error: {resp.text}")
    except Exception as e:
        logger.error(f"Failed to push to Telegram: {e}")
