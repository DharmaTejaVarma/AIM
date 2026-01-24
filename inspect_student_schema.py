import sys
import os
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.getcwd())

from backend.supabase_client import get_supabase

def list_student_columns():
    supabase = get_supabase()
    try:
        # Fetch one record to see keys
        res = supabase.table("student").select("*").limit(1).execute()
        if res.data:
            print("Columns in 'student' table:", list(res.data[0].keys()))
        else:
            print("Table 'student' is empty. Cannot infer columns from data.")
            # Fallback: Try valid insert error to get schema? No.
            # Just assume standard columns from models.py if empty.
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_student_columns()
