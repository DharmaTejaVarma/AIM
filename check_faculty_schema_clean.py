import psycopg2

DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

def check_schema():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        expected = ['id', 'name', 'email', 'phone', 'designation', 'department_id', 'status', 'department', 'created_at']
        print(f"Checking for: {expected}")
        
        cur.execute(f"SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name='faculty'")
        rows = cur.fetchall()
        existing = {r[0]: (r[1], r[2]) for r in rows}
        
        for col in expected:
            if col in existing:
                print(f"[OK] {col} (Type: {existing[col][0]}, Null: {existing[col][1]})")
            else:
                print(f"[MISSING] {col}")
                
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_schema()
