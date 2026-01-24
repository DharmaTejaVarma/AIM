import psycopg2
import uuid
import random

DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

FACULTY_NAMES = [
    ("Dr. Rajesh Kumar", "rajesh.k@example.com", "Professor"),
    ("Dr. Anita Singh", "anita.s@example.com", "Associate Professor"),
    ("Prof. Suresh Reddy", "suresh.r@example.com", "Head of Department"),
    ("Mr. John Doe", "john.doe@example.com", "Assistant Professor"),
    ("Ms. Jane Smith", "jane.smith@example.com", "Assistant Professor"),
    ("Dr. Emily White", "emily.w@example.com", "Professor"),
    ("Mr. Michael Brown", "michael.b@example.com", "Lab Assistant"),
    ("Mrs. Sarah Lee", "sarah.l@example.com", "Associate Professor"),
    ("Dr. David Green", "david.g@example.com", "Professor"),
    ("Ms. Lisa Black", "lisa.b@example.com", "Assistant Professor"),
]

def seed_faculty():
    try:
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        cur = conn.cursor()
        
        # 1. Get Departments
        cur.execute("SELECT id, name FROM department")
        depts = cur.fetchall()
        
        if not depts:
            print("No departments found! Cannot seed faculty.")
            return

        print(f"Found {len(depts)} departments.")
        dept_ids = [d[0] for d in depts]
        
        # 2. Get Max ID
        cur.execute("SELECT MAX(id) FROM faculty")
        max_id = cur.fetchone()[0]
        next_id = 1 if max_id is None else max_id + 1
        
        # 3. Insert Faculty
        count = 0
        from datetime import datetime
        now = datetime.now()
        
        for i, (name, email, designation) in enumerate(FACULTY_NAMES):
            # Check if exists
            cur.execute("SELECT id FROM faculty WHERE email = %s", (email,))
            if cur.fetchone():
                print(f"Skipping {name} (already exists)")
                continue

            # Pick random department (id, name)
            dept_id_int = random.choice(dept_ids) # This comes from [d[0] for d in depts]
            # Find name
            dept_name = next(d[1] for d in depts if d[0] == dept_id_int)

            current_id = next_id + count
            faculty_code = f"FAC{str(current_id).zfill(3)}" # FAC001
            phone = f"98765{random.randint(10000, 99999)}"
            experience = random.randint(1, 20) # Integer
            
            # Insert with ALL required columns + updated_at
            try:
                cur.execute("""
                    INSERT INTO faculty (
                        id, faculty_id, name, email, phone, designation, 
                        department_id, department, experience, status, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'active', %s, %s)
                """, (current_id, faculty_code, name, email, phone, designation, 
                      dept_id_int, dept_name, experience, now, now))
                
                print(f"Inserted {name} ({faculty_code}) -> {dept_name}")
                count += 1
            except Exception as e:
                with open("seed_errors.txt", "a") as f:
                    f.write(f"FAILED to insert {name}. Error: {e}\n")
                print(f"FAILED to insert {name}. (See seed_errors.txt)")
                
        print(f"Seeding complete. Added {count} new faculty members.")
        conn.close()
        
    except Exception as e:
        print(f"Error seeding faculty: {e}")

if __name__ == "__main__":
    seed_faculty()
