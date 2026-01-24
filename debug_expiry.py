import sys
import os
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.getcwd())

from backend.supabase_client import get_supabase

def debug_expiry_logic():
    try:
        supabase = get_supabase()
        print("Attempting to select 'batch' column...")
        
        # Test 1: simple select to see if column exists
        try:
            res = supabase.table("student").select("batch").limit(1).execute()
            print(f"Select success. Data sample: {res.data}")
        except Exception as e:
            print(f"Select FAILED. Error: {e}")
            return

        # Test 2: The actual query
        print("Running full logic query...")
        res = supabase.table("student").select("id, batch, status").eq("status", "active").not_.is_("batch", "null").execute()
        students = res.data
        print(f"Found {len(students)} active students with batch.")
        
        # Test 3: Iteration logic
        for s in students:
            print(f"Processing student {s.get('id')} with batch {s.get('batch')}")

    except Exception as e:
        print(f"Global Error: {e}")

if __name__ == "__main__":
    debug_expiry_logic()
