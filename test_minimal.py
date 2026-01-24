import psycopg2
import uuid

DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

def test_minimal():
    try:
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        cur = conn.cursor()
        
        print("Attempting MINIMAL insert (name, code)...")
        # Use random code
        ucode = str(uuid.uuid4())[:4]
        cur.execute("INSERT INTO department (name, code) VALUES (%s, %s) RETURNING id", (f"Minimal {ucode}", ucode))
        new_id = cur.fetchone()[0]
        print(f"Success! ID: {new_id}")
        
        # Cleanup
        cur.execute("DELETE FROM department WHERE id = %s", (new_id,))
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_minimal()
