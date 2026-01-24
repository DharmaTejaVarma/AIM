import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

# Parse DB URL from .env or hardcoded fallbacks if needed (copied from reset_student_passwords.py pattern)
DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    # Fallback to the one seen in reset_student_passwords.py if env is missing, 
    # but preferably use what's available.
    # User's reset_student_passwords.py had: "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"
    # I will try to read .env first, then fallback.
    pass

# Hardcoded fallback based on previous file context (Step 116)
FALLBACK_DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

def migrate():
    url = DB_URL or FALLBACK_DB_URL
    print(f"Connecting to DB...")
    
    try:
        conn = psycopg2.connect(url)
        conn.autocommit = True
        cur = conn.cursor()
        
        print("Checking/Creating 'semester' table...")
        
        # Create Table
        create_table_query = """
        CREATE TABLE IF NOT EXISTS semester (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            academic_year_id UUID REFERENCES academic_year(id),
            name TEXT NOT NULL,
            type TEXT, -- e.g. Odd/Even
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            status TEXT DEFAULT 'Inactive', -- Active, Inactive, Completed
            created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
        );
        """
        cur.execute(create_table_query)
        print("Table 'semester' ensured.")
        
        # Check columns to ensure they exist (if table already existed but old schema)
        # We want to ensure start_date, end_date, status exist
        # This is a basic check; usually we trust CREATE IF NOT EXISTS for greenfield
        
        # Seed a default active semester if none exists
        cur.execute("SELECT count(*) FROM semester")
        count = cur.fetchone()[0]
        
        if count == 0:
            print("Seeding default Active semester...")
            # We need an academic year id logic, but for now specific ID or null?
            # Let's try to get an academic year first
            cur.execute("SELECT id FROM academic_year LIMIT 1")
            ay_row = cur.fetchone()
            ay_id = ay_row[0] if ay_row else None
            
            if ay_id:
                insert_query = """
                INSERT INTO semester (academic_year_id, name, type, start_date, end_date, status)
                VALUES (%s, 'Semester 1', 'Odd', CURRENT_DATE - INTERVAL '1 month', CURRENT_DATE + INTERVAL '5 months', 'Active')
                """
                cur.execute(insert_query, (ay_id,))
                print("Seeded 'Semester 1' as Active.")
            else:
                print("Warning: No Academic Year found, skipping seed.")
        
        print("Migration completed successfully.")
        conn.close()
        
    except Exception as e:
        print(f"Error during migration: {e}")

if __name__ == "__main__":
    migrate()
