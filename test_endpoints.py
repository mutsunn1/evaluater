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
        start_resp.raise_for_status()
        start_data = start_resp.json()
        print("Start Response:", start_data)

        session_id = start_data.get("session_id")

        # 2. 连续聊天，直到评测结束
        print("\n=== 2. 测试聊天接口（循环至完成） ===")
        for idx in range(1, 10):
            chat_resp = await client.post(
                f"{base_url}/api/assessment/chat",
                json={
                    "session_id": session_id,
                    "user_response_text": "我把房间整理好了，而且已经把书放回书架了。",
                    "actual_time_sec": 8.5 + idx * 0.4,
                },
            )
            chat_resp.raise_for_status()
            chat_data = chat_resp.json()
            print(f"Round {idx}:", chat_data)

            # 严格规范模式：返回字段必须与状态一致，且不应出现多余空字段。
            if chat_data.get("status") == "in_progress":
                assert set(chat_data.keys()) == {"status", "next_question", "expected_time_sec"}
                assert isinstance(chat_data["next_question"], str) and chat_data["next_question"]
                assert isinstance(chat_data["expected_time_sec"], (int, float))

            if chat_data.get("status") == "completed":
                assert set(chat_data.keys()) == {"status", "redirect_url"}
                assert chat_data["redirect_url"].startswith("/api/assessment/report/")
                break

        # 3. 拉取最终报告
        print("\n=== 3. 测试报告接口 ===")
        report_resp = await client.get(f"{base_url}/api/assessment/report/{session_id}")
        report_resp.raise_for_status()
        print("Report Response:", report_resp.json())


if __name__ == "__main__":
    asyncio.run(run_tests())
