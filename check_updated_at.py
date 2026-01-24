import psycopg2
DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

def check_updated():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='faculty' AND column_name='updated_at'")
    if cur.fetchone():
        print("Column 'updated_at' EXISTS.")
    else:
        print("Column 'updated_at' MISSING.")
    conn.close()

if __name__ == "__main__":
    check_updated()
