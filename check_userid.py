import psycopg2
DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

def check_userid():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("SELECT is_nullable FROM information_schema.columns WHERE table_name='faculty' AND column_name='user_id'")
    res = cur.fetchone()
    if res:
        print(f"user_id Nullable: {res[0]}")
    else:
        print("user_id MISSING")
    conn.close()

if __name__ == "__main__":
    check_userid()
