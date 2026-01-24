
import asyncio
import os
import sys

# Add current directory to path so we can import backend modules
sys.path.append(os.getcwd())

# Load .env manually
dotenv_path = os.path.join(os.getcwd(), '.env')
if os.path.exists(dotenv_path):
    with open(dotenv_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()


from backend.supabase_client import get_supabase
from backend.auth import get_password_hash

async def test_import_logic():
    print("Starting import test...")
    
    supabase = get_supabase()
    
    # Sample data that caused the error (inferred from context)
    # We'll try to insert a single test student
    row = {
        "student_id": "TEST_IMPORT_001",
        "name": "Test Student Import",
        "email": "test_import_001@example.com",
        "branch": "CSE",
        "year": 1,
        "semester": 1,
        "section": "A",
        "phone": "1234567890",
        "date_of_birth": "2000-01-01",
        "status": "active"
    }
    
    sid = row.get('student_id')
    print(f"Processing student: {sid}")
    
    try:
        # 1. Check existing
        print(f"DEBUG: Checking existing student with ID: {sid}")
        query = supabase.table("student").select("id, user_id").eq("student_id", sid).maybe_single()
        print(f"DEBUG: Query constructed: {query}")
        
        existing_s = query.execute()
        print(f"DEBUG: Existing check result object: {existing_s}")
        print(f"DEBUG: Type of result: {type(existing_s)}")
        
        if existing_s and hasattr(existing_s, 'data'):
             print(f"DEBUG: Data: {existing_s.data}")
        else:
             print("DEBUG: existing_s is None or has no data attribute")

        if existing_s and existing_s.data:

            print("Student exists, updating...")
            # Simulate update logic
            s_update = {
                 "name": row.get('name'),
                 "email": row.get('email'),
                 "branch": row.get('branch'),
                 "year": row.get('year'),
                 "semester": row.get('semester'),
                 "section": row.get('section'),
                 "phone": row.get('phone'),
                 "status": "active"
            }
            res = supabase.table("student").update(s_update).eq("student_id", sid).execute()
            print(f"Update result: {res}")
        else:
            print("Student does not exist, creating...")
            # Simulate insert logic
            p_hash = get_password_hash("student123")
            print("Password hashed.")
            
            print("Inserting user...")
            user_res = supabase.table("users").insert({
                "username": sid,
                "email": row.get('email'),
                "password_hash": p_hash,
                "role": "student",
                "name": row.get('name')
            }).execute()
            print(f"User Insert Result: {user_res}")
            
            if user_res.data:
                 uid = user_res.data[0]['id']
                 print(f"User created with ID: {uid}")
                 s_data = {
                     "user_id": uid,
                     "student_id": sid,
                     "name": row.get('name'),
                     "email": row.get('email'),
                     "branch": row.get('branch'),
                     "year": row.get('year'),
                     "semester": row.get('semester'),
                     "section": row.get('section'),
                     "phone": row.get('phone'),
                     "date_of_birth": row.get('date_of_birth'),
                     "status": "active"
                 }
                 print("Inserting student...")
                 student_res = supabase.table("student").insert(s_data).execute()
                 print(f"Student Insert Result: {student_res}")
            else:
                print("FAILED: User insert returned no data.")

    except Exception as e:
        print(f"EXCEPTION CAUGHT: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_import_logic())
