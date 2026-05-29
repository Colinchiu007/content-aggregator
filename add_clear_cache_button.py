#!/usr/bin/env python3
"""
添加"清除去重缓存"按钮到 settings.html
"""

import re

# 读取文件
with open('web/templates/settings.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 要添加的 HTML + JS 代码
danger_section = """
        
        {% endblock %}
    </div>
</div>

{# ===== 危险操作 ===== #}
<div class="card" style="border-left:4px solid var(--danger);margin-top:24px">
    <div class="card-header">
        <span class="card-title">⚠️ 危险操作</span>
    </div>
    <div style="padding:16px">
        <p style="font-size:13px;color:var(--text-muted);margin-bottom:16px">
            清除去重缓存后，系统会重新采集已采集过的文章（因为不再去重）。
        </p>
        <button type="button" class="btn btn-danger" onclick="clearDedupCache()">🗑️ 清除去重缓存</button>
        <span id="cache-status" style="margin-left:12px;font-size:13px"></span>
    </div>
</div>

<script>
    // 清除去重缓存
    async function clearDedupCache() {
        if (!confirm('确定要清除去重缓存吗？\\n\\n清除后，系统会重新采集已采集过的文章。')) {
            return;
        }
        
        const btn = event.target;
        btn.disabled = true;
        btn.textContent = '清除中...';
        
        try {
            const resp = await fetch('/api/cache/clear', { method: 'POST' });
            const data = await resp.json();
            
            if (data.success) {
                showToast('成功：' + data.message, 'success');
                document.getElementById('cache-status').textContent = '缓存已清除';
                document.getElementById('cache-status').style.color = 'var(--success)';
            } else {
                showToast('清除失败: ' + (data.error || '未知错误'), 'error');
                document.getElementById('cache-status').textContent = '清除失败';
                document.getElementById('cache-status').style.color = 'var(--danger)';
            }
        } catch (e) {
            showToast('请求失败: ' + e.message, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = '🗑️ 清除去重缓存';
        }
    }
</script>
"""

# 在 </form> 标签后插入（在 {% endblock %} 之前）
if '</form>' in content:
    # 找到 </form> 的位置
    form_end = content.find('</form>')
    # 在 </form> 后插入
    new_content = content[:form_end + 7] + danger_section + content[form_end + 7:]
    
    # 写回文件
    with open('web/templates/settings.html', 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("[OK] 已添加'清除去重缓存'按钮到 settings.html")
    print("   位置：</form> 标签之后")
else:
    print("[ERROR] 未找到 </form> 标签")
