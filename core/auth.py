import time
import httpx
import json
import hashlib
from base64 import b64encode, b64decode
from gmssl.sm4 import CryptSM4, SM4_ENCRYPT, SM4_DECRYPT

class AuthManager:
    """
    Handles fetching school URLs and performing Account Login to get Tokens.
    Does not depend on any global config files.
    """
    def __init__(self, device_id, device_name, sys_edition, app_edition, md5key, platform, cipherkey, cipherkeyencrypted):
        self.device_id = device_id
        self.device_name = device_name
        self.sys_edition = sys_edition
        self.app_edition = app_edition
        self.md5key = md5key
        self.platform = platform
        self.default_key = cipherkey
        self.CipherKeyEncrypted = cipherkeyencrypted
        
    @staticmethod
    def md5_encryption(data):
        md5 = hashlib.md5()
        md5.update(data.encode('utf-8'))
        return md5.hexdigest()

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

    async def get_school_url_id(self, school_name, uuid="2211725972932675"):
        utc = str(int(time.time()))
        sign_data = f'platform=android&utc={utc}&uuid={uuid}&appsecret={self.md5key}'
        sign = self.md5_encryption(sign_data)
        url = "http://sports.aiyyd.com:9001/api/app/schoolList"
        
        headers = {
            "isApp": "app",
            "deviceId": uuid,
            "deviceName": "Xiaomi",
            "version": self.app_edition,
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
            "cipherKey": self.CipherKeyEncrypted,
            "content": self.encrypt_sm4("", b64decode(self.default_key), isBytes=False)
        }
        
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(url, headers=headers, json=data_json, timeout=10)
            result = res.text
            DecryptedData = json.loads(self.decrypt_sm4(result, b64decode(self.default_key)).decode())
            dataList = DecryptedData['data']
            for school in dataList:
                if school['name'] == school_name:
                    return school['host'], school['id']
            return None, None
        except Exception as e:
            return None, None

    async def login(self, username, password, school_id, school_host, school_login_url, uuid, utc):
        """
        Performs the login sequence.
        school_login_url usually falls back to 'appLogin'
        Returns a dict with token and updated information on success, or raises Exception on failure.
        """
        encryptData = f'{{"password":"{password}","schoolId":"{school_id}","userName":"{username}","type":"1"}}'
        
        sign_data = f'platform={self.platform}&utc={utc}&uuid={uuid}&appsecret={self.md5key}'
        sign = self.md5_encryption(sign_data)
        content = self.encrypt_sm4(encryptData, b64decode(self.default_key), isBytes=False)
        
        headers = {
            "token": "",
            "isApp": "app",
            "deviceId": uuid,
            "deviceName": self.device_name,
            "version": self.app_edition,
            "platform": self.platform,
            "uuid": uuid,
            "utc": str(utc),
            "sign": sign,
            "Content-Type": "application/json; charset=utf-8",
            "Accept-Encoding": "gzip",
            "User-Agent": "okhttp/3.12.0"
        }
        
        data = {
            "cipherKey": self.CipherKeyEncrypted,
            "content": content
        }
        
        url = f"{school_host}/login/{school_login_url}"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=data, timeout=10)
        result = response.text
        
        try:
            if "{" in result and result.strip().startswith("{"):
                DecryptedData = response.json()
            else:
                DecryptedData = json.loads(self.decrypt_sm4(result, b64decode(self.default_key)).decode())
        except Exception:
            try:
                DecryptedData = json.loads(self.decrypt_sm4(result, b64decode(self.default_key)).decode())
            except Exception as e:
                raise Exception(f"Login Response Parsing Failed. Status {response.status_code}, Body: {result[:200]}")
                
        if DecryptedData.get('code') == 500:
            raise Exception(f"Login failed internal error 500: {DecryptedData.get('msg', 'Error')}")
            
        if 'data' not in DecryptedData:
            raise Exception(f"Login failed. 'data' missing in response. {DecryptedData}")
            
        if response.status_code == 200:
            return {
                "token": DecryptedData['data']['token'],
                "school_id": school_id,
                "school_host": school_host,
                "uuid": uuid,
                "device_id": self.device_id,
                "device_name": self.device_name,
                "sys_edition": self.sys_edition
            }
        else:
            raise Exception(f"Login Failed with status {response.status_code}: {DecryptedData}")
