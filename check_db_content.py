import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()
DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

def check():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    print("--- COURSES ---")
    cur.execute("SELECT name, code FROM course")
    rows = cur.fetchall()
    for r in rows: print(r)
    
    print("\n--- DEPARTMENTS (Branches) ---")
    cur.execute("SELECT name, code, course_id FROM department")
    rows = cur.fetchall()
    for r in rows: print(r)

    print("\n--- BATCHES ---")
    cur.execute("SELECT name FROM batch")
    rows = cur.fetchall()
    for r in rows: print(r)
    
    conn.close()

if __name__ == "__main__":
    check()
