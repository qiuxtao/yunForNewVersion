import requests
import json
import logging
import os
import configparser

logger = logging.getLogger(__name__)

# 获取配置 (为了不硬编码密钥，从 config.ini 中的 [QQBot] 部分读取)
def _get_api_credentials():
    conf = configparser.ConfigParser()
    conf_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.ini')
    conf.read(conf_path, encoding="utf-8")
    
    app_id = conf.get("QQBot", "app_id", fallback="")
    client_secret = conf.get("QQBot", "client_secret", fallback="")
    
    # 是否是沙箱环境 (官方机器人未上线前，通常只能使用沙箱环境进行测试)
    is_sandbox = conf.getboolean("QQBot", "is_sandbox", fallback=True)
    
    base_url = "https://sandbox.api.sgroup.qq.com" if is_sandbox else "https://api.sgroup.qq.com"
    return app_id, client_secret, base_url

def _get_access_token():
    app_id, client_secret, _ = _get_api_credentials()
    if not app_id or not client_secret:
        logger.error("QQ Bot AppID or ClientSecret is not configured in config.ini")
        return None
        
    url = "https://bots.qq.com/app/getAppAccessToken"
    payload = {
        "appId": app_id,
        "clientSecret": client_secret
    }
    try:
        res = requests.post(url, json=payload, timeout=5)
        res_data = res.json()
        if "access_token" in res_data:
            return res_data["access_token"]
        else:
            logger.error(f"Failed to get QQ API access_token. Res: {res_data}")
            return None
    except Exception as e:
        logger.error(f"QQ API token request failed: {e}")
        return None

def send_group_msg(group_id: str, message: str):
    """
    发送群聊消息 (基于 QQ 官方开放平台群聊接口 v2)
    需要你的机器人在开放平台申请了对应的群聊权限
    """
    if not group_id or not message:
        return False
        
    access_token = _get_access_token()
    if not access_token:
        return False
        
    _, _, base_url = _get_api_credentials()
    
    # 官方群聊发消息 API (如果是频道发消息，API 会是 /channels/{channel_id}/messages)
    # 此处假定 user 传递的 group_id 就是 openid 关联的群的 group_openid 
    url = f"{base_url}/v2/groups/{group_id}/messages"
    
    headers = {
        "Authorization": f"QQBot {access_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "content": message,
        "msg_type": 0 # 文本消息
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=5)
        res_data = res.json()
        if res.status_code == 200 or res_data.get("id"):
            logger.info(f"Successfully sent group message to {group_id}")
            return True
        else:
            logger.error(f"Failed to send group message. Code: {res.status_code}, Response: {res_data}")
            return False
    except Exception as e:
        logger.error(f"Error calling QQ Bot API: {e}")
        return False

def notify_run_success(group_id: str, username: str, mileage: float, time_minutes: float):
    msg = f"✅ 云运动打卡成功\n👤 用户: {username}\n🏃 距离: {mileage} 公里\n⏱️ 用时: {time_minutes:.1f} 分钟\n🎉 辛苦了！"
    send_group_msg(group_id, msg)

def notify_run_failed(group_id: str, username: str, reason: str):
    msg = f"❌ 云运动打卡失败\n👤 用户: {username}\n⚠️ 原因: {reason}\n请登录 Web 面板检查。"
    send_group_msg(group_id, msg)
