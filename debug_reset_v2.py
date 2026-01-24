import sys
import os
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.getcwd())

from backend.supabase_client import get_supabase

def test_delete():
    supabase = get_supabase()
    # Ordered list
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
        print(f"--- Table: {t} ---")
        try:
            # 1. Check ID type
            res = supabase.table(t).select("id").limit(1).execute()
            if res.data:
                sample_id = res.data[0]['id']
                print(f"  Sample ID: {sample_id} ({type(sample_id).__name__})")
                
                is_uuid = isinstance(sample_id, str) and len(sample_id) > 20 # Rough check
                
                # 2. Attempt Delete
                if is_uuid:
                    print(f"  Detected UUID, using 'neq.0000...'")
                    # Comparing UUID to '0' usually fails. Use a valid UUID or another logic.
                    # Or 'not.is.null' if supported? PostgREST: 'id=not.is.null'
                    # Supabase-py: .neq('id', 'null') ? No.
                    # Best hack: .gt('id', '00000000-0000-0000-0000-000000000000')
                    supabase.table(t).delete().gt("id", "00000000-0000-0000-0000-000000000000").execute()
                else:
                    print(f"  Detected Int, using 'neq.0'")
                    supabase.table(t).delete().neq("id", 0).execute()
                    
                print(f"  SUCCESS: Deleted rows from {t}")
            else:
                print(f"  Empty table, trying generic delete to be sure...")
                # If empty, delete shouldn't fail even with type mismatch usually? 
                # Actually it might.
                try:
                     supabase.table(t).delete().neq("id", 0).execute()
                     print(f"  SUCCESS: Checked {t} (Empty, Int-check passed)")
                except:
                     print("  Switching to UUID check for empty table...")
                     supabase.table(t).delete().gt("id", "00000000-0000-0000-0000-000000000000").execute()
                     print(f"  SUCCESS: Checked {t} (Empty, UUID-check passed)")

        except Exception as e:
            print(f"  FAILED: {t} - {str(e)}")

if __name__ == "__main__":
    test_delete()
