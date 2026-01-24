from datetime import datetime
import asyncio
from dotenv import load_dotenv
from dotenv import load_dotenv
load_dotenv()
from backend.routes.faculty import fetch_timetable, FetchTimetableRequest
from backend.supabase_client import get_supabase

# Mock User Data
# We need a valid faculty user_id from DB to test real queries.
# Let's fetch one valid faculty first.

async def test():
    supabase = get_supabase()
    # 1. Get a faculty
    res = supabase.table("faculty").select("*").limit(1).execute()
    if not res.data:
        print("No faculty found to test.")
        return
        
    fac = res.data[0]
    print(f"Testing with Faculty: {fac['name']} (ID: {fac['id']}, UserID: {fac['user_id']})")
    
    mock_user = {
        "user_id": fac['user_id'],
        "role": "faculty",
        "sub": fac['name']
    }
    
    # 2. Test Fetch Timetable
    req = FetchTimetableRequest(date="2026-01-22") # Todayish
    
    print("\nCalling fetch_timetable...")
    try:
        result = await fetch_timetable(req, user=mock_user)
        print("Success!")
        # print(result)
        print(f"Days: {len(result.get('days', []))}")
        print(f"Periods: {len(result.get('periods', []))}")
        print(f"Data Keys: {list(result.get('timetable', {}).keys())}")
        
    except Exception as e:
        print(f"CRASHED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test())
