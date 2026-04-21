import os

with open('web/routers/api.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. load_schools_cache
content = content.replace('def load_schools_cache():', 'async def load_schools_cache():')
content = content.replace('suc, res = YunCore.get_global_schools', 'suc, res = await YunCore.get_global_schools')
content = content.replace('load_schools_cache()', 'await load_schools_cache()')

# 2. _validate_yun_sync
content = content.replace('def _validate_yun_sync(', 'async def _validate_yun_sync(')
content = content.replace('login_res = auth.login(', 'login_res = await auth.login(')
content = content.replace('if not _validate_yun_sync(', 'if not await _validate_yun_sync(')

# 3. other yun/auth methods
content = content.replace('success, data = yun.get_terms()', 'success, data = await yun.get_terms()')
content = content.replace('success, data = yun.get_term_history(term_value)', 'success, data = await yun.get_term_history(term_value)')
content = content.replace('success, data = yun.get_run_detail(run_id, term_value)', 'success, data = await yun.get_run_detail(run_id, term_value)')

with open('web/routers/api.py', 'w', encoding='utf-8') as f:
    f.write(content)
