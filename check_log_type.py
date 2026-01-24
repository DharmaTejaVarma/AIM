import sys
import os
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.getcwd())

from backend.supabase_client import get_supabase

def check_log_type():
    supabase = get_supabase()
    t = "activity_log"
    try:
        res = supabase.table(t).select("id").limit(1).execute()
        if res.data:
            sample = res.data[0]['id']
            print(f"Table '{t}': Sample ID = {sample} (Type: {type(sample).__name__})")
        else:
            print(f"Table '{t}': Empty")
            # Try inserting dummy to check type? No, too risky/complex.
            # Just enable UUID logic in deletion.
    except Exception as e:
        print(f"Table '{t}': Error - {e}")

if __name__ == "__main__":
    check_log_type()
