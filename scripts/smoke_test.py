from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from app.main import app


if __name__ == "__main__":
    client = TestClient(app)

    health = client.get("/health")
    print("health:", health.status_code, health.json())

    payload = {
        "user_id": "u-demo",
        "thread_id": "t-demo",
        "message": "查询型号 STM32F103C8T6 的库存",
        "auto_approve": True,
    }
    chat = client.post("/v1/chat", json=payload)
    print("chat:", chat.status_code)
    print(chat.json())
