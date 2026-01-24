import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()
DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

def fix_data():
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    cur = conn.cursor()
    
    print("Fixing Course Data...")
    # Fix 1: Update Name='2022-2026' to 'B.Tech' if Code='B.TECH'
    cur.execute("UPDATE course SET name='B.Tech' WHERE code='B.TECH' AND name LIKE '20%-20%'")
    print(f"Updated {cur.rowcount} courses.")
    
    # Fix 2: Check for other flipped cases?
    # If code is 'M.TECH' and name is a batch?
    cur.execute("UPDATE course SET name='M.Tech' WHERE code='M.TECH' AND name LIKE '20%-20%'")
    print(f"Updated {cur.rowcount} other courses.")

    print("\nFixing Department Status...")
    # Fix 3: Set status 'active' (lowercase) or 'Active' (Capital)
    # Check current values
    cur.execute("UPDATE department SET status='Active' WHERE status IS NULL OR status='undefined'")
    print(f"Updated {cur.rowcount} departments.")
    
    conn.close()

if __name__ == "__main__":
    fix_data()
