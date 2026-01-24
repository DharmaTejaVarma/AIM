from backend.supabase_client import get_supabase
import json
import os
from dotenv import load_dotenv

load_dotenv()


def inspect_table():
    supabase = get_supabase()
    try:
        print("\nChecking for subject table:")
        try:
            res = supabase.table("subject").select("*").limit(1).execute()
            if res.data:
                print("subject table columns:", list(res.data[0].keys()))
            else:
                print("subject table exists but empty.")
        except Exception as e:
            print(f"Error checking subject: {e}")

        print("\nChecking for subjects_master table:")
        try:
            res = supabase.table("subjects_master").select("*").limit(1).execute()
            if res.data:
                print("subjects_master table columns:", list(res.data[0].keys()))
            else:
                print("subjects_master table exists but empty.")
        except Exception as e:
            print(f"Error checking subjects_master: {e}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_table()
