import os

with open('web/app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

ws_lines = []
pages_lines = []
api_lines = []
app_lines = []

in_ws = False
in_pages = False
in_api = False

current_block = []
current_type = 'app'

for line in lines:
    if line.startswith('@app.websocket'):
        current_type = 'ws'
    elif line.startswith('@app.get("/login"') or line.startswith('@app.post("/login"') or line.startswith('@app.get("/logout"') or line.startswith('@app.get("/", ') or line.startswith('@app.get("/logs"'):
        current_type = 'pages'
    elif line.startswith('@app.') and not line.startswith('@app.on_event') and not line.startswith('@app.exception_handler') and not line.startswith('@app.middleware'):
        current_type = 'api'
    
    # Check if a function is ending and going back to neutral
    if line.startswith('@app.') or line.startswith('def ') or line.startswith('class ') or line.startswith('GLOBAL_') or line.startswith('# ==='):
        pass # Not changing type immediately unless it's a decorator
        
    if current_type == 'ws':
        ws_lines.append(line.replace('@app.websocket', '@router.websocket'))
    elif current_type == 'pages':
        pages_lines.append(line.replace('@app.get', '@router.get').replace('@app.post', '@router.post'))
    elif current_type == 'api':
        api_lines.append(line.replace('@app.get', '@router.get').replace('@app.post', '@router.post').replace('@app.put', '@router.put').replace('@app.delete', '@router.delete'))
    else:
        app_lines.append(line)
        
with open('web/routers/ws.py', 'w', encoding='utf-8') as f:
    f.write('from fastapi import APIRouter, WebSocket, WebSocketDisconnect\nfrom notifications.qq_bot import manager\n\nrouter = APIRouter()\n\n')
    f.writelines(ws_lines)
    
