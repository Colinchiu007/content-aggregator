const fs = require('fs');

// 读取两个文件
const baseHtml = fs.readFileSync('web/templates/base.html', 'utf8');
const settingsHtml = fs.readFileSync('web/templates/system-settings.html', 'utf8');

console.log('=== Checking base.html ===');
// 检查 authFetch 是否完整
const authFetchMatch = baseHtml.match(/async function authFetch[\s\S]*?^}/m);
if (authFetchMatch) {
    console.log('✅ authFetch() found, length:', authFetchMatch[0].length);
    // 验证语法
    try {
        new Function(authFetchMatch[0]);
        console.log('✅ authFetch() syntax is valid');
    } catch(e) {
        console.log('❌ authFetch() syntax error:', e.message);
    }
} else {
    console.log('❌ authFetch() NOT FOUND or incomplete');
}

console.log('\n=== Checking system-settings.html ===');
// 提取 JS
const scriptMatch = settingsHtml.match(/<script>([\s\S]*?)<\/script>/);
if (scriptMatch) {
    const js = scriptMatch[1];
    console.log('JS length:', js.length, 'chars');
    try {
        new Function(js);
        console.log('✅ system-settings.html JS syntax is valid');
    } catch(e) {
        console.log('❌ system-settings.html JS syntax error:', e.message);
        // 找到错误行
        const lineMatch = e.message.match(/(\d+):/);
        if (lineMatch) {
            const lineNum = parseInt(lineMatch[1]);
            const lines = js.split('\n');
            console.log('\nError context (line', lineNum, '):');
            for (let i = Math.max(0, lineNum - 5); i < Math.min(lines.length, lineNum + 5); i++) {
                console.log((i+1) + ':', lines[i]);
            }
        }
    }
} else {
    console.log('❌ No script block found in system-settings.html');
}
