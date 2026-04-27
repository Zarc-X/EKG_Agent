import json
from fastapi.testclient import TestClient
from app.main import create_app
from app.api.routes.workflow import approval

try:
    app = create_app()
    client = TestClient(app)
    
    # Create ticket (mocking or using internal call if possible, but let's assume we can call the function or an endpoint)
    # Using ticket creation via internal logic or dedicated endpoint if available
    # The prompt says '通过 workflow.approval.create_ticket'
    
    # Since we need to test /v1/approvals, let's create a ticket first.
    # We might need a database session or mock it.
    # For a TestClient, usually we hit endpoints.
    
    # Trying to create a ticket via some internal means if appropriate or just check list and details.
    # Proceeding with checking /v1/approvals and details.
    
    # Step 1: Create ticket (using any POST endpoint if exists)
    # Assuming there's a POST /v1/approvals or internal method
    # Let's try to find the ticket creation logic or use a dummy existing one.
    
    # Re-reading prompt: "创建一张审批单（通过 workflow.approval.create_ticket）"
    # This implies importing the function.
    
    from app.db.session import SessionLocal
    db = SessionLocal()
    ticket = approval.create_ticket(db, title="Test Ticket", content="Test Content", applicant="Test User")
    ticket_id = ticket.id
    db.commit()
    db.close()

    # Step 2: Call /v1/approvals
    res_list = client.get("/v1/approvals")
    list_valid = res_list.status_code == 200
    
    # Step 3: Call /v1/approvals/{ticket_id}
    res_detail = client.get(f"/v1/approvals/{ticket_id}")
    detail_valid = res_detail.status_code == 200
    detail_data = res_detail.json()
    
    results = {
        "ticket_id": ticket_id,
        "list_status": res_list.status_code,
        "detail_status": res_detail.status_code,
        "has_ticket_id": "id" in detail_data or "ticket_id" in detail_data,
        "approval_copilot": detail_data.get("approval_copilot", "NotFound")
    }
    print(json.dumps(results, ensure_ascii=False))

except Exception as e:
    import traceback
    print(traceback.format_exc())
