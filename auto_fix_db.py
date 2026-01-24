import os
import psycopg2
from urllib.parse import urlparse

# DATABASE CONNECTION DETAILS from .env
# SUPABASE_DB_URI=postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres
DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

SQL_COMMANDS = [
    "ALTER TABLE public.student ADD COLUMN IF NOT EXISTS batch TEXT;",
    "ALTER TABLE public.student ADD COLUMN IF NOT EXISTS phone TEXT;",
    "ALTER TABLE public.student ADD COLUMN IF NOT EXISTS address TEXT;",
    "ALTER TABLE public.student ADD COLUMN IF NOT EXISTS father_name TEXT;",
    "ALTER TABLE public.student ADD COLUMN IF NOT EXISTS mother_name TEXT;",
    "ALTER TABLE public.student ADD COLUMN IF NOT EXISTS parents_phone TEXT;",
    "ALTER TABLE public.student ADD COLUMN IF NOT EXISTS date_of_birth DATE;",
    "ALTER TABLE public.student ADD COLUMN IF NOT EXISTS admission_date DATE;",
    # Ensure department has course_id
    "ALTER TABLE public.department ADD COLUMN IF NOT EXISTS course_id UUID;",
    "NOTIFY pgrst, 'reload schema';"
]

def auto_fix():
    print("--- AUTO-FIXING DATABASE SCHEMA ---")
    try:
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        cur = conn.cursor()
        
        for sql in SQL_COMMANDS:
            print(f"Executing: {sql}")
            cur.execute(sql)
            
        print("\n[SUCCESS] Database schema updated successfully.")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"\n[ERROR] Failed to auto-fix: {e}")
        print("You may need to install psycopg2: pip install psycopg2-binary")

if __name__ == "__main__":
    auto_fix()
