import json
from fastapi.testclient import TestClient
from app.main import create_app
try:
    app = create_app()
    client = TestClient(app)
    response = client.get("/")
    html = response.text
    markers = ["人工审批台", 'id="approvalsList"', 'id="approveTicketBtn"', 'id="rejectTicketBtn"', 'id="approvalCopilotCard"', 'id="approvalFilter"']
    results = {m: (m in html) for m in markers}
    print(json.dumps(results, ensure_ascii=False))
except Exception as e:
    import traceback
    print(traceback.format_exc())
