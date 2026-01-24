import psycopg2
import uuid

DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

def test_status():
    try:
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        cur = conn.cursor()
        
        print("Attempting insert with STATUS...")
        ucode = str(uuid.uuid4())[:4]
        cur.execute("INSERT INTO department (name, code, status) VALUES (%s, %s, 'active') RETURNING id", 
                    (f"Status Test {ucode}", ucode))
        new_id = cur.fetchone()[0]
        print(f"Success! ID: {new_id}")
        
        cur.execute("DELETE FROM department WHERE id = %s", (new_id,))
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_status()
