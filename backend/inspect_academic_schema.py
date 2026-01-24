import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def inspect_schema():
    print("--- Inspecting 'semesters' table ---")
    try:
        # Try to fetch one row from a 'semesters' table to see if it exists
        res = supabase.table("semesters").select("*").limit(1).execute()
        print("Table 'semesters' exists.")
        if res.data:
            print("Sample data:", res.data[0])
        else:
            print("Table is empty.")
    except Exception as e:
        print(f"Error inspecting 'semesters': {e}")

    print("\n--- Inspecting 'academic_years' table ---")
    try:
        res = supabase.table("academic_years").select("*").limit(1).execute()
        print("Table 'academic_years' exists.")
        if res.data:
            print("Sample data:", res.data[0])
        else:
            print("Table is empty.")
    except Exception as e:
        print(f"Error inspecting 'academic_years': {e}")
        
    print("\n--- Inspecting 'academic_setup.json' (Frontend only?) ---")
    # This file might just be a file, let's check basic file existence in current dir, 
    # but the prompt implies DB.

if __name__ == "__main__":
    inspect_schema()
