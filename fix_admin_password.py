import os
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    print("Error: Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env")
    exit(1)

try:
    supabase = create_client(url, key)
    
    # The valid pbkdf2_sha256 hash for 'password123'
    # Generated via passlib in this environment
    new_hash = '$pbkdf2-sha256$29000$FQLA2Buj1Po/h3DO2XsvJQ$Jty55itnT956eN8TFtnShoD.CoCjSCBR71nh2TXCb1Q'
    
    # 1. Fetch current admin user
    print("Fetching admin user...")
    res = supabase.table("users").select("*").eq("username", "admin").execute()
    
    if not res.data:
        print("Admin user not found! The database tables might be missing.")
        print("Please run the SQL in 'supabase_db/schema.sql' in your Supabase Dashboard first.")
    else:
        user = res.data[0]
        current_hash = user.get('password_hash')
        print(f"Found admin user. Current hash: {current_hash}")
        
        if current_hash != new_hash:
            print("Hash does not match target. Updating...")
            
            # 2. Update the hash
            update_res = supabase.table("users").update({"password_hash": new_hash}).eq("username", "admin").execute()
            
            if update_res.data:
                print("SUCCESS: Password hash updated successfully.")
                print("You should now be able to login with 'admin' / 'password123'.")
            else:
                print("FAILED: Did not receive data back from update.")
        else:
            print("Hash is already correct. You should be able to login.")
            
except Exception as e:
    print(f"An error occurred: {e}")
