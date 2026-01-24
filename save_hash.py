from passlib.context import CryptContext
try:
    pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
    hash_val = pwd_context.hash("password123")
    with open("hash.txt", "w") as f:
        f.write(hash_val)
except Exception as e:
    print(f"Error: {e}")
