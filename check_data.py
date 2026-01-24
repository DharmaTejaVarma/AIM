import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

def check_data():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    print("--- Departments ---")
    cur.execute("SELECT id, name, code, course_id FROM department")
    rows = cur.fetchall()
    for r in rows:
        print(r)
        
    print("\n--- Student Batches ---")
    cur.execute("SELECT batch, count(*) FROM student GROUP BY batch")
    rows = cur.fetchall()
    for r in rows:
        print(r)
        
    conn.close()

if __name__ == "__main__":
    check_data()
