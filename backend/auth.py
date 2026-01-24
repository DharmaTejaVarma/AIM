from datetime import datetime, timedelta
import os
from typing import Optional
from jose import jwt
from passlib.context import CryptContext
from fastapi import Request, HTTPException, status

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "supersecret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

# Security Contexts
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    print(f"DEBUG AUTH: Verifying password.")
    # print(f"DEBUG AUTH: Hash received (type {type(hashed_password)}): '{hashed_password}'")
    try:
        if not hashed_password:
             print("DEBUG AUTH: Hash is empty/None!")
             return False
        result = pwd_context.verify(plain_password, hashed_password)
        print(f"DEBUG AUTH: Verify Result: {result}")
        return result
    except Exception as e:
        print(f"DEBUG AUTH: Error in verify_password: {e}")
        raise e

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
         auth_header = request.headers.get("Authorization")
         if auth_header and auth_header.startswith("Bearer "):
             token = auth_header.split(" ")[1]
    
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
