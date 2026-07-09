const fs = require('fs');
const text = fs.readFileSync('src/App.tsx', 'utf8');
let stack = [];
let inString = false;
let stringChar = '';
let inComment = false;
let inLineComment = false;
for (let i = 0; i < text.length; i++) {
  const c = text[i];
  const next = text[i+1];
  
  if (inString) {
    if (c === stringChar && text[i-1] !== '\\') inString = false;
    continue;
  }
  if (inComment) {
    if (c === '*' && next === '/') { inComment = false; i++; }
    continue;
  }
  if (inLineComment) {
    if (c === '\n') inLineComment = false;
    continue;
  }
  if (c === '/' && next === '/') { inLineComment = true; i++; continue; }
  if (c === '/' && next === '*') { inComment = true; i++; continue; }
  if (c === '"' || c === "'" || c === '`') { inString = true; stringChar = c; continue; }
  
  if (c === '{') {
    const lines = text.slice(0, i).split('\n');
    stack.push({ char: c, line: lines.length, col: lines[lines.length - 1].length });
  } else if (c === '}') {
    if (stack.length === 0) {
      console.log('Extra } at index', i);
      break;
    }
    stack.pop();
  }
}
console.log('Unclosed braces:', stack);
