import asyncio
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
from backend.routes.student import fetch_timetable, FetchTimetableRequest
from backend.supabase_client import get_supabase

async def test():
    supabase = get_supabase()
    # 1. Get the student '25AITS265' (known valid from previous steps)
    # The username acts as student_id in 'student' table often, or let's search by username in 'users' or 'student'
    # Actually 'get_current_student' usually takes user_id from auth.
    # Let's find the student record first.
    
    res = supabase.table("student").select("*").eq("student_id", "25AITS265").execute()
    if not res.data:
        print("Student '25AITS265' not found. Trying flexible search.")
        res = supabase.table("student").select("*").limit(1).execute()
        
    if not res.data:
        print("No students found.")
        return
        
    student = res.data[0]
    print(f"Testing with Student: {student['name']} (ID: {student['id']}, UserID: {student['user_id']})")
    
    mock_user = {
        "user_id": student['user_id'],
        "role": "student",
        "sub": student['name']
    }
    
    # 2. Test Fetch Timetable
    # Try invalid date format or empty to see if it causes 500
    try:
        print("Testing with EMPTY date...")
        req = FetchTimetableRequest(date="")
        await fetch_timetable(req, user=mock_user)
    except Exception as e:
        print(f"Empty Date Crash: {e}")

    # Correct date but maybe something else
    req = FetchTimetableRequest(date=datetime.now().strftime('%Y-%m-%d'))
    
    print(f"\nCalling fetch_timetable for date: {req.date}...")
    try:
        result = await fetch_timetable(req, user=mock_user)
        print("Success!")
        # print(result)
        print(f"Days: {len(result.get('days', []))}")
        print(f"Periods: {len(result.get('periods', []))}")
        
    except Exception as e:
        print(f"CRASHED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test())
