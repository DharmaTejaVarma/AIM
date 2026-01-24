import psycopg2

DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

def debug_rls():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("SELECT polname, polcmd, pg_get_expr(polqual, polrelid) FROM pg_policy WHERE polrelid = 'department'::regclass")
    rows = cur.fetchall()
    print(f"Policies: {len(rows)}")
    for r in rows:
        print(f"{r[0]}: {r[1]} -> Expr: {r[2]}")
        
    # Check if RLS enabled
    cur.execute("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid = 'department'::regclass")
    print(f"RLS Enabled/Forced: {cur.fetchone()}")
    conn.close()

if __name__ == "__main__":
    debug_rls()
