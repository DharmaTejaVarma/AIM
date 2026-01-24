
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(url, key)

def inspect_table(table_name):
    print(f"--- Inspecting {table_name} ---")
    try:
        # Fetch one row to see keys
        res = supabase.table(table_name).select("*").limit(1).execute()
        if res.data:
            print("Columns:", list(res.data[0].keys()))
        else:
            print("Table empty, cannot infer columns from data.")
            # Try to insert/delete to maybe get schema error or just guess?
            # Actually, let's just assume empty means we can't see cols easily via API unless we use rpc or generic introspection if enabled.
            # But let's try to select specific columns I care about to see if they error.
    except Exception as e:
        print(f"Error inspecting {table_name}: {e}")

inspect_table("subject")
inspect_table("subjects_master")
