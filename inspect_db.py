import os
from dotenv import load_dotenv
from supabase import create_client
import pathlib

# Force load .env from current directory
env_path = pathlib.Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)
load_dotenv() # Fallback

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

print(f"URL: {url}")
print(f"Key loaded: {bool(key)}")

if not url or not key:
    print("Missing env vars. Checked SUPABASE_KEY and SUPABASE_SERVICE_ROLE_KEY")
    exit(1)

supabase = create_client(url, key)

print("Checking 'timetable' table...")
try:
    res = supabase.table("timetable").select("*").limit(1).execute()
    if res.data:
        cols = sorted(list(res.data[0].keys()))
        print("Columns found:")
        for c in cols:
            print(f"- {c}")
    else:
        print("Table 'timetable' exists but is empty.")
except Exception as e:
    print(f"Error checking timetable: {e}")
