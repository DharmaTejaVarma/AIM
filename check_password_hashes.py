import psycopg2

DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

def check_hashes():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        cur.execute("SELECT username, password_hash, role FROM users LIMIT 5")
        rows = cur.fetchall()
        
        print(f"{'Username':<20} | {'Role':<10} | {'Password Hash Attempt'}")
        print("-" * 60)
        for r in rows:
            u, h, role = r
            # Check if it looks like pbkdf2_sha256 hash (starts with $pbkdf2-sha256$...)
            is_valid_format = h.startswith("$pbkdf2-sha256$") if h else False
            print(f"{u:<20} | {role:<10} | {h[:30]}... (Valid fmt: {is_valid_format})")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_hashes()
