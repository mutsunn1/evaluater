import asyncio
import httpx

async def run_tests():
    base_url = "http://127.0.0.1:18000"
    
    async with httpx.AsyncClient() as client:
        # 1. 启动评测
        print("=== 1. 测试启动评测 ===")
        start_resp = await client.post(
            f"{base_url}/api/assessment/start",
            json={"user_id": "test_user_001", "self_assessed_level": "INTERMEDIATE"}
        )
        start_data = start_resp.json()
        print("Start Response:", start_data)
        
        session_id = start_data.get("session_id")
        
        # 2. 聊天过程
        print("\n=== 2. 测试聊天接口 ===")
        chat_resp = await client.post(
            f"{base_url}/api/assessment/chat",
            json={
                "session_id": session_id,
                "user_response_text": "我把书放在桌子上了",
                "actual_time_sec": 8.5
            }
        )
        print("Chat Response:", chat_resp.json())
        
        # 3. HLR 学习模块测试
        print("\n=== 3. 测试 HLR 学习辅助模块 ===")
        trace_resp = await client.post(
            f"{base_url}/api/learning/trace",
            json={
                "user_id": "test_user_001",
                "kc_id": "G_Structure_Ba",
                "is_correct": True
            }
        )
        print("Learning Trace Response:", trace_resp.json())
        
        retention_resp = await client.get(
            f"{base_url}/api/learning/retention",
            params={
                "user_id": "test_user_001",
                "kc_id": "G_Structure_Ba"
            }
        )
        print("Learning Retention Response:", retention_resp.json())

if __name__ == "__main__":
    asyncio.run(run_tests())
