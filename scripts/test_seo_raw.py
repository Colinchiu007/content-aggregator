#!/usr/bin/env python3
"""直接调用 LLM，把原始响应保存成文件，绕开终端编码问题。"""
import sys
import json
import httpx
from pathlib import Path

# 加项目根目录到 sys.path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config.loader import load_config

PROMPT = """请为以下文章生成 SEO 优化数据，以 JSON 格式返回：

文章标题：AI 助手正在改变软件开发方式
文章内容：AI 助手可以帮助开发者提高效率……

请返回 JSON：
{
  "keywords": ["关键词1", "关键词2"],
  "description": "简介",
  "tags": ["标签1", "标签2"]
}
"""

def main():
    cfg = load_config()
    llm_cfg = cfg.get_llm()  # 返回 dict

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {llm_cfg['api_key']}",
    }
    payload = {
        "model": llm_cfg.get("model", "deepseek-chat"),
        "messages": [{"role": "user", "content": PROMPT}],
        "temperature": 0.7,
    }

    print(f"→ 调用 LLM: {llm_cfg.get('base_url', 'https://api.deepseek.com')}")
    with httpx.Client(timeout=60) as client:
        resp = client.post(
            f"{llm_cfg.get('base_url', 'https://api.deepseek.com')}/chat/completions",
            headers=headers,
            json=payload,
        )
    print(f"→ HTTP status: {resp.status_code}")

    # 把原始响应保存到文件
    out_file = ROOT / "scripts" / "llm_raw_response.json"
    out_file.write_text(resp.text, encoding="utf-8")
    print(f"→ 原始响应已保存到: {out_file}")

    # 尝试解析
    try:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        print(f"→ content 长度: {len(content)}")
        print(f"→ content 前 500 字符:")
        print(content[:500])
    except Exception as e:
        print(f"→ 解析失败: {e}")
        print(f"→ resp.text 前 500 字符:")
        print(resp.text[:500])


if __name__ == "__main__":
    main()
