#!/usr/bin/env python3
"""
API 集成测试脚本 (ASCII-only, no emoji)

测试 content-aggregator Web API 的完整流程：
1. 启动测试服务器（后台）
2. 测试同步 API（配置、统计、文章列表）
3. 测试异步任务 API（采集、改写、导出）
4. 清理测试数据

使用方法：
    python scripts/test_api.py

前置条件：
    - 安装 httpx: pip install httpx
    - 确保 config.yaml 配置了测试数据源（如 RSS）
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

BASE_URL = "http://127.0.0.1:8000"
SERVER_PROCESS = None


def wait_for_server(timeout=15):
    """等待服务器启动（通过端口检测）"""
    import socket
    for i in range(timeout * 2):  # 每 0.5s 检查一次
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(('127.0.0.1', 8000))
                if result == 0:
                    # 端口开放，再验证 HTTP 响应
                    import httpx
                    try:
                        resp = httpx.get(f"{BASE_URL}/api/config", timeout=2)
                        if resp.status_code in (200, 401, 403, 500):
                            return True
                    except Exception:
                        pass
        except Exception:
            pass
        time.sleep(0.5)
    return False


def start_server():
    """启动测试服务器（后台）"""
    global SERVER_PROCESS
    
    print("[START] 启动测试服务器...")
    
    # 使用 uvicorn 启动
    cmd = [
        sys.executable, "-m", "uvicorn",
        "web.server:app",
        "--host", "127.0.0.1",
        "--port", "8000",
        "--log-level", "warning",
    ]
    
    SERVER_PROCESS = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
    )
    
    # 等待服务器启动（最多 15 秒）
    if wait_for_server(timeout=15):
        print("[OK] 服务器启动成功")
        return True
    
    print("[FAIL] 服务器启动超时")
    # 打印子进程输出帮助诊断
    if SERVER_PROCESS:
        try:
            stdout, stderr = SERVER_PROCESS.communicate(timeout=2)
            if stdout:
                print(f"  服务器输出: {stdout[:500]}")
        except Exception:
            pass
    stop_server()
    return False


def stop_server():
    """停止测试服务器"""
    global SERVER_PROCESS
    if SERVER_PROCESS:
        print("\n[STOP] 停止测试服务器...")
        SERVER_PROCESS.terminate()
        SERVER_PROCESS.wait(timeout=5)
        SERVER_PROCESS = None


async def test_sync_apis():
    """测试同步 API"""
    import httpx
    
    print("\n" + "="*60)
    print("[TEST] 测试同步 API")
    print("="*60)
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        results = {"passed": 0, "failed": 0, "errors": []}
        
        # 1. 测试 GET /api/config
        print("\n[1/6] GET /api/config")
        try:
            resp = await client.get("/api/config")
            if resp.status_code == 200:
                data = resp.json()
                if "llm" in data or "sources" in data:
                    print("  [OK] 获取配置成功")
                    results["passed"] += 1
                else:
                    print(f"  [WARN] 响应格式异常: {list(data.keys())}")
                    results["failed"] += 1
            else:
                print(f"  [FAIL] HTTP {resp.status_code}: {resp.text[:200]}")
                results["failed"] += 1
        except Exception as e:
            print(f"  [FAIL] 异常: {e}")
            results["failed"] += 1
            results["errors"].append(str(e))
        
        # 2. 测试 GET /api/stats
        print("\n[2/6] GET /api/stats")
        try:
            resp = await client.get("/api/stats")
            if resp.status_code == 200:
                data = resp.json()
                if "total_articles" in data:
                    print(f"  [OK] 获取统计成功: {data['total_articles']} 篇文章")
                    results["passed"] += 1
                else:
                    print(f"  [WARN] 响应格式异常")
                    results["failed"] += 1
            else:
                print(f"  [FAIL] HTTP {resp.status_code}")
                results["failed"] += 1
        except Exception as e:
            print(f"  [FAIL] 异常: {e}")
            results["failed"] += 1
            results["errors"].append(str(e))
        
        # 3. 测试 GET /api/articles (空列表)
        print("\n[3/6] GET /api/articles")
        try:
            resp = await client.get("/api/articles", params={"page": 1, "per_page": 20})
            if resp.status_code == 200:
                data = resp.json()
                if "articles" in data and "total" in data:
                    print(f"  [OK] 获取文章列表成功: {data['total']} 篇")
                    results["passed"] += 1
                else:
                    print(f"  [WARN] 响应格式异常")
                    results["failed"] += 1
            else:
                print(f"  [FAIL] HTTP {resp.status_code}")
                results["failed"] += 1
        except Exception as e:
            print(f"  [FAIL] 异常: {e}")
            results["failed"] += 1
            results["errors"].append(str(e))
        
        # 4. 测试 GET /api/sources
        print("\n[4/6] GET /api/sources")
        try:
            resp = await client.get("/api/sources")
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) or "sources" in data:
                    print(f"  [OK] 获取数据源成功")
                    results["passed"] += 1
                else:
                    print(f"  [WARN] 响应格式异常")
                    results["failed"] += 1
            else:
                print(f"  [FAIL] HTTP {resp.status_code}")
                results["failed"] += 1
        except Exception as e:
            print(f"  [FAIL] 异常: {e}")
            results["failed"] += 1
            results["errors"].append(str(e))
        
        # 5. 测试 GET /api/tasks (空列表)
        print("\n[5/6] GET /api/tasks")
        try:
            resp = await client.get("/api/tasks")
            if resp.status_code == 200:
                data = resp.json()
                if "tasks" in data or isinstance(data, list):
                    print(f"  [OK] 获取任务列表成功")
                    results["passed"] += 1
                else:
                    print(f"  [WARN] 响应格式异常")
                    results["failed"] += 1
            else:
                print(f"  [FAIL] HTTP {resp.status_code}")
                results["failed"] += 1
        except Exception as e:
            print(f"  [FAIL] 异常: {e}")
            results["failed"] += 1
            results["errors"].append(str(e))
        
        # 6. 测试 PUT /api/config (保存配置)
        print("\n[6/6] PUT /api/config (测试保存)")
        try:
            test_config = {"test_key": "test_value"}
            resp = await client.put(
                "/api/config",
                json=test_config,
                headers={"Content-Type": "application/json"},
            )
            # 可能返回 200 或 400（验证失败），但不应 500
            if resp.status_code in (200, 400):
                print(f"  [OK] 保存配置接口正常 (HTTP {resp.status_code})")
                results["passed"] += 1
            else:
                print(f"  [FAIL] HTTP {resp.status_code}: {resp.text[:200]}")
                results["failed"] += 1
        except Exception as e:
            print(f"  [FAIL] 异常: {e}")
            results["failed"] += 1
            results["errors"].append(str(e))
        
        return results


async def test_async_task_api():
    """测试异步任务 API（仅测试任务创建，不等待完成）"""
    import httpx
    
    print("\n" + "="*60)
    print("[TEST] 测试异步任务 API（创建任务）")
    print("="*60)
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        results = {"passed": 0, "failed": 0, "errors": [], "task_ids": []}
        
        # 1. 测试 POST /api/collect/url (异步)
        print("\n[1/3] POST /api/collect/url (创建任务)")
        try:
            resp = await client.post(
                "/api/collect/url",
                data={
                    "url": "https://example.com",
                    "source_type": "rss",
                    "rewrite": "true",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                if "task_id" in data and data.get("status") == "started":
                    task_id = data["task_id"]
                    print(f"  [OK] 任务创建成功: {task_id}")
                    results["passed"] += 1
                    results["task_ids"].append(task_id)
                    
                    # 立即查询任务状态
                    await asyncio.sleep(0.5)
                    task_resp = await client.get(f"/api/tasks/{task_id}")
                    if task_resp.status_code == 200:
                        task_data = task_resp.json()
                        print(f"  任务状态: {task_data.get('status', 'unknown')}")
                else:
                    print(f"  [WARN] 响应格式异常: {data}")
                    results["failed"] += 1
            else:
                print(f"  [FAIL] HTTP {resp.status_code}: {resp.text[:200]}")
                results["failed"] += 1
        except Exception as e:
            print(f"  [FAIL] 异常: {e}")
            results["failed"] += 1
            results["errors"].append(str(e))
        
        # 2. 测试 POST /api/compose (异步)
        print("\n[2/3] POST /api/compose (创建任务)")
        try:
            resp = await client.post(
                "/api/compose",
                data={
                    "title": "测试标题",
                    "content": "这是一段测试内容，用于验证 API 是否正常工作。",
                    "action": "export",
                    "format_type": "markdown",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                if "task_id" in data and data.get("status") == "started":
                    task_id = data["task_id"]
                    print(f"  [OK] 任务创建成功: {task_id}")
                    results["passed"] += 1
                    results["task_ids"].append(task_id)
                else:
                    print(f"  [WARN] 响应格式异常: {data}")
                    results["failed"] += 1
            else:
                print(f"  [FAIL] HTTP {resp.status_code}: {resp.text[:200]}")
                results["failed"] += 1
        except Exception as e:
            print(f"  [FAIL] 异常: {e}")
            results["failed"] += 1
            results["errors"].append(str(e))
        
        # 3. 测试任务状态查询
        print("\n[3/3] GET /api/tasks/{task_id} (查询任务状态)")
        if results["task_ids"]:
            task_id = results["task_ids"][0]
            try:
                resp = await client.get(f"/api/tasks/{task_id}")
                if resp.status_code == 200:
                    data = resp.json()
                    if "id" in data and "status" in data:
                        print(f"  [OK] 查询任务状态成功: {data['status']}")
                        results["passed"] += 1
                    else:
                        print(f"  [WARN] 响应格式异常")
                        results["failed"] += 1
                else:
                    print(f"  [FAIL] HTTP {resp.status_code}")
                    results["failed"] += 1
            except Exception as e:
                print(f"  [FAIL] 异常: {e}")
                results["failed"] += 1
                results["errors"].append(str(e))
        else:
            print("  [WARN] 无可用 task_id，跳过")
            results["failed"] += 1
        
        return results


async def test_task_polling():
    """测试任务轮询（等待任务完成）"""
    import httpx
    
    print("\n" + "="*60)
    print("[POLL] 测试任务轮询（等待任务完成）")
    print("="*60)
    
    # 先创建一个快速任务（compose + export）
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        print("\n创建测试任务...")
        resp = await client.post(
            "/api/compose",
            data={
                "content": "测试内容",
                "action": "export",
                "format_type": "markdown",
            },
        )
        
        if resp.status_code != 200:
            print(f"[FAIL] 创建任务失败: HTTP {resp.status_code}")
            return {"passed": 0, "failed": 1, "errors": [resp.text]}
        
        task_id = resp.json().get("task_id")
        if not task_id:
            print("[FAIL] 未返回 task_id")
            return {"passed": 0, "failed": 1, "errors": ["No task_id"]}
        
        print(f"[OK] 任务已创建: {task_id}")
        print("[WAIT] 轮询任务状态...")
        
        # 轮询最多 30 秒
        for i in range(30):
            await asyncio.sleep(1)
            resp = await client.get(f"/api/tasks/{task_id}")
            if resp.status_code != 200:
                print(f"[FAIL] 查询任务失败: HTTP {resp.status_code}")
                return {"passed": 0, "failed": 1, "errors": [resp.text]}
            
            data = resp.json()
            status = data.get("status")
            progress = data.get("progress", 0)
            
            print(f"  [{i+1}s] 状态: {status}, 进度: {progress}%")
            
            if status == "done":
                print(f"[OK] 任务完成!")
                if "result" in data:
                    print(f"  结果: {json.dumps(data['result'], ensure_ascii=False)[:200]}")
                return {"passed": 1, "failed": 0, "errors": []}
            elif status == "error":
                print(f"[FAIL] 任务失败: {data.get('message', 'unknown')}")
                return {"passed": 0, "failed": 1, "errors": [data.get("message")]}
        
        print("[FAIL] 任务超时（30 秒）")
        return {"passed": 0, "failed": 1, "errors": ["Task timeout"]}


async def cleanup():
    """清理测试数据"""
    import httpx
    
    print("\n" + "="*60)
    print("[CLEANUP] 清理测试数据")
    print("="*60)
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        # 清空所有文章
        print("\n清空文章...")
        try:
            resp = await client.post("/api/articles/clear")
            if resp.status_code == 200:
                data = resp.json()
                print(f"  [OK] {data.get('message', '已清空')}")
            else:
                print(f"  [WARN] 清空失败: HTTP {resp.status_code}")
        except Exception as e:
            print(f"  [FAIL] 异常: {e}")


async def main():
    """主测试流程"""
    print("="*60)
    print("[TEST] Content Aggregator API 集成测试")
    print("="*60)
    
    # 检查依赖
    try:
        import httpx
    except ImportError:
        print("[FAIL] 缺少依赖: pip install httpx")
        return
    
    # 启动服务器
    if not start_server():
        return
    
    try:
        # 测试同步 API
        sync_results = await test_sync_apis()
        
        # 测试异步任务 API
        async_results = await test_async_task_api()
        
        # 测试任务轮询
        polling_results = await test_task_polling()
        
        # 清理
        await cleanup()
        
        # 汇总结果
        print("\n" + "="*60)
        print("[RESULTS] 测试结果汇总")
        print("="*60)
        
        total_passed = sync_results["passed"] + async_results["passed"] + polling_results["passed"]
        total_failed = sync_results["failed"] + async_results["failed"] + polling_results["failed"]
        
        print(f"\n[PASS] 通过: {total_passed}")
        print(f"[FAIL] 失败: {total_failed}")
        
        all_errors = sync_results["errors"] + async_results["errors"] + polling_results["errors"]
        if all_errors:
            print(f"\n错误详情:")
            for i, err in enumerate(all_errors, 1):
                print(f"  {i}. {err}")
        
        print("\n" + "="*60)
        if total_failed == 0:
            print("[DONE] 所有测试通过!")
        else:
            print(f"[WARN] 有 {total_failed} 个测试失败，请检查 above.")
        print("="*60)
        
    finally:
        stop_server()


if __name__ == "__main__":
    asyncio.run(main())
