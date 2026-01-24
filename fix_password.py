from dotenv import load_dotenv
import os
import sys

# Ensure we can import from backend
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.supabase_client import get_supabase
from passlib.context import CryptContext

load_dotenv() # Try loading env again, just in case

# Setup Supabase
try:
    supabase = get_supabase()
except Exception as e:
    print(f"Failed to initialize Supabase: {e}")
    # Fallback: Try to print env vars to debug (be careful with secrets)
    # print("Env vars:", os.environ.keys())
    sys.exit(1)

# Setup Password Hashing
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def reset_password(username, new_password):
    print(f"Resetting password for user: {username}")
    
    # 1. Generate Hash
    hashed_password = pwd_context.hash(new_password)
    print(f"Generated Hash: {hashed_password}")
    
    # 2. Update Database
    try:
        response = supabase.table("users").update({"password_hash": hashed_password}).eq("username", username).execute()
        
        if response.data:
            print(f"Success! Password updated for {username}.")
            print("Row data:", response.data)
        else:
            print(f"Error: User {username} not found or update failed.")
            
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python fix_password.py <username> <new_password>")
    else:
        u = sys.argv[1]
        p = sys.argv[2]
        reset_password(u, p)
