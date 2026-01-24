import os
from backend.supabase_client import get_supabase

def verify_schema():
    print("--- Verifying Student Table Schema ---")
    supabase = get_supabase()
    
    try:
        # Try to select the specific column 'batch'
        print("Checking for 'batch' column in 'student' table...")
        res = supabase.table("student").select("batch").limit(1).execute()
        print("[SUCCESS] 'batch' column exists.")
    except Exception as e:
        print(f"[FAILURE] Error selecting 'batch': {e}")
        if "PGRST204" in str(e):
             print("\n>>> CONFIRMED: The 'batch' column is MISSING from your database.")
             print(">>> YOU MUST RUN THE SQL FIX script in Supabase.")

if __name__ == "__main__":
    verify_schema()
