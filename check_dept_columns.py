import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

def check_columns():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("""
        SELECT column_name, data_type, is_nullable 
        FROM information_schema.columns 
        WHERE table_name = 'department';
    """)
    print("Department Columns:")
    for row in cur.fetchall():
        print(row)
    conn.close()

if __name__ == "__main__":
    check_columns()
