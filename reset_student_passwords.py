import psycopg2
from passlib.context import CryptContext

# Auth Configuration (Matching backend/auth.py)
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

def reset_passwords():
    try:
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        cur = conn.cursor()
        
        print("Fetching students...")
        # Get students who have a user_id
        cur.execute("SELECT student_id, user_id, name FROM student WHERE user_id IS NOT NULL")
        students = cur.fetchall()
        
        print(f"Found {len(students)} students linked to users.")
        
        updated_count = 0
        for s_id, u_id, name in students:
            if not s_id: continue
            
            # Hash the student_id
            new_hash = get_password_hash(str(s_id))
            
            # Update user
            cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, u_id))
            updated_count += 1
            
            if updated_count % 10 == 0:
                print(f"Processed {updated_count}...")
                
        print(f"Done. Reset passwords for {updated_count} students to their Student ID.")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    reset_passwords()
