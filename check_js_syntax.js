const fs = require('fs');
const path = 'C:/Users/邱领/.qclaw/workspace/content-aggregator/web/templates/system-settings.html';

// 读取 HTML 文件
const html = fs.readFileSync(path, 'utf8');

// 提取 <script> 块
const match = html.match(/<script>([\s\S]*?)<\/script>/);
if (!match) {
    console.log('❌ No script block found');
    process.exit(1);
}

const jsCode = match[1];
console.log('✅ JS code extracted, length:', jsCode.length, 'chars');

// 验证 JS 语法
try {
    new Function(jsCode);
    console.log('✅ JS syntax is VALID!');
} catch (e) {
    console.log('❌ JS syntax error:', e.message);
    
    // 提取错误行号
    const lineMatch = e.message.match(/(\d+):/);
    if (lineMatch) {
        const lineNum = parseInt(lineMatch[1]);
        const lines = jsCode.split('\n');
        console.log('\nError context (around line', lineNum, '):');
        for (let i = Math.max(0, lineNum - 5); i < Math.min(lines.length, lineNum + 5); i++) {
            const marker = (i + 1 === lineNum) ? ' >>> ' : '     ';
            console.log(marker + (i + 1) + ':', lines[i]);
        }
    }
}
