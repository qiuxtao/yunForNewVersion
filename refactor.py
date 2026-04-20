import re

# 1. Clean up app.py: Remove all routes, replace with router inclusion.
with open('web/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the first @app. router which is @app.get("/api/schools") around line 157
start_idx = content.find('@app.get("/api/schools")')
if start_idx == -1:
    print("Could not find start index")

top_part = content[:start_idx]

# Add imports and includes
include_part = '''
from web.routers import api, pages, ws

app.include_router(pages.router)
app.include_router(api.router)
app.include_router(ws.router)

'''

with open('web/app.py', 'w', encoding='utf-8') as f:
    f.write(top_part + include_part)

# 2. Clean up api.py: change @app. to @router., remove ws and pages routes
with open('web/routers/api.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('@app.', '@router.')
# Add APIRouter at the top where app = FastAPI was
content = content.replace('app = FastAPI(title="云运动 Web 控制台")', 'from fastapi import APIRouter\nrouter = APIRouter()')

with open('web/routers/api.py', 'w', encoding='utf-8') as f:
    f.write(content)
