import psycopg2

DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

def debug_triggers():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("SELECT tgname, pg_get_triggerdef(oid) FROM pg_trigger WHERE tgrelid = 'department'::regclass")
    rows = cur.fetchall()
    print(f"Triggers: {len(rows)}")
    for r in rows:
        print(f"{r[0]}: {r[1]}")
    conn.close()

if __name__ == "__main__":
    debug_triggers()
