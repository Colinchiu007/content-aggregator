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
let jsLines = jsCode.split('\n');

console.log('Total JS lines:', jsLines.length);

// 找到 "setTimeout(() => { toast.style.opacity" 行
// showToast() 函数结束应该是这行后面第 2 个 '}'
let toastEndIndex = -1;
for (let i = 0; i < jsLines.length; i++) {
    if (jsLines[i].includes('setTimeout(() => { toast.style.opacity')) {
        // 找到 showToast 的结束位置
        for (let j = i + 1; j < Math.min(i + 5, jsLines.length); j++) {
            if (jsLines[j].trim() === '}') {
                toastEndIndex = j;
                console.log('Found showToast() ending at line', j + 1);
                break;
            }
        }
        break;
    }
}

if (toastEndIndex >= 0 && toastEndIndex + 1 < jsLines.length) {
    // 检查下一行是否也是单独的 '}'
    if (jsLines[toastEndIndex + 1].trim() === '}') {
        console.log('Found EXTRA } at line', toastEndIndex + 2, '- removing it');
        jsLines.splice(toastEndIndex + 1, 1);
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
