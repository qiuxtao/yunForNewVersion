import os

with open('web/routers/api.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('async def await load_schools_cache():', 'async def load_schools_cache():')
content = content.replace('async def await _validate_yun_sync(', 'async def _validate_yun_sync(')

with open('web/routers/api.py', 'w', encoding='utf-8') as f:
    f.write(content)
