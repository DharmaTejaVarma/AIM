import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

def reload_schema():
    try:
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        cur = conn.cursor()
        print("Sending NOTIFY pgrst, 'reload schema'...")
        cur.execute("NOTIFY pgrst, 'reload schema';")
        conn.close()
        print("Done.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    reload_schema()
