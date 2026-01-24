import sys
import os
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.getcwd())

from backend.supabase_client import get_supabase

try:
    supabase = get_supabase()
    print("Testing query: table('student').select('*, users(email, username)').limit(1)")
    res = supabase.table("student").select("*, users(email, username)").limit(1).execute()
    print("Success!")
    print(res.data)
except Exception as e:
    print(f"FAILED: {e}")
