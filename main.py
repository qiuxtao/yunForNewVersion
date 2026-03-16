import configparser
import os
import time
from tqdm import tqdm
from core.auth import AuthManager
from core.yun import YunCore
import argparse
import random
import json

def parse_args():
    parser = argparse.ArgumentParser(description='云运动自动跑步脚本')
    parser.add_argument('-f', '--config_path', type=str, default='./config.ini', help='配置文件路径')
    parser.add_argument('-t', '--task_path', type=str, default='./tasks_else', help='任务文件路径')
    parser.add_argument('-a', '--auto_run', action='store_true', help='自动跑步，默认打表')
    parser.add_argument('-d', '--drift', action='store_true', help='是否添加漂移')
    return parser.parse_args()

def main():
    args = parse_args()
    conf = configparser.ConfigParser()
    if not os.path.exists(args.config_path):
        print(f"Error: 配置文件 {args.config_path} 不存在。")
        return
        
    conf.read(args.config_path, encoding="utf-8")
    
    # User info
    token = conf.get("User", 'token', fallback="")
    device_id = conf.get("User", "device_id", fallback="")
    device_name = conf.get("User", "device_name", fallback="")
    uuid = conf.get("User", "uuid", fallback="")
    sign = conf.get("User", "sign", fallback="")
    utc = conf.get('User', 'utc', fallback="")
    sys_edition = conf.get("User", "sys_edition", fallback="14")
    
    # App info
    school_host = conf.get("Yun", "school_host", fallback="")
    school_id = conf.get("Yun", "school_id", fallback="195")
    app_edition = conf.get("Yun", "app_edition", fallback="3.5.1")
    md5key = conf.get("Yun", "md5key", fallback="")
    platform = conf.get("Yun", "platform", fallback="android")
    school_name = conf.get("Yun", "school_name", fallback="")
    school_login_url = conf.get("Yun", "school_login_url", fallback="appLogin")
    
    # Keys
    public_key = conf.get("Yun", "PublicKey", fallback="")
    private_key = conf.get("Yun", "PrivateKey", fallback="")
    cipherkey = conf.get("Yun", "cipherkey", fallback="")
    cipherkeyencrypted = conf.get("Yun", "cipherkeyencrypted", fallback="")
    
    # Login config
    username = conf.get("Login", "username", fallback="")
    password = conf.get("Login", "password", fallback="")

    auth = AuthManager(device_id, device_name, sys_edition, app_edition, md5key, platform, cipherkey, cipherkeyencrypted)
    
    if not token:
        print("config中token为空，尝试提取或使用账号密码登录...")
        if not username or not password:
            username = input('未找到用户名，请输入用户名：')
            password = input('未找到密码，请输入密码：')
            conf.set('Login', 'username', username)
            conf.set('Login', 'password', password)
        
        if not device_id:
            device_id = str(random.randint(1000000000000000, 9999999999999999))
            uuid = device_id
        
        if not device_name:
            device_name = input("DeviceName为空 请输入希望使用的手机名称 (留空则默认 Xiaomi): ") or "Xiaomi"
            
        utc = str(int(time.time()))
        
        try:
            print("正在获取由于 Token 失效的最新环境数据...")
            login_res = auth.login(username, password, school_id, school_host, school_login_url, uuid, utc)
            token = login_res['token']
            print(f"Token 更新成功: {token}")
            
            # Update config file
            conf.set('User', 'token', token)
            conf.set('User', 'device_id', login_res['device_id'])
            conf.set('User', 'device_name', login_res['device_name'])
            conf.set('User', 'sys_edition', login_res['sys_edition'])
            conf.set('User', 'uuid', login_res['uuid'])
            conf.set('User', 'utc', utc)
            with open(args.config_path, 'w', encoding='utf-8') as f:
                conf.write(f)
                
        except Exception as e:
            print(f"登录失败退出: {e}")
            return

    # Initialize YunCore
    run_config = {
        "strides": conf.get("Run", "strides", fallback="0.8"),
        "single_mileage_min_offset": conf.get("Run", "single_mileage_min_offset", fallback="0.5"),
        "single_mileage_max_offset": conf.get("Run", "single_mileage_max_offset", fallback="-0.5"),
        "cadence_min_offset": conf.get("Run", "cadence_min_offset", fallback="30"),
        "cadence_max_offset": conf.get("Run", "cadence_max_offset", fallback="-150")
    }
    
    split_count = int(conf.get("Run", "split_count", fallback="10"))
    
    print()
    print("====== 准备运行数据 ======")
    print("Token: ".ljust(15) + token)
    print('deviceId: '.ljust(15) + device_id)
    print('deviceName: '.ljust(15) +  device_name)
    print('utc: '.ljust(15) + utc)
    print('uuid: '.ljust(15) + uuid)
    print("=========================\n")

    sure = 'y' if args.auto_run else input("确认：[y/n]")
    if sure != 'y':
        print("退出。")
        return
        
    core = YunCore(token, device_id, device_name, uuid, sign, utc, 
                  school_host, school_id, app_edition, md5key, platform,
                  public_key, private_key, cipherkey, cipherkeyencrypted, run_config)
                  
    success, msg = core.init_run_info()
    if not success:
        print(f"获取首页运行信息失败! {msg}")
        return
        
    success, msg = core.start_run()
    if not success:
        print(f"开始跑步失败! {msg}")
        return
        
    print(f"开始跑步成功! {msg}")
    
    # Point mapping simulation 
    print_table = 'y' if args.auto_run else input("打表模式(固定路线，无需高德地图key)：[y/n]")
    if print_table != 'y':
        print("退出。此版本仅支持打表模式（预设路线）运行")
        return

    path_dir = args.task_path if args.auto_run else "./tasks_else"
    if not args.auto_run:
        print("请选择校区（1.翡翠湖校区,2.屯溪路校区,3.宣城校区,4.自定义(文件夹tasks_else)）")
        choice = input("选(默认4): ") or "4"
        if choice == '1': path_dir = "./tasks_fch"
        elif choice == '2': path_dir = "./tasks_txl"
        elif choice == '3': path_dir = "./tasks_xc"
        else: path_dir = "./tasks_else"
        
    is_drift = False
    if not args.auto_run:
        driftChoice = input("是否为数据添加漂移：[y/n]")
        is_drift = True if driftChoice == 'y' else False
    else:
        is_drift = args.drift

    files = [f for f in os.listdir(path_dir) if f.endswith('.json')]
    if not files:
        print(f"未在 {path_dir} 中找到任务文件.")
        return
        
    files.sort()
    
    # Auto choose a random task
    file = os.path.join(path_dir, random.choice(files))
    print("随机选择：" + file)
    
    with open(file, 'r', encoding='utf-8') as f:
        task_map = json.loads(f.read())
        
    if is_drift:
        from tools.drift import add_drift
        task_map = add_drift(task_map)

    points = []
    count = 0
    
    # Calculate sleep
    total_points = len(task_map['data']['pointsList'])
    sleep_time = task_map['data']['duration'] / total_points * split_count
            
    print(f"预计每组挂机等待 {sleep_time:.2f} 秒.")
    
    for point in tqdm(task_map['data']['pointsList'], leave=True):
        point_changed = {
            'point': point['point'],
            'runStatus': '1',
            'speed': point['speed'],
            'isFence': 'Y',
            'isMock': False,
            "runMileage": point['runMileage'],
            "runTime": point['runTime'],
            "ts": str(int(time.time()))
        }
        points.append(point_changed)
        count += 1
        
        if count == split_count:
            # Send split points
            core.split_by_points_map(points, task_map['data']['recodePace'])
            time.sleep(sleep_time)
            count = 0
            points = []
            
    if count != 0:
        core.split_by_points_map(points, task_map['data']['recodePace'])
        
    # Finish run
    print("所有点已经发送完毕，正在发起结算...")
    res = core.finish_by_points_map(task_map)
    print("结算响应: ", res)

if __name__ == "__main__":
    main()
