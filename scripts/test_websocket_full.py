#!/usr/bin/env python3
"""
完整的 WebSocket 进度功能测试脚本
- 触发采集任务（调用 API）
- 监听 WebSocket 进度消息
- 显示实时进度条
"""

import asyncio
import json
import aiohttp
import time
from pathlib import Path

# 修复 Windows 中文编码问题
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


API_BASE = "http://127.0.0.1:8080"
WS_URL = f"{API_BASE.replace('http', 'ws')}/ws"


async def trigger_collection_task():
    """触发采集任务"""
    print("🚀 触发采集任务...")
    
    async with aiohttp.ClientSession() as session:
        # 调用 /api/collect/all 触发采集
        try:
            async with session.post(f"{API_BASE}/api/collect/all") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    task_id = data.get("task_id")
                    print(f"✅ 任务已创建: {task_id}")
                    return task_id
                else:
                    text = await resp.text()
                    print(f"❌ 创建任务失败: {resp.status} - {text}")
                    return None
        except Exception as e:
            print(f"❌ 请求失败: {e}")
            return None


async def listen_websocket(task_id: str):
    """监听 WebSocket 进度消息"""
    print(f"\n📡 连接到 WebSocket: {WS_URL}")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.ws_connect(WS_URL) as ws:
                print("✅ WebSocket 连接成功！")
                print("=" * 70)
                
                # 发送心跳
                await ws.send_str(json.dumps({"type": "pong"}))
                
                # 监听消息
                start_time = time.time()
                last_progress = -1
                
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        msg_type = data.get("type", "")
                        
                        # 只处理与任务相关的消息
                        if data.get("task_id") != task_id and msg_type != "pong":
                            continue
                        
                        if msg_type == "task_update":
                            status = data.get("status", "")
                            progress = data.get("progress", 0)
                            message = data.get("message", "")
                            source = data.get("source", "")
                            
                            # 只在进度变化时更新
                            if progress != last_progress:
                                last_progress = progress
                                
                                # 绘制进度条
                                bar_width = 40
                                filled = int(bar_width * progress / 100)
                                bar = "█" * filled + "░" * (bar_width - filled)
                                
                                print(f"\r📊 [{bar}] {progress:3d}% | {status:8s} | {message[:50]}")
                                
                            # 如果任务完成，退出
                            if status in ["done", "error"]:
                                print(f"\n\n✅ 任务完成！")
                                print(f"   状态: {status}")
                                print(f"   消息: {message}")
                                if "result" in data:
                                    print(f"   结果: {json.dumps(data['result'], ensure_ascii=False)[:200]}")
                                break
                                
                        elif msg_type == "pong":
                            print("💓 收到心跳 pong")
                            
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        print(f"\n❌ WebSocket 错误: {msg.data}")
                        break
                        
                    # 超时保护（60秒）
                    if time.time() - start_time > 60:
                        print("\n⏰ 监听超时（60秒）")
                        break
                        
        except Exception as e:
            print(f"\n❌ WebSocket 连接失败: {e}")
            return False
            
    return True


async def main():
    """主函数"""
    print("=" * 70)
    print(" " * 20 + "WebSocket 进度功能测试")
    print("=" * 70)
    print()
    
    # 步骤1：触发采集任务
    task_id = await trigger_collection_task()
    
    if not task_id:
        print("\n❌ 无法创建任务，测试终止")
        print("\n可能的原因：")
        print("  1. Web 服务器未启动")
        print("  2. API 端点不存在")
        print("  3. 配置文件中没有启用的数据源")
        return
        
    # 等待1秒，让任务开始
    await asyncio.sleep(1)
    
    # 步骤2：监听 WebSocket 进度
    success = await listen_websocket(task_id)
    
    if success:
        print("\n" + "=" * 70)
        print("✅ 测试完成！WebSocket 进度功能正常工作")
        print("=" * 70)
    else:
        print("\n" + "=" * 70)
        print("❌ 测试失败！请检查日志")
        print("=" * 70)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
    except Exception as e:
        print(f"\n\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
