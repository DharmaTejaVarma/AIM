import os
import sys
from dotenv import load_dotenv

# Add current dir to path to find backend
sys.path.append(os.getcwd())

from backend.database import get_supabase

load_dotenv()
supabase = get_supabase()

def inspect_schema():
    print("--- Inspecting class_offering schema ---")
    try:
        # Fetch one record
        res = supabase.table("class_offering").select("*").limit(1).execute()
        if res.data:
            print(f"Columns: {list(res.data[0].keys())}")
        else:
            print("No data in class_offering, cannot infer columns.")
            
        # Also check if course_instructions table exists
        try:
            res_instr = supabase.table("course_instructions").select("*").limit(1).execute()
            print("Table 'course_instructions' EXISTS.")
        except Exception as e:
             print(f"Table 'course_instructions' likely DOES NOT exist. Error: {e}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_schema()
