import os
import sys
from dotenv import load_dotenv
load_dotenv()
from backend.supabase_client import get_supabase
from passlib.context import CryptContext

# Auth Context
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

def reset_password(username, new_password):
    supabase = get_supabase()
    
    # 1. Check User
    print(f"Checking user: {username}...")
    res = supabase.table("users").select("*").eq("username", username).execute()
    
    if not res.data:
        print(f"Error: User '{username}' not found.")
        print("Searching for similar users...")
        all_users = supabase.table("users").select("username").execute()
        found = [u['username'] for u in all_users.data if username.lower() in u['username'].lower()]
        if found:
            print(f"Did you mean? {found}")
        else:
             print("No strings match.")
        return
        
    user = res.data[0]
    uid = user['id']
    print(f"Found User ID: {uid}")
    
    # 2. Hash
    new_hash = get_password_hash(new_password)
    print(f"New Hash Generated: {new_hash[:20]}...")
    
    # 3. Update
    try:
        supabase.table("users").update({"password_hash": new_hash}).eq("id", uid).execute()
        print(f"Success! Password for '{username}' has been updated to '{new_password}'.")
        print("Try logging in now.")
    except Exception as e:
        print(f"Update failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python reset_password_manual.py <username> <new_password>")
        print("Example: python reset_password_manual.py AITS AITS")
    else:
        u = sys.argv[1]
        p = sys.argv[2]
        reset_password(u, p)
