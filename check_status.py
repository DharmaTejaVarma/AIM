import psycopg2
DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

def check_status_col():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='department' AND column_name='status'")
        res = cur.fetchone()
        if res:
            print("Status column FOUND.")
        else:
            print("Status column MISSING.")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_status_col()
