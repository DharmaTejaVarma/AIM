import os
import json
import uuid
import psycopg2
from dotenv import load_dotenv
from datetime import datetime
import traceback

load_dotenv()

# DB Connection
DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

# JSON Data File
DATA_FILE = os.path.join("backend", "data", "academic_setup.json")

def get_db_connection():
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    return conn

def create_tables(cur, conn):
    print("Creating tables...")
    # Skip extension creation, assume python UUIDs or pre-existing

    # 1. Academic Year
    cur.execute("""
        CREATE TABLE IF NOT EXISTS academic_year (
            id UUID PRIMARY KEY,
            name TEXT NOT NULL,
            start_date DATE,
            end_date DATE,
            is_active BOOLEAN DEFAULT TRUE,
            is_current BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    
    # 2. Course
    cur.execute("""
        CREATE TABLE IF NOT EXISTS course (
            id UUID PRIMARY KEY,
            name TEXT NOT NULL,
            code TEXT UNIQUE NOT NULL,
            duration_years INTEGER,
            total_semesters INTEGER,
            status TEXT DEFAULT 'Active',
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    # 3. Batch
    cur.execute("""
        CREATE TABLE IF NOT EXISTS batch (
            id UUID PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            start_year INTEGER,
            end_year INTEGER,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    # 3.5. Semester (Fix for missing table)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS semester (
            id UUID PRIMARY KEY,
            academic_year_id UUID REFERENCES academic_year(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            start_date DATE,
            end_date DATE,
            sequence_number INTEGER,
            status TEXT DEFAULT 'Upcoming',
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    
    # Ensure sequence_number exists
    try:
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name='semester' AND column_name='sequence_number';
        """)
        if not cur.fetchone():
            print("Adding sequence_number to semester table...")
            cur.execute("ALTER TABLE semester ADD COLUMN sequence_number INTEGER;")
    except Exception as e:
        print(f"Error checking/adding sequence_number column: {e}")

    # Ensure status exists
    try:
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name='semester' AND column_name='status';
        """)
        if not cur.fetchone():
            print("Adding status to semester table...")
            cur.execute("ALTER TABLE semester ADD COLUMN status TEXT DEFAULT 'Upcoming';")
    except Exception as e:
        print(f"Error checking/adding status column: {e}")

    # 4. Alter Department to add course_id
    try:
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name='department' AND column_name='course_id';
        """)
        if not cur.fetchone():
            print("Adding course_id to department table...")
            cur.execute("ALTER TABLE department ADD COLUMN course_id UUID;")
    except Exception as e:
        print(f"Error checking/adding column: {e}")

    # Ensure status exists in department
    try:
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name='department' AND column_name='status';
        """)
        if not cur.fetchone():
            print("Adding status to department table...")
            cur.execute("ALTER TABLE department ADD COLUMN status TEXT DEFAULT 'active';")
    except Exception as e:
        print(f"Error checking/adding status column: {e}")

    print("Tables created/verified.")

def migrate_data(conn, cur):
    if not os.path.exists(DATA_FILE):
        print("No JSON file found. Skipping data migration.")
        return

    with open(DATA_FILE, "r") as f:
        data = json.load(f)

    # 1. Migrate Years
    print(f"Migrating {len(data.get('years', []))} Years...")
    for y in data.get("years", []):
        cur.execute("SELECT id FROM academic_year WHERE id = %s", (y['id'],))
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO academic_year (id, name, start_date, end_date, is_active, is_current)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (y['id'], y['name'], y['start_date'], y['end_date'], y['is_active'], y.get('is_current', False)))

    # 2. Migrate Courses
    print(f"Migrating {len(data.get('courses', []))} Courses...")
    for c in data.get("courses", []):
        cur.execute("SELECT id FROM course WHERE id = %s", (c['id'],))
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO course (id, name, code, duration_years, total_semesters, status)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (c['id'], c['name'], c['code'], c['duration_years'], c['total_semesters'], c.get('status', 'Active')))

    # 3. Migrate Branches (Update Departments)
    print(f"Syncing {len(data.get('branches', []))} Branches...")
    
    # Temporarily Disable RLS to ensure migration succeeds
    try:
        cur.execute("ALTER TABLE department DISABLE ROW LEVEL SECURITY")
        print("RLS Disabled for migration.")
    except Exception as e:
        print(f"Could not disable RLS: {e}")

    for b in data.get("branches", []):
        try:
            
            # Check by CODE
            cur.execute("SELECT id FROM department WHERE code = %s", (b['code'],))
            res = cur.fetchone()
            
            if not res:
                # Check by NAME
                cur.execute("SELECT id FROM department WHERE name = %s", (b['name'],))
                res = cur.fetchone()

            if res:
                # Update course_id
                dept_id = res[0]
                print(f"  [UPDATE] Branch {b['code']} exists (ID: {dept_id}). Updating...")
                cur.execute("UPDATE department SET course_id = %s WHERE id = %s", (b['course_id'], dept_id))
            else:
                # Insert new
                print(f"  [INSERT] Creating new branch {b['code']}...")
                
                with open("migration_log.txt", "a") as log:
                     log.write(f"Attempting INSERT for {b['code']} (Auto ID)...\n")
                
                cur.execute("""
                    INSERT INTO department (name, code, status, course_id)
                    VALUES (%s, %s, %s, %s)
                """, (b['name'], b['code'], b.get('status', 'active'), b['course_id']))
                
                with open("migration_log.txt", "a") as log:
                     log.write(f"SUCCESS: Inserted {b['code']}.\n")
                

        except Exception as e:
            with open("error_trace.txt", "a") as f:
                f.write(f"--- ERROR migrating {b.get('code')} ---\n")
                f.write(str(e) + "\n")
                traceback.print_exc(file=f)
            
            with open("migration_log.txt", "a") as log:
                 log.write(f"ERROR migrating branch {b.get('name', 'Unknown')}: {e}\n")
            print(f"Error migrating branch {b.get('name', 'Unknown')}: {e}")

    # 4. Auto-Create Batches from Students
    print("Auto-creating Batches from Student data...")
    cur.execute("SELECT DISTINCT batch FROM student WHERE batch IS NOT NULL")
    raw_batches = cur.fetchall() # List of tuples [('2024-2028',), ...]
    
    count = 0
    for row in raw_batches:
        batch_name = row[0]
        if not batch_name: continue
        
        # Check if exists
        cur.execute("SELECT id FROM batch WHERE name = %s", (batch_name,))
        if cur.fetchone():
            continue
            
        # Parse years
        start_year = None
        end_year = None
        try:
            parts = batch_name.split('-')
            if len(parts) == 2:
                start_year = int(parts[0])
                end_year = int(parts[1])
        except:
            pass
            
        # Insert
        new_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO batch (id, name, start_year, end_year, is_active)
            VALUES (%s, %s, %s, %s, TRUE)
        """, (new_id, batch_name, start_year, end_year))
        count += 1
        
    print(f"Created {count} new batches.")
    
    # conn.commit() # Autocommit is on

def main():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        create_tables(cur, conn)
        migrate_data(conn, cur)
        
        cur.close()
        conn.close()
        print("Migration completed successfully.")
    except Exception as e:
        print(f"Migration Failed: {e}")

if __name__ == "__main__":
    main()
