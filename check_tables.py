import sys
import os
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.getcwd())

from backend.supabase_client import get_supabase

try:
    supabase = get_supabase()
    tables = ["fee", "announcement", "student", "department"]
    for t in tables:
        try:
            res = supabase.table(t).select("*", count="exact").limit(1).execute()
            print(f"Table '{t}' count: {res.count}")
        except Exception as e:
            print(f"Table '{t}' error: {e}")

except Exception as e:
    print(f"Error: {e}")
