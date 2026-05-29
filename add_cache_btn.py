#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
添加"清除去重缓存"按钮到 settings.html
"""
import sys
import os

# 切换到项目根目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 读取文件
with open('web/templates/settings.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 检查是否已添加
if '清除去重缓存' in content:
    print('[INFO] Button already exists, skip')
    sys.exit(0)

# 要插入的 HTML（在 </form> 之后，{% endblock %} 之前）
btn_html = '''
    
    <div class="form-actions">
        <button type="submit" class="btn btn-primary">保存配置</button>
        <button type="reset" class="btn btn-secondary">重置</button>
    </div>
</form>

{# Dangerous operations #}
<div class="card" style="border-left:4px solid #dc3545;margin-top:24px">
    <div class="card-header">
        <span class="card-title">Dangerous Operations</span>
    </div>
    <div style="padding:16px">
        <p style="font-size:13px;color:#666;margin-bottom:16px">
            After clearing the dedup cache, the system will re-collect previously collected articles.
        </p>
        <button type="button" class="btn btn-danger" onclick="clearDedupCache()">Clear Dedup Cache</button>
        <span id="cache-status" style="margin-left:12px;font-size:13px"></span>
    </div>
</div>

<script>
async function clearDedupCache() {
    if (!confirm('Clear dedup cache?\\n\\nThis will cause re-collection of previous articles.')) {
        return;
    }
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = 'Clearing...';
    try {
        const resp = await fetch('/api/cache/clear', { method: 'POST' });
        const data = await resp.json();
        if (data.success) {
            showToast('Success: ' + data.message, 'success');
            document.getElementById('cache-status').textContent = 'Cache cleared';
            document.getElementById('cache-status').style.color = '#28a745';
        } else {
            showToast('Failed: ' + (data.error || 'Unknown'), 'error');
        }
    } catch (e) {
        showToast('Request failed: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Clear Dedup Cache';
    }
}
</script>
'''

# 在 </form> 后插入
if '</form>' in content:
    form_end = content.find('</form>') + len('</form>')
    new_content = content[:form_end] + btn_html + content[form_end:]
    
    with open('web/templates/settings.html', 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print('[OK] Added "Clear Dedup Cache" button to settings.html')
else:
    print('[ERROR] </form> not found')
    sys.exit(1)
