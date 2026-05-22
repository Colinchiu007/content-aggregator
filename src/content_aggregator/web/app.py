"""Content Aggregator Web GUI"""
import sys, os, tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
import yaml

from content_aggregator.workflows.pipeline import ContentPipeline
from content_aggregator.exporters import (
    Exporter, to_markdown, to_html, to_json,
    to_txt, to_xiaohongshu, PDFExporter,
)
from content_aggregator.models import Article


# ── 配置 ─────────────────────────────────────────────
CONFIG_PATH = ROOT / "config" / "config.yaml"
_config_cache = None


def load_config() -> dict:
    global _config_cache
    if _config_cache is None:
        if not CONFIG_PATH.exists():
            raise RuntimeError(f"配置文件不存在: {CONFIG_PATH}")
        with open(CONFIG_PATH, encoding="utf-8") as f:
            _config_cache = yaml.safe_load(f)
    return _config_cache


import asyncio

_pipeline = None
_plock = asyncio.Lock()


async def get_pipeline():
    global _pipeline
    if _pipeline is None:
        async with _plock:
            if _pipeline is None:
                _pipeline = ContentPipeline(load_config())
                await _pipeline.__aenter__()
    return _pipeline


# ── FastAPI App ─────────────────────────────────────
app = FastAPI(title="Content Aggregator", version="1.0")


# ── 首页路由 ────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    return INDEX_HTML


# ── API: 采集 ───────────────────────────────────────
@app.post("/api/collect")
async def api_collect(body: dict):
    url: str = body.get("url", "").strip()
    max_articles: int = min(int(body.get("max_articles", 3)), 20)
    rewrite: bool = body.get("rewrite", False)
    strategy: str = body.get("strategy", "REWRITE")
    seo: bool = bool(body.get("seo", False))

    if not url:
        raise HTTPException(status_code=400, detail="url 不能为空")

    try:
        pipeline = await get_pipeline()
        articles_out = []
        for i in range(max_articles):
            art = await pipeline.process_url(url, rewrite=rewrite, strategy=strategy, seo=seo)
            if art and art.content:
                if rewrite and strategy:
                    art_dict_extras = {"_strategy": strategy}
                    articles_out.append((art, art_dict_extras))
                else:
                    articles_out.append((art, {}))
            # 即使 None 也继续尝试下一篇，不要 break
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"采集失败: {e}")

    if not articles_out:
        raise HTTPException(status_code=404, detail="未采集到任何文章")

    out_dir = os.path.join(tempfile.gettempdir(), "ca_web")
    os.makedirs(out_dir, exist_ok=True)
    exporter = Exporter(out_dir)

    result = []
    for idx, (art, extras) in enumerate(articles_out):
        exp_dir = os.path.join(out_dir, str(idx))
        os.makedirs(exp_dir, exist_ok=True)

        art_dict = art.to_dict()
        art_dict["_markdown"] = to_markdown(art)
        art_dict["_html"] = to_html(art)
        art_dict["_json"] = to_json(art)
        art_dict["_txt"] = to_txt(art)
        art_dict["_xiaohongshu"] = to_xiaohongshu(art)
        art_dict.update(extras)
        result.append(art_dict)

    return {"success": True, "count": len(result), "articles": result}


# ── API: 导出 PDF ───────────────────────────────────
@app.post("/api/export/pdf")
async def api_export_pdf(body: dict):
    try:
        art = Article.from_dict(body)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        exp = PDFExporter()
        safe_title = "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in art.title)[:50]
        out_path = os.path.join(tempfile.gettempdir(), f"{safe_title}.pdf")
        result = exp.export(art, out_path)
        if not result.success:
            raise RuntimeError(result.error)
        return FileResponse(out_path, media_type="application/pdf", filename="article.pdf")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 首页 HTML ───────────────────────────────────────
INDEX_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Content Aggregator</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, "Segoe UI", sans-serif; background: #f5f6fa; color: #333; }
header { background: #2c3e50; color: #fff; padding: 16px 24px; font-size: 18px; font-weight: 600; }
.container { max-width: 900px; margin: 24px auto; padding: 0 16px; }
.card { background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,.06); }
.card h2 { font-size: 15px; color: #2c3e50; margin-bottom: 14px; border-bottom: 1px solid #eee; padding-bottom: 8px; }
input, select, button { font-size: 14px; padding: 10px 14px; border: 1px solid #ddd; border-radius: 6px; }
input, select { width: 100%; margin-bottom: 12px; }
button { background: #3498db; color: #fff; border: none; cursor: pointer; font-weight: 500; }
button:hover { background: #2980b9; }
button:disabled { background: #bbb; cursor: not-allowed; }
.badge { background: #e8f4fc; color: #2980b9; padding: 2px 8px; border-radius: 12px; font-size: 12px; margin-right: 4px; }
#log { background: #1e1e1e; color: #ddd; padding: 12px; border-radius: 6px; font-family: monospace; font-size: 12px; max-height: 200px; overflow-y: auto; line-height: 1.6; }
#log .info { color: #3498db; }
#log .success { color: #2ecc71; }
#log .error { color: #e74c3c; }
.result-tab { display: inline-block; padding: 8px 16px; cursor: pointer; border-bottom: 2px solid transparent; }
.result-tab.active { border-bottom-color: #3498db; color: #3498db; }
.result-content { display: none; padding: 12px 0; }
.result-content.active { display: block; }
.flex { display: flex; gap: 12px; }
.flex > * { flex: 1; }
.article-item { padding: 10px; border: 1px solid #eee; border-radius: 6px; margin-bottom: 8px; cursor: pointer; }
.article-item:hover { background: #f0f7ff; border-color: #3498db; }
.article-item.active { background: #e8f4fc; border-color: #3498db; }
</style>
</head>
<body>
<header>📰 Content Aggregator</header>
<div class="container">
<div class="card">
<h2>📥 输入 RSS URL 采集</h2>
<div class="flex">
<input type="text" id="rssUrl" placeholder="https://example.com/feed.xml" value="">
<input type="number" id="maxArticles" placeholder="篇数" value="3" style="width:80px;flex:none;">
</div>
<select id="rewriteStrategy">
<option value="">不改写（仅采集）</option>
<option value="REWRITE" selected>深度改写</option>
<option value="PARAPHRASE">伪原创</option>
<option value="STYLE_TRANSFER">风格转换</option>
<option value="SUMMARIZE">摘要</option>
<option value="EXPAND">扩写</option>
</select>
<select id="seoEnabled"><option value="false">无SEO</option><option value="true">+SEO优化</option></select>
<button onclick="runCollect()" id="collectBtn">🚀 开始采集</button>
</div>

<div class="card" id="articlesCard" style="display:none">
<h2>📚 已采文章</h2>
<div id="articlesList"></div>
</div>

<div class="card" id="resultCard" style="display:none">
<h2>📄 采集结果</h2>
<div id="resultMeta"></div>
<div style="margin: 12px 0;">
<div class="result-tab active" data-name="content" onclick="switchTab(this,'content')">正文</div>
<div class="result-tab" data-name="_markdown" onclick="switchTab(this,'_markdown')">Markdown</div>
<div class="result-tab" data-name="_html" onclick="switchTab(this,'_html')">HTML</div>
<div class="result-tab" data-name="_json" onclick="switchTab(this,'_json')">JSON</div>
<div class="result-tab" data-name="_txt" onclick="switchTab(this,'_txt')">TXT</div>
<div class="result-tab" data-name="_xiaohongshu" onclick="switchTab(this,'_xiaohongshu')">小红书</div>
</div>
<div id="resultContent" class="result-content active"></div>
<div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">
<button onclick="copyContent()" style="background:#27ae60">📋 复制内容</button>
<button onclick="downloadMarkdown()" style="background:#8e44ad">📥 下载 Markdown</button>
<button onclick="exportPDF()" style="background:#e67e22">📄 导出 PDF</button>
</div>
</div>

<div class="card">
<h2>📋 日志</h2>
<pre id="log"></pre>
</div>
</div>

<script>
let currentResult = null;
let articles = [];

function log(msg, type='info') {
  const el = document.getElementById('log');
  const ts = new Date().toLocaleTimeString();
  el.innerHTML += `<span class="${type}">[${ts}] ${msg}</span>\n`;
  el.scrollTop = el.scrollHeight;
}

function switchTab(el, name) {
  document.querySelectorAll('.result-tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  const content = document.getElementById('resultContent');
  content.classList.remove('active');
  setTimeout(() => {
    content.classList.add('active');
    content.innerHTML = currentResult && currentResult[name] || '无内容';
  }, 10);
}

async function runCollect() {
  const url = document.getElementById('rssUrl').value.trim();
  const max = parseInt(document.getElementById('maxArticles').value) || 3;
  const rewrite = document.getElementById('rewriteStrategy').value;
  const seo = document.getElementById('seoEnabled').value === 'true';

  if (!url) { alert('请输入 RSS URL'); return; }
  document.getElementById('resultCard').style.display = 'none';
  document.getElementById('articlesCard').style.display = 'none';
  document.getElementById('log').innerHTML = '';
  log('开始采集...');
  document.getElementById('collectBtn').disabled = true;

  try {
    const res = await fetch('/api/collect', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ url, max_articles: max, rewrite: !!rewrite, strategy: rewrite, seo })
    });
    const data = await res.json();
    if (!res.ok || data.success !== true) throw new Error(data.detail || data.error || '采集失败');

    log(`采集完成，共 ${data.count} 篇`, 'success');
    articles = data.articles;

    // 文章列表
    const listEl = document.getElementById('articlesList');
    listEl.innerHTML = '';
    articles.forEach((art, i) => {
      const div = document.createElement('div');
      div.className = 'article-item';
      div.innerHTML = `<b>${art.title || '无标题'}</b> <span style="color:#888">${art.word_count || 0}字</span>`;
      div.onclick = () => {
        document.querySelectorAll('.article-item').forEach(e => e.classList.remove('active'));
        div.classList.add('active');
        showResult(art);
      };
      listEl.appendChild(div);
    });

    document.getElementById('articlesCard').style.display = 'block';
    if (articles.length > 0) showResult(articles[0]);

  } catch(e) {
    log('错误: ' + e.message, 'error');
  } finally {
    document.getElementById('collectBtn').disabled = false;
  }
}

function showResult(article) {
  currentResult = article;
  document.getElementById('resultCard').style.display = 'block';
  const meta = [];
  meta.push(`<b>${article.title || '-'}</b>`);
  meta.push(`${article.word_count || 0}字`);
  if (article.source) meta.push(`来源: ${article.source}`);
  if (article._strategy) meta.push(`策略: ${article._strategy}`);
  if (article.tags && article.tags.length) meta.push(`标签: ${article.tags.map(t => '<span class="badge">'+t+'</span>').join(' ')}`);
  document.getElementById('resultMeta').innerHTML = meta.join(' &nbsp;|&nbsp; ');
  // 找当前激活的 tab name
  const activeTab = document.querySelector('.result-tab.active');
  const tabName = activeTab ? activeTab.getAttribute('data-name') || 'content' : 'content';
  document.getElementById('resultContent').innerHTML = article[tabName] || article.content || article._markdown || '无内容';
}

async function exportPDF() {
  if (!currentResult) return;
  try {
    const res = await fetch('/api/export/pdf', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(currentResult)
    });
    if (!res.ok) throw new Error('PDF 导出失败');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = (currentResult.title || 'article').replace(/[^a-zA-Z0-9\u4e00-\u9fa5]/g, '_') + '.pdf';
    a.click();
    URL.revokeObjectURL(url);
  } catch(e) {
    alert('导出失败: ' + e.message);
  }
}

function copyContent() {
  if (!currentResult) return;
  const text = currentResult.content || currentResult._markdown || '';
  navigator.clipboard.writeText(text).then(() => {
    log('已复制到剪贴板', 'success');
  }).catch(() => {
    // fallback
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    log('已复制到剪贴板', 'success');
  });
}

function downloadMarkdown() {
  if (!currentResult) return;
  const text = currentResult._markdown || currentResult.content || '';
  const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = (currentResult.title || 'article').replace(/[^a-zA-Z0-9\u4e00-\u9fa5]/g, '_') + '.md';
  a.click();
  URL.revokeObjectURL(url);
  log('Markdown 已下载', 'success');
}
</script>
</body>
</html>"""