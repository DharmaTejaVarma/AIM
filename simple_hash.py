from passlib.context import CryptContext
try:
    pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
    print(pwd_context.hash("password123"))
except Exception as e:
    print(f"Error: {e}")
