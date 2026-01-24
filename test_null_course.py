import psycopg2
import uuid

DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

def test_null_course():
    try:
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        cur = conn.cursor()
        
        print("Attempting insert with NULL course_id...")
        cur.execute("""
            INSERT INTO department (name, code, status, course_id)
            VALUES ('Null Course Test', 'NULLC', 'active', NULL) RETURNING id;
        """)
        new_id = cur.fetchone()[0]
        print(f"Success! ID: {new_id}")
        
        # Cleanup
        cur.execute("DELETE FROM department WHERE id = %s", (new_id,))
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_null_course()
