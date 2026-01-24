import psycopg2
import re

DB_URL = "postgresql://postgres:DineshK%402624@db.altsfwlvjvwffoebqlna.supabase.co:5432/postgres"

def sync_seq():
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    cur = conn.cursor()
    
    # Get max id
    cur.execute("SELECT MAX(id) FROM department")
    max_id = cur.fetchone()[0] or 0
    print(f"Max ID: {max_id}")
    
    # Get sequence name
    cur.execute("SELECT column_default FROM information_schema.columns WHERE table_name='department' AND column_name='id'")
    default_val = cur.fetchone()[0]
    print(f"Default: {default_val}")
    
    if default_val and 'nextval' in default_val:
        # Extract sequence name: nextval('department_id_seq'::regclass)
        m = re.search(r"'([^']+)'", default_val)
        if m:
            seq_name = m.group(1)
            print(f"Sequence Name: {seq_name}")
            
            # Set val
            new_val = max_id + 1
            cur.execute(f"SELECT setval('{seq_name}', {new_val}, false)")
            print(f"Sequence set to {new_val}")
        else:
            print("Could not parse sequence name.")
    else:
        print("No sequence found in default.")
        
    conn.close()

if __name__ == "__main__":
    sync_seq()
