import asyncio
from dotenv import load_dotenv
load_dotenv()
from backend.routes.student import resources
from backend.supabase_client import get_supabase
from starlette.requests import Request
from unittest.mock import MagicMock

async def test():
    supabase = get_supabase()
    # 1. Get student
    res = supabase.table("student").select("*").eq("student_id", "25AITS265").execute()
    if not res.data:
        print("Student not found")
        return
    student = res.data[0]
    
    mock_user = {
        "user_id": student['user_id'],
        "role": "student",
        "sub": student['name']
    }
    
    # Mock Request
    scope = {"type": "http"}
    req = Request(scope)
    
    print(f"Calling resources for {student['name']}...")
    try:
        resp = await resources(req, user=mock_user)
        print("Success!")
        print("Status Code:", resp.status_code)
    except Exception as e:
        print(f"CRASHED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test())
