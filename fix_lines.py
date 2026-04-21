import sys

with open('web/static/js/dashboard.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

lines[1672] = lines[1672].replace("document.addEventListener('DOMContentLoaded', async () => {", "(async () => {")
lines[1720] = lines[1720].replace("});", "})();")
lines[2234] = lines[2234].replace("window.addEventListener('DOMContentLoaded', () => {", "(() => {")
lines[2257] = lines[2257].replace("});", "})();")

with open('web/static/js/dashboard.js', 'w', encoding='utf-8') as f:
    f.writelines(lines)
