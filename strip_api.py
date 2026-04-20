with open('web/routers/api.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False

for line in lines:
    if line.startswith('@router.get("/login"') or line.startswith('@router.post("/login"') or line.startswith('@router.get("/logout"') or line.startswith('@router.get("/", ') or line.startswith('@router.get("/logs"') or line.startswith('@router.websocket'):
        skip = True
    elif line.startswith('@router.') or line.startswith('def ') or line.startswith('class ') or line.startswith('GLOBAL_') or line.startswith('load_schools_cache'):
        skip = False
        
    if not skip:
        new_lines.append(line)

with open('web/routers/api.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
