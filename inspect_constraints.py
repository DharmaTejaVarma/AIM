import psycopg2

DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

def inspect_constraints():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        print("--- CONSTRAINTS ---")
        cur.execute("""
            SELECT conname, pg_get_constraintdef(c.oid)
            FROM pg_constraint c
            WHERE conrelid = 'faculty'::regclass;
        """)
        rows = cur.fetchall()
        for r in rows:
            print(f"Constraint: {r[0]}")
            print(f"Def: {r[1]}")
            print("-" * 20)
            
        print("--- REQUIRED COLUMNS ---")
        cur.execute("""
            SELECT column_name, column_default
            FROM information_schema.columns
            WHERE table_name = 'faculty' AND is_nullable = 'NO';
        """)
        rows = cur.fetchall()
        for r in rows:
            print(f"- {r[0]} (Default: {r[1]})")

        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_constraints()
