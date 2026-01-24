import os
import psycopg2
from dotenv import load_dotenv

# Hardcoded from previous context failure if .env fails
DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

def inspect_departments():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        cur.execute("SELECT id, name, code, course_id FROM department")
        rows = cur.fetchall()
        
        print(f"Total Departments found: {len(rows)}")
        for row in rows:
            print(f"- [{row[0]}] {row[1]} ({row[2]}) Course: {row[3]}")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_departments()
