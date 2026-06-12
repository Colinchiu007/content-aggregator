const fs = require('fs');
const path = 'C:/Users/邱领/.qclaw/workspace/content-aggregator/web/templates/system-settings.html';

// 读取文件
let content = fs.readFileSync(path, 'utf8');

// 提取 <script> 块
const scriptMatch = content.match(/(<script>)([\s\S]*?)(<\/script>)/);
if (!scriptMatch) {
    console.log('❌ No script block found');
    process.exit(1);
}

let jsCode = scriptMatch[2];
const jsLines = jsCode.split('\n');

console.log('JS lines:', jsLines.length);

// 找到 showToast() 函数结束后的多余 '}'
// 策略：找到 "setTimeout(() =>" 行，它后面第 2 行应该是 '}' (showToast 结束)，再后面一行不应该再有 '}'
let showToastEndLine = -1;
for (let i = 0; i < jsLines.length; i++) {
    if (jsLines[i].includes('setTimeout(() => { toast.style.opacity')) {
        // showToast 函数的结尾应该是 i+2 位置
        showToastEndLine = i + 2;
        console.log('Found showToast end at line', showToastEndLine + 1);
        break;
    }
}

if (showToastEndLine >= 0 && showToastEndLine + 1 < jsLines.length) {
    // 检查下一行是否只有 '}'
    const nextLine = jsLines[showToastEndLine + 1].trim();
    if (nextLine === '}') {
        console.log('Found EXTRA } at line', showToastEndLine + 2, '- removing it');
        jsLines.splice(showToastEndLine + 1, 1);
    }
}

// 重新组装
jsCode = jsLines.join('\n');

// 验证 JS 语法
try {
    new Function(jsCode);
    console.log('✅ JS syntax is valid!');
} catch (e) {
    console.log('❌ JS syntax error:', e.message);
    process.exit(1);
}

// 替换回文件
const newContent = content.replace(/(<script>)([\s\S]*?)(<\/script>)/, '$1' + jsCode + '$3');
fs.writeFileSync(path, newContent, 'utf8');
console.log('✅ File updated successfully!');
