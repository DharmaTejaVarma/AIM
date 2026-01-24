import psycopg2
DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

def check_dept():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='faculty' AND column_name='department'")
    if cur.fetchone():
        print("Column 'department' EXISTS.")
    else:
        print("Column 'department' MISSING.")
    conn.close()

if __name__ == "__main__":
    check_dept()
