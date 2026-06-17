#!/usr/bin/env python3
"""
API 集成测试脚本 (纯测试，不负责启停服务器)

假设服务器已在 http://127.0.0.1:8000 运行

使用方法：
    # 先手动启动服务器：
    # cd content-aggregator && python -m uvicorn web.server:app --host 127.0.0.1 --port 8000
    
    # 再运行测试：
    python scripts/test_api_pure.py
"""

import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

BASE_URL = "http://127.0.0.1:8000"


async def test_sync_apis():
    """测试同步 API"""
    import httpx
    
    print("\n" + "="*60)
    print("[TEST] 测试同步 API")
    print("="*60)
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        results = {"passed": 0, "failed": 0, "errors": []}
        
        # 1. GET /api/config
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
        
        # 2. GET /api/stats
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
        
        # 3. GET /api/articles
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
        
        # 4. GET /api/sources
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
        
        # 5. GET /api/tasks
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
        
        # 6. PUT /api/config
        print("\n[6/6] PUT /api/config (测试保存)")
        try:
            test_config = {"test_key": "test_value"}
            resp = await client.put(
                "/api/config",
                json=test_config,
                headers={"Content-Type": "application/json"},
            )
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


async def test_async_task_create():
    """测试异步任务创建（不等待完成）"""
    import httpx
    
    print("\n" + "="*60)
    print("[TEST] 测试异步任务创建")
    print("="*60)
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        results = {"passed": 0, "failed": 0, "errors": [], "task_ids": []}
        
        # 1. POST /api/compose (最轻量的异步任务)
        print("\n[1/2] POST /api/compose (创建任务)")
        try:
            resp = await client.post(
                "/api/compose",
                data={
                    "title": "API测试",
                    "content": "这是一段测试内容，用于验证异步任务 API 是否正常工作。",
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
        
        # 2. GET /api/tasks/{task_id}
        print("\n[2/2] GET /api/tasks/{task_id}")
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
            print("  [SKIP] 无可用 task_id")
            results["failed"] += 1
        
        return results


async def test_task_polling(task_id):
    """轮询任务直到完成或超时"""
    import httpx
    
    print("\n" + "="*60)
    print(f"[POLL] 轮询任务 {task_id[:16]}...")
    print("="*60)
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        for i in range(60):  # 最多等 60 秒
            await asyncio.sleep(1)
            try:
                resp = await client.get(f"/api/tasks/{task_id}")
                if resp.status_code != 200:
                    print(f"  [FAIL] 查询失败: HTTP {resp.status_code}")
                    return {"passed": 0, "failed": 1, "errors": [resp.text]}
                
                data = resp.json()
                status = data.get("status")
                progress = data.get("progress", 0)
                
                if i % 5 == 0:
                    print(f"  [{i+1}s] 状态: {status}, 进度: {progress}%")
                
                if status == "done":
                    print(f"  [OK] 任务完成!")
                    if "result" in data:
                        result_str = json.dumps(data["result"], ensure_ascii=False)[:300]
                        print(f"  结果: {result_str}")
                    return {"passed": 1, "failed": 0, "errors": []}
                elif status == "error":
                    msg = data.get("message", "unknown")
                    print(f"  [FAIL] 任务失败: {msg}")
                    return {"passed": 0, "failed": 1, "errors": [msg]}
            except Exception as e:
                print(f"  [FAIL] 轮询异常: {e}")
                return {"passed": 0, "failed": 1, "errors": [str(e)]}
        
        print("  [FAIL] 任务超时（60秒）")
        return {"passed": 0, "failed": 1, "errors": ["Task timeout"]}


async def cleanup():
    """清理测试数据"""
    import httpx
    
    print("\n" + "="*60)
    print("[CLEANUP] 清理测试数据")
    print("="*60)
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
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
    print("="*60)
    print("[TEST] Content Aggregator API 集成测试")
    print("="*60)
    print(f"目标: {BASE_URL}")
    print("提示: 请确保服务器已启动")
    print("="*60)
    
    # 检查依赖
    try:
        import httpx
    except ImportError:
        print("[FAIL] 缺少依赖: pip install httpx")
        return
    
    # 检查服务器是否可访问
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{BASE_URL}/api/config", timeout=3)
            print(f"\n[OK] 服务器可访问 (HTTP {resp.status_code})")
    except Exception as e:
        print(f"\n[FAIL] 无法连接服务器: {e}")
        print(f"请先启动服务器: cd {PROJECT_ROOT} && python -m uvicorn web.server:app --host 127.0.0.1 --port 8000")
        return
    
    # 测试同步 API
    sync_results = await test_sync_apis()
    
    # 测试异步任务创建
    async_results = await test_async_task_create()
    
    # 轮询任务完成
    polling_results = {"passed": 0, "failed": 0, "errors": []}
    if async_results.get("task_ids"):
        task_id = async_results["task_ids"][0]
        polling_results = await test_task_polling(task_id)
    
    # 清理
    await cleanup()
    
    # 汇总
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
        print(f"[WARN] 有 {total_failed} 个测试失败")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
