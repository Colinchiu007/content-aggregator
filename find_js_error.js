const fs = require('fs');

const html = fs.readFileSync('web/templates/system-settings.html', 'utf8');
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);

if (!scriptMatch) {
    console.log('❌ No script block found');
    process.exit(1);
}

const jsCode = scriptMatch[1];
const lines = jsCode.split('\n');

console.log('Total JS lines:', lines.length);

// 逐段验证 JS 语法，找到出错位置
for (let i = 10; i <= lines.length; i += 10) {
    const chunk = lines.slice(0, i).join('\n');
    try {
        new Function(chunk);
    } catch (e) {
        console.log(`\n❌ Syntax error found near line ${i}:`);
        console.log('Error:', e.message);
        
        // 显示错误周围的代码
        for (let j = Math.max(0, i - 15); j < Math.min(lines.length, i + 5); j++) {
            const marker = (j + 1 === i) ? ' >>> ' : '     ';
            console.log(marker + (j + 1) + ':', lines[j]);
        }
        break;
    }
}

// 如果上面没找到，验证整个文件
try {
    new Function(jsCode);
    console.log('✅ Full JS syntax is valid (unexpected?)');
} catch (e) {
    console.log('\n❌ Full JS syntax error:', e.message);
}
