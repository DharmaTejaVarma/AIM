import psycopg2
# Hardcoded
DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

def inspect_schema():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'faculty';
        """)
        columns = cur.fetchall()
        print("FULL FACULTY COLUMNS:")
        for col in columns:
            print(f"- {col[0]}: {col[1]}")
            
        print("\nConstraints:")
        cur.execute("""
            SELECT conname, pg_get_constraintdef(c.oid)
            FROM pg_constraint c
            JOIN pg_namespace n ON n.oid = c.connamespace
            WHERE conrelid = 'department'::regclass;
        """)
        cons = cur.fetchall()
        for con in cons:
            print(con)
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_schema()
