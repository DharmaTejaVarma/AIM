from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

# Test
password = "testpassword"
hashed = get_password_hash(password)
print(f"Password: {password}")
print(f"Hash: {hashed}")
print(f"Verify: {verify_password(password, hashed)}")

# Test with whitespace
p2 = " 123 "
h2 = get_password_hash(p2)
print(f"P2: '{p2}' Hash: {h2}")
print(f"Verify '123' against P2 hash: {verify_password('123', h2)}")
