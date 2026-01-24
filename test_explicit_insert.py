import psycopg2
import uuid

DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

def test_explicit_id():
    try:
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        cur = conn.cursor()
        
        # Get valid course id
        cur.execute("SELECT id FROM course LIMIT 1")
        cid = cur.fetchone()[0]
        
        print("Attempting insert with explicit ID 9876...")
        cur.execute("""
            INSERT INTO department (id, name, code, status, course_id)
            VALUES (9876, 'Test Explicit', 'EXP', 'active', %s)
        """, (cid,))
        print("Success!")
        
        # Cleanup
        cur.execute("DELETE FROM department WHERE id = 9876")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_explicit_id()
