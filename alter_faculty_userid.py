import psycopg2

DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

def make_userid_nullable():
    try:
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        cur = conn.cursor()
        
        print("Altering user_id to be NULLABLE...")
        cur.execute("ALTER TABLE faculty ALTER COLUMN user_id DROP NOT NULL;")
        print("Done.")
        
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    make_userid_nullable()
