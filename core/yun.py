import base64
import random
import time
import httpx
import json
import hashlib
import gzip
from typing import List, Dict
from gmssl.sm4 import CryptSM4, SM4_ENCRYPT, SM4_DECRYPT
import gmssl.sm2 as sm2
from base64 import b64encode, b64decode
from gmssl import sm4, func
import traceback

class YunCore:
    def __init__(self, token, device_id, device_name, uuid, sign, utc, 
                 school_host, school_id, app_edition, md5key, platform,
                 public_key, private_key, cipherkey, cipherkeyencrypted,
                 run_config):
        self.my_token = token
        self.my_device_id = device_id
        self.my_device_name = device_name
        self.my_uuid = uuid
        self.my_sign = sign
        self.my_utc = utc
        self.my_host = school_host
        self.school_id = school_id
        self.my_app_edition = app_edition
        self.md5key = md5key
        self.platform = platform
        
        self.public_key_bytes = b64decode(public_key)
        self.private_key_bytes = b64decode(private_key)
        self.default_key = cipherkey
        self.CipherKeyEncrypted = cipherkeyencrypted
        
        # SM2 Crypt instance
        self.sm2_crypt = sm2.CryptSM2(
            public_key=self.bytes_to_hex(self.public_key_bytes[1:]), 
            private_key=self.bytes_to_hex(self.private_key_bytes), 
            mode=1, asn1=True
        )

        # Run configs
        self.strides = float(run_config.get("strides", 0.8))
        self.single_mileage_min_offset = float(run_config.get("single_mileage_min_offset", 0.5))
        self.single_mileage_max_offset = float(run_config.get("single_mileage_max_offset", -0.5))
        self.cadence_min_offset = int(run_config.get("cadence_min_offset", 30))
        self.cadence_max_offset = int(run_config.get("cadence_max_offset", -150))
        
        self.raType = None
        self.raId = None
        self.raRunArea = None
        self.raDislikes = None
        self.raCadenceMin = None
        self.raCadenceMax = None
        self.crsRunRecordId = None
        self.recordStartTime = None
        self.userName = None

    @staticmethod
    def string_to_hex(input_string):
        return hex(int.from_bytes(input_string.encode(), 'big'))[2:].upper()

    @staticmethod
    def bytes_to_hex(input_string):
        return hex(int.from_bytes(input_string, 'big'))[2:].upper()

    @staticmethod
    def encrypt_sm4(value, SM_KEY, isBytes=False):
        crypt_sm4 = CryptSM4()
        crypt_sm4.set_key(SM_KEY, SM4_ENCRYPT)
        if not isBytes:
            encrypt_value = b64encode(crypt_sm4.crypt_ecb(value.encode("utf-8")))
        else:
            encrypt_value = b64encode(crypt_sm4.crypt_ecb(value))
        return encrypt_value.decode()

    @staticmethod
    def decrypt_sm4(value, SM_KEY):
        crypt_sm4 = CryptSM4()
        crypt_sm4.set_key(SM_KEY, SM4_DECRYPT)
        decrypt_value = crypt_sm4.crypt_ecb(b64decode(value))
        return decrypt_value

    def encrypt_sm2(self, info):
        encode_info = self.sm2_crypt.encrypt(info.encode("utf-8"))
        encode_hex = encode_info.hex().upper()
        encode_hex_with_prefix = "04" + encode_hex # 添加04头
        encode_info = b64encode(bytes.fromhex(encode_hex_with_prefix)).decode()
        return encode_info

    def decrypt_sm2(self, info):
        decode_info = b64decode(info)
        decode_info = self.sm2_crypt.decrypt(decode_info)
        return decode_info

    @staticmethod
    def generate_sm4():
        key_hex = func.random_hex(32)
        key_bytes = bytes.fromhex(key_hex)
        return b64encode(key_bytes).decode('utf-8')

    def getsign(self, utc, uuid):
        sb = (
            "platform=" + self.platform + 
            "&utc=" + str(utc) + 
            "&uuid=" + str(uuid) + 
            "&appsecret=" + self.md5key
        )
        m = hashlib.md5()
        m.update(sb.encode("utf-8"))
        return m.hexdigest()

    @staticmethod
    async def get_global_schools(app_edition, cipherkey, cipherkeyencrypted, md5key):
        utc = str(int(time.time()))
        uuid = "2211725972932675"
        sign_data = f'platform=android&utc={utc}&uuid={uuid}&appsecret={md5key}'
        m = hashlib.md5()
        m.update(sign_data.encode('utf-8'))
        sign = m.hexdigest()
        
        url = "http://sports.aiyyd.com:9001/api/app/schoolList"
        headers = {
            "isApp": "app",
            "deviceId": uuid,
            "deviceName": "Xiaomi",
            "version": app_edition,
            "platform": "android",
            "uuid": uuid,
            "utc": utc,
            "sign": sign,
            "Content-Type": "application/json; charset=utf-8",
            "Content-Length": "217",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": "okhttp/3.12.0"
        }
        data_json = {
            "cipherKey": cipherkeyencrypted,
            "content": YunCore.encrypt_sm4("", b64decode(cipherkey), isBytes=False)
        }
        try:
            async with httpx.AsyncClient() as client:
                req = await client.post(url=url, content=json.dumps(data_json), headers=headers, timeout=10)
            infojson = json.loads(YunCore.decrypt_sm4(req.text, b64decode(cipherkey)).decode())
            if infojson.get('code') == 200:
                return True, infojson.get('data', [])
            return False, "Failed to get schools"
        except Exception as e:
            return False, str(e)

    async def default_post(self, router, data, headers=None, m_host=None, isBytes=False, gen_sign=True):
        m_host = m_host or self.my_host
        url = m_host + router
        
        my_utc = str(int(time.time())) if gen_sign else self.my_utc
        sign = self.getsign(my_utc, self.my_uuid) if gen_sign else self.my_sign
        
        if headers is None:
            headers = {
                'token': self.my_token,
                'isApp': 'app',
                'deviceId': self.my_device_id,
                'deviceName': self.my_device_name,
                'version': self.my_app_edition,
                'platform': 'android',
                'Content-Type': 'application/json; charset=utf-8',
                'Connection': 'Keep-Alive',
                'Accept-Encoding': 'gzip',
                'User-Agent': 'okhttp/4.9.1',
                'utc': my_utc,
                'uuid': self.my_uuid,
                'sign': sign
            }
            
        sm4_key = self.default_key if self.default_key and self.default_key.strip() else self.generate_sm4()
        
        data_json = {
            "cipherKey": self.encrypt_sm2(sm4_key),
            "content": self.encrypt_sm4(data, b64decode(sm4_key), isBytes=isBytes)
        }
        
        async with httpx.AsyncClient() as client:
            req = await client.post(url=url, content=json.dumps(data_json), headers=headers, timeout=15)
        try:
            return self.decrypt_sm4(req.text, b64decode(sm4_key)).decode()
        except:
            return req.text

    async def init_run_info(self):
        try:
            resp = await self.default_post("/run/getHomeRunInfo", "")
            data = json.loads(resp)
            if data.get('code') != 200:
                print(f"Error fetching home run info: {data}")
                return False, data.get('msg', 'Unknown Error')
                
            cralist = data['data']['cralist']
            if not cralist:
                return False, "No running task list available from server."
                
            run_data = cralist[0]
            self.raType = run_data['raType']
            self.raId = run_data['id']
            self.school_id = run_data.get('schoolId', self.school_id)
            self.raRunArea = run_data['raRunArea']
            self.raDislikes = run_data['raDislikes']
            self.raCadenceMin = run_data['raCadenceMin'] + self.cadence_min_offset
            self.raCadenceMax = run_data['raCadenceMax'] + self.cadence_max_offset
            return True, "Success"
        except Exception as e:
            traceback.print_exc()
            return False, str(e)

    async def start_run(self):
        data = {
            'raRunArea': self.raRunArea,
            'raType': self.raType,
            'raId': self.raId
        }
        resp = await self.default_post('/run/start', json.dumps(data))
        try:
            j = json.loads(resp)
        except Exception as e:
            return False, f"Failed to parse /run/start response: {resp}"

        if j.get('code') == 200:
            try:
                self.recordStartTime = j['data']['recordStartTime']
                self.crsRunRecordId = j['data']['id']
                self.userName = j['data']['studentId']
                return True, "云运动任务创建成功"
            except KeyError as e:
                return False, f"API returned 200 but missing field {e}. Full response: {j}"
        else:
            return False, f"API `/run/start` failed. Full response: {j}"

    async def split_by_points_map(self, points, speed_pace):
        data = {
            "StepNumber": int(float(points[-1]['runMileage']) - float(points[0]['runMileage'])) / self.strides,
            'a': 0,
            'b': None,
            'c': None,
            "mileage": float(points[-1]['runMileage']) - float(points[0]['runMileage']),
            "orientationNum": 0,
            "runSteps": random.uniform(self.raCadenceMin, self.raCadenceMax),
            'cardPointList': points,
            "simulateNum": 0,
            "time": float(points[-1]['runTime']) - float(points[0]['runTime']),
            'crsRunRecordId': self.crsRunRecordId,
            "speeds": speed_pace,
            'schoolId': self.school_id,
            "strides": self.strides,
            'userName': self.userName
        }
        resp = await self.default_post("/run/splitPointCheating", gzip.compress(data=json.dumps(data).encode("utf-8")), isBytes=True)
        return resp

    async def finish_by_points_map(self, task_map):
        data = {
            'recordMileage': task_map['data']['recordMileage'],
            'recodeCadence': task_map['data']['recodeCadence'],
            'recodePace': task_map['data']['recodePace'],
            'deviceName': self.my_device_name,
            'sysEdition': "14", # Fallback
            'appEdition': self.my_app_edition,
            'raIsStartPoint': 'Y',
            'raIsEndPoint': 'Y',
            'raRunArea': self.raRunArea,
            'recodeDislikes': str(task_map['data']['recodeDislikes']),
            'raId': str(self.raId),
            'raType': self.raType,
            'id': str(self.crsRunRecordId),
            'duration': task_map['data']['duration'],
            'recordStartTime': self.recordStartTime,
            'manageList': task_map['data']['manageList'],
            'remake': '1'
        }
        resp = await self.default_post("/run/finish", json.dumps(data))
        return resp

    async def get_terms(self):
        try:
            resp = await self.default_post("/run/listXnYearXqByStudentId", "")
            try:
                term_list = json.loads(resp)
            except:
                return False, f"List terms failed: {resp[:200]}"
                
            if term_list.get("code") != 200:
                return False, term_list.get("msg", "获取学期失败")
                
            terms = term_list.get("data", [])
            if not terms:
                return False, "没有任何学期数据"
                
            filtered_terms = []
            for term in terms:
                # 只保留 2025-2026 及以后的学期
                try:
                    year = int(term['key'][:4])
                    if year >= 2025:
                        filtered_terms.append(term)
                except:
                    # 如果解析失败，保守起见保留
                    filtered_terms.append(term)
                    
            return True, filtered_terms
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, str(e)

    async def get_term_history(self, term_value):
        try:
            run_list_resp = await self.default_post("/run/crsReocordInfoList", json.dumps({"tableName": term_value}))
            runs = []
            run_list = json.loads(run_list_resp)
            if run_list.get("code") == 200:
                for month_data in run_list.get("data", {}).get("rank", []):
                    month_label = month_data.get("month", "") # Extract the month info from parent
                    for run in month_data.get("rankList", []):
                        run['month_label'] = month_label
                        runs.append(run)
            return True, runs
        except Exception as e:
            return False, str(e)

    async def get_run_detail(self, run_id, table_name):
        try:
            payload = json.dumps({"id": run_id, "tableName": table_name})
            
            my_utc = str(int(time.time()))
            headers = {
                'token': self.my_token,
                'isApp': 'app',
                'deviceId': self.my_device_id,
                'deviceName': self.my_device_name,
                'version': self.my_app_edition,
                'platform': 'android',
                'Content-Type': 'application/json; charset=utf-8',
                'Connection': 'Keep-Alive',
                'Accept-Encoding': 'gzip',
                'User-Agent': 'okhttp/4.9.1',
                'utc': my_utc,
                'uuid': self.my_uuid,
                'sign': self.getsign(my_utc, self.my_uuid)
            }
            
            sm4_key = self.generate_sm4()
            data_json = {
                "cipherKey": self.encrypt_sm2(sm4_key),
                "content": self.encrypt_sm4(payload, b64decode(sm4_key), isBytes=False)
            }
            
            url = self.my_host + "/run/crsReocordInfo"
            async with httpx.AsyncClient() as client:
                req = await client.post(url=url, content=json.dumps(data_json), headers=headers, timeout=15)
            
            import gzip
            decrypted_bytes = self.decrypt_sm4(req.text, b64decode(sm4_key))
            text = gzip.decompress(decrypted_bytes).decode('utf-8')
            
            return True, json.loads(text)
        except Exception as e:
            return False, str(e)
