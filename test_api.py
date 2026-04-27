from fastapi.testclient import TestClient
from app.main import app
import json

client = TestClient(app)
payload = {
    "messages": [{"role": "user", "content": "把 components 里库存小于10的库存加1"}],
    "auto_approve": False
}
response = client.post("/v1/chat", json=payload)
print(f"Status: {response.status_code}")
data = response.json()
has_copilot = "approval_copilot" in data
print(f"Contains approval_copilot: {has_copilot}")
ticket_id = data.get("approval_copilot", {}).get("approval_ticket_id") if has_copilot else None
print(f"approval_ticket_id: {ticket_id}")

if ticket_id:
    resp_appr = client.get(f"/v1/approvals/{ticket_id}")
    print(f"Approval Status Code: {resp_appr.status_code}")
    print(f"Approval Contains approval_copilot: {'approval_copilot' in resp_appr.json()}")
