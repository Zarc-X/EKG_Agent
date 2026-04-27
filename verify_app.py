from fastapi.testclient import TestClient
from app.main import app
import json

client = TestClient(app)

# Test 1: /v1/admin/change-explanations
print("--- Testing /v1/admin/change-explanations ---")
# Use a thread_id that might have data if web-thread is empty
response = client.get("/v1/admin/change-explanations?thread_id=web-thread&branch=main&limit=5")
print(f"Status Code: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    # Check if items list exists or if it's a direct list
    items = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get('items', [])
    
    print(f"Count: {len(items)}")
    if len(items) > 0:
        first_item = items[0]
        print(f"First item keys: {list(first_item.keys())}")
        print(f"management_summary in keys: {'management_summary' in first_item}")
        print(f"risk_level in keys: {'risk_level' in first_item}")
        print(f"rollback_recommendation in keys: {'rollback_recommendation' in first_item}")
    else:
        # Check database directly if empty
        from app.db.mongodb import MongoDB
        import asyncio
        async def check_db():
            db = MongoDB()
            await db.connect()
            coll = db.db["change_explanations"]
            count = await coll.count_documents({})
            print(f"Total documents in change_explanations collection: {count}")
            if count > 0:
                doc = await coll.find_one()
                print(f"Sample DB doc keys: {list(doc.keys())}")
        try:
            asyncio.run(check_db())
        except:
            pass

# Test 2: / (Home Page)
print("\n--- Testing / (Index HTML) ---")
response = client.get("/")
print(f"Status Code: {response.status_code}")
if response.status_code == 200:
    html = response.text
    checks = ["变更解释器", "id=\"changeExplainList\"", "id=\"refreshChangeExplainBtn\"", "loadChangeExplanations"]
    for check in checks:
        print(f"Contains '{check}': {check in html}")
