import psycopg2

DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

def debug_faculty():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        cur.execute("SELECT count(*) FROM faculty")
        count = cur.fetchone()[0]
        print(f"Total Faculty Count: {count}")
        
        if count > 0:
            cur.execute("SELECT id, name, email, department_id, designation FROM faculty LIMIT 5")
            rows = cur.fetchall()
            for r in rows:
                print(f"- {r[1]} ({r[4]}) DeptID: {r[3]}")
                
        # Also check departments to match IDs
        print("\nDepartments:")
        cur.execute("SELECT id, name FROM department LIMIT 5")
        rows = cur.fetchall()
        for r in rows:
            print(f"- {r[1]} ID: {r[0]}")

        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_faculty()
