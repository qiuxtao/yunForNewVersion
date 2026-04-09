import json
import math
import random

# 加载 JSON 文件并提取经纬度
def load_json(filePath):
    with open(filePath, 'r', encoding='utf-8') as f:
        data = json.loads(f.read())
    return split_data(data)


def split_data(data):
    
    lonData = []
    latData = []

    # 遍历 pointsList 中的每一个点
    for point in data['data']['pointsList']:
        point_str = point['point']  
        lon, lat = map(float, point_str.split(','))  
        lonData.append(lon)
        latData.append(lat)
    
    return lonData, latData

# 计算两点之间的距离（使用 Haversine 公式） 
def haversine_distance(lat1, lon1, lat2, lon2):
    EARTH_RADIUS = 6371000 #地球半径 用于计算两点间距离
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    Distance = EARTH_RADIUS * c
    return  Distance
    #Chatgpt真好用啊#

def add_drift(data, enable_coord_drift=True, enable_duration_random=True, enable_cadence_random=True):
    """
    给坐标加上一个轻微的随机偏移量，实现简单的动态伪装。
    因为坐标和距离在之前已经计算完善，所以只需所有点按统一偏移平移即可。
    """
    if enable_coord_drift:
        drift = random.uniform(-0.0005, 0.0005)
    else:
        drift = 0.0

    lonData, latData = split_data(data)
    for index in range(len(lonData)):
        lonData[index] += drift
    for index in range(len(latData)):
        latData[index] += drift

    # 生成修改后的坐标列表（仅偏移坐标，不重新计算里程）
    ChangedData = [f"{lon},{lat}" for lon, lat in zip(lonData, latData)]
    for i in range(min(len(ChangedData), len(data['data']['pointsList']))):
        data['data']['pointsList'][i]['point'] = ChangedData[i]
        
    # 加入时间波动（随机正负 5% 的偏离值）
    dur_ratio = random.uniform(0.95, 1.05) if enable_duration_random else 1.0
    
    if 'duration' in data['data']:
        new_dur = int(float(data['data']['duration']) * dur_ratio)
        data['data']['duration'] = new_dur
        
        # 重新计算整体配速
        mileage = float(data['data'].get('recordMileage', 0))
        if mileage > 0:
            new_pace = (new_dur / 60.0) / mileage
            data['data']['recodePace'] = round(new_pace, 2)
            
    # 让步频也跟着随机波动一下（正负 5%）独立于耗时的波动
    if 'recodeCadence' in data['data']:
        orig_cadence = float(data['data']['recodeCadence'])
        cadence_factor = random.uniform(0.95, 1.05) if enable_cadence_random else 1.0
        data['data']['recodeCadence'] = int(orig_cadence * cadence_factor)
            
    # 等比例缩放每一个点上的耗时属性和瞬时速度
    for pt in data['data']['pointsList']:
        if 'runTime' in pt:
            pt['runTime'] = int(float(pt['runTime']) * dur_ratio)
        if 'speed' in pt:
            pt['speed'] = round(float(pt['speed']) / dur_ratio, 2)

    # recordMileage 保留原始云端值，不覆写，避免 Haversine 与云端算法的里程偏差

    return data

if __name__ == '__main__':
    print("此脚本用于对已有的tasklist进行少量偏移、步频配速重新随机、并写回到原json中")
    print("不建议直接使用，建议在main中自动调用")
    print("对一个json的累计更改可能会导致路线鬼畜.")
    pos_choice = input("你需要修改哪一个校区tasklist？(1.翡翠湖 2.屯溪路 3.其他)")

    path = "./tasks_fch/" if pos_choice == "1" else "./tasks_txl/" if pos_choice == "2" else "./tasks_else/"
    chi = input("选择要更改的文件: ")

    FilePath = os.path.join(path, "tasklist_" + chi + ".json")
    drift = random.uniform(-0.000000001, 0.000000001)
    lonData, latData = load_json(FilePath)

    for index in range(len(lonData)):
        lonData[index] += drift
    for index in range(len(latData)):
        latData[index] += drift

    #计算总距离
    Distance = 0.0
    for index in range(len(lonData) - 1):
        Distance += haversine_distance(latData[index], lonData[index], latData[index + 1], lonData[index + 1])
    Distance = round(Distance / 10) / 100
    # 生成修改后的坐标列表
    ChangedData = [f"{lon},{lat}" for lon, lat in zip(lonData, latData)]

    with open(FilePath, 'r+', encoding='utf-8') as f:
        jsondata = json.load(f)
        for i in range(min(len(ChangedData), len(jsondata['data']['pointsList']))):
            jsondata['data']['pointsList'][i]['point'] = ChangedData[i]
        jsondata['data']['recordMileage'] = Distance
        # 重置文件指针并写回修改后的 JSON 数据
        f.seek(0)
        json.dump(jsondata, f, indent=4, ensure_ascii=False)
        f.truncate()  
        print(f"write to {FilePath}. ")
    # change_pace(FilePath, round(random.uniform(4.5, 5.5), 2)) # 不放缩配速
