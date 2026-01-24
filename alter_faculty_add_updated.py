import psycopg2

DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

def add_updated():
    try:
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        cur = conn.cursor()
        
        print("Adding updated_at to faculty...")
        cur.execute("ALTER TABLE faculty ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();")
        print("Done.")
        
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    add_updated()
