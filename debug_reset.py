import sys
import os
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.getcwd())

from backend.supabase_client import get_supabase

def test_delete():
    supabase = get_supabase()
    # List from admin.py
    tables = [
        "mark", 
        "attendance", 
        "fee", 
        "timetable", 
        "class_offering", 
        "subject", 
        "announcement", 
        "student", 
        "faculty", 
        "department"
    ]
    
    for t in tables:
        print(f"Testing delete on table '{t}'...")
        try:
            # Try the logic used in admin.py
            # Note: This WILL delete data if it works. Use with caution (User wanted reset anyway)
            # We will try to fetch first to see ID type
            res = supabase.table(t).select("id").limit(1).execute()
            if res.data:
                sample_id = res.data[0]['id']
                print(f"  Sample ID: {sample_id} (Type: {type(sample_id)})")
                
            # Try delete
            supabase.table(t).delete().neq("id", 0).execute()
            print(f"  SUCCESS: {t}")
        except Exception as e:
            print(f"  FAILED: {t} - {e}")

if __name__ == "__main__":
    test_delete()
