const fs = require('fs');
const content = fs.readFileSync('web/static/js/dashboard.js', 'utf8');

let count = 0;
let lines = content.split('\n');
for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    for (let j = 0; j < line.length; j++) {
        if (line[j] === '{') count++;
        if (line[j] === '}') count--;
    }
    if (count < 0) {
        console.log('Extra closing brace at line ' + (i + 1));
        count = 0;
    }
}
console.log('Final brace count: ' + count);
