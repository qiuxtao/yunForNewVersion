import os

with open('web/static/js/dashboard.js', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace document.addEventListener('DOMContentLoaded', async () => {
content = content.replace("document.addEventListener('DOMContentLoaded', async () => {", "(async () => {")
# The closing for this is at line 1721. Wait, there are multiple }); in the file.
