import sys
import os
sys.path.append(os.getcwd())

from backend.database import get_supabase

def inspect():
    supabase = get_supabase()
    
    print("--- ATTENDANCE SAMPLE ---")
    att = supabase.table("attendance").select("*").limit(2).execute()
    print(att.data)
    
    print("\n--- TIMETABLE SAMPLE ---")
    tt = supabase.table("timetable").select("*").limit(2).execute()
    print(tt.data)

if __name__ == "__main__":
    inspect()
