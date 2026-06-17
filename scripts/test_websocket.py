#!/usr/bin/env python3
"""
测试 WebSocket 进度功能
"""
import asyncio
import json
import aiohttp


async def test_websocket():
    """测试 WebSocket 连接和进度消息"""
    url = "http://127.0.0.1:8080/ws"
    
    print(f"🔌 连接到 WebSocket: {url}")
    
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(url) as ws:
            print("✅ WebSocket 连接成功！")
            
            # 发送心跳 pong
            await ws.send_str(json.dumps({"type": "pong"}))
            print("📤 发送心跳 pong")
            
            # 监听消息（最多等待 30 秒）
            print("\n📥 等待进度消息...\n")
            
            try:
                for i in range(30):  # 最多等待 30 秒
                    msg = await asyncio.wait_for(ws.receive(), timeout=1.0)
                    
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        print(f"📨 收到消息: {json.dumps(data, ensure_ascii=False, indent=2)}")
                        
                        # 如果是任务更新，显示进度
                        if data.get("type") == "task_update":
                            status = data.get("status", "")
                            progress = data.get("progress", 0)
                            message = data.get("message", "")
                            print(f"📊 任务状态: {status} | 进度: {progress}% | 消息: {message}")
                            print("-" * 60)
                            
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        print(f"❌ WebSocket 错误: {msg.data}")
                        break
                        
            except asyncio.TimeoutError:
                print("\n⏰ 等待超时（30秒），停止监听")
            except Exception as e:
                print(f"\n❌ 错误: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("WebSocket 进度功能测试")
    print("=" * 60)
    print("\n提示：请先在浏览器中触发一个采集任务（点击'开始采集'按钮）")
    print("然后此脚本会接收到实时进度消息\n")
    
    input("按 Enter 开始监听 WebSocket 消息...")
    
    asyncio.run(test_websocket())
