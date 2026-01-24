import psycopg2
import uuid
import sys

# Hardcoded
DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

def test_write():
    conn = None
    try:
        print("Connecting...")
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        cur = conn.cursor()
        
        test_code = f"TEST_{uuid.uuid4().hex[:4]}"
        print(f"Attempting to insert dummy department {test_code}...")
        
        # Check course_id to use? We need a valid one? 
        # Actually course_id is UUID. Let's get one from course table
        cur.execute("SELECT id FROM course LIMIT 1")
        c_res = cur.fetchone()
        if not c_res:
            print("No courses found to link to!")
            return
        cid = c_res[0]
        
        cur.execute("""
            INSERT INTO department (name, code, status, course_id)
            VALUES (%s, %s, 'active', %s) RETURNING id;
        """, (f"Test Dept {test_code}", test_code, cid))
        
        new_id = cur.fetchone()[0]
        print(f"Inserted ID: {new_id}")
        
        # Verify immediately
        cur.execute("SELECT name FROM department WHERE id = %s", (new_id,))
        row = cur.fetchone()
        if row:
            print(f"Verification successful: Found {row[0]}")
        else:
            print("Verification FAILED: Row not found immediately after insert!")
            
        # Clean up
        print("Cleaning up...")
        cur.execute("DELETE FROM department WHERE id = %s", (new_id,))
        print("Deleted.")
        
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
    finally:
        if conn: conn.close()
        print("Done.")

if __name__ == "__main__":
    test_write()
