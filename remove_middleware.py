with open('web/routers/api.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False

for line in lines:
    if line.startswith('@router.middleware("http")'):
        skip = True
    
    if not skip:
        new_lines.append(line)
        
    if skip and line.startswith('    return response'):
        skip = False

with open('web/routers/api.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
