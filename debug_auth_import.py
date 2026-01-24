import sys
import os
# Add current dir to path to find backend
sys.path.append(os.getcwd())

try:
    from backend.auth.auth import verify_password, pwd_context
    
    hash_val = '$pbkdf2-sha256$29000$FQLA2Buj1Po/h3DO2XsvJQ$Jty55itnT956eN8TFtnShoD.CoCjSCBR71nh2TXCb1Q'
    
    print(f"Context schemes: {pwd_context.schemes()}")
    
    print("Attempting verify...")
    res = verify_password("password123", hash_val)
    print(f"Verify result: {res}")

except Exception as e:
    import traceback
    traceback.print_exc()
