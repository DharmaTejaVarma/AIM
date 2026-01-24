import sys
import os
from dotenv import load_dotenv
import psycopg2
from urllib.parse import urlparse

load_dotenv()
sys.path.append(os.getcwd())

def add_batch_column():
    # Updated with finding from .env
    db_url = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"
    
    if not db_url:
        print("No DATABASE_URL found. Cannot connect for DDL.")
        return

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        # Check if column exists
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='student' AND column_name='batch';")
        if cur.fetchone():
            print("Column 'batch' already exists.")
        else:
            print("Adding 'batch' column...")
            cur.execute("ALTER TABLE student ADD COLUMN batch TEXT;")
            conn.commit()
            print("Success: Added 'batch' column.")
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error executing DDL: {e}")

if __name__ == "__main__":
    add_batch_column()
