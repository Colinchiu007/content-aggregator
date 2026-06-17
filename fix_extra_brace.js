const fs = require('fs');

const path = 'C:/Users/邱领/.qclaw/workspace/content-aggregator/web/templates/system-settings.html';

// 读取文件（保留原始换行符）
let content = fs.readFileSync(path, 'utf8');

// 使用正则匹配两种换行符格式
// 匹配：}\r\n\r\n}\r\n\r\n// ========== 保存模型
// 或：}\n\n}\n\n// ========== 保存模型
const pattern = /}\r?\n\r?\n}\r?\n\r?\n\/\/ ========== 保存模型/;

if (pattern.test(content)) {
    content = content.replace(pattern, '}\r\n\r\n// ========== 保存模型');
    fs.writeFileSync(path, content, 'utf8');
    console.log('✅ Extra } removed successfully!');
} else {
    console.log('⚠️ Pattern not found - checking file...');
    // 调试：显示第 381-386 行
    const lines = content.split('\r\n');
    for (let i = 380; i < 386 && i < lines.length; i++) {
        console.log(i + 1, JSON.stringify(lines[i]));
    }
}
