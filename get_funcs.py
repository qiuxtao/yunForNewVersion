import re

with open('templates/dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

funcs = set()
for m in re.finditer(r'(?:onclick|onsubmit)=[\'"]([a-zA-Z0-9_]+)\(', content):
    funcs.add(m.group(1))

print(" ".join(funcs))
