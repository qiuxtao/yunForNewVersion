import os

os.makedirs('web/static/css', exist_ok=True)
os.makedirs('web/static/js', exist_ok=True)

with open('templates/dashboard.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

html_lines = []
css_lines = []
js_lines = []

in_style = False
in_script = False

for line in lines:
    if '<style>' in line and 'templates' not in line:
        in_style = True
        continue
    if '</style>' in line and 'templates' not in line:
        in_style = False
        continue
    
    if '<script>' in line and 'templates' not in line and 'function' not in line and len(line) < 20:
        in_script = True
        continue
    if '</script>' in line and in_script:
        in_script = False
        continue

    if in_style:
        css_lines.append(line)
    elif in_script:
        js_lines.append(line)
    else:
        html_lines.append(line)

# Now, we need to inject the <link> and <script> back into html_lines
# Find head end
head_end = -1
for i, l in enumerate(html_lines):
    if '</head>' in l:
        head_end = i
        break

if head_end != -1:
    html_lines.insert(head_end, '    <link rel="stylesheet" href="/static/css/dashboard.css">\n')

body_end = -1
for i, l in enumerate(html_lines):
    if '</body>' in l:
        body_end = i
        break

if body_end != -1:
    html_lines.insert(body_end, '    <script src="/static/js/dashboard.js"></script>\n')

with open('templates/dashboard.html', 'w', encoding='utf-8') as f:
    f.writelines(html_lines)

with open('web/static/css/dashboard.css', 'w', encoding='utf-8') as f:
    f.writelines(css_lines)

with open('web/static/js/dashboard.js', 'w', encoding='utf-8') as f:
    f.writelines(js_lines)
