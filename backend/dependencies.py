from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from .auth import SECRET_KEY, ALGORITHM

# OAuth2 Scheme (for Swagger UI mostly, but we use cookies)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

from .supabase_client import get_supabase

async def get_current_user_token(request: Request):
    # print(f"DEBUG AUTH: Checking token for URL: {request.url}")
    # print(f"DEBUG AUTH: Cookies: {request.cookies}")
    # print(f"DEBUG AUTH: Headers: {request.headers}")
    
    token = request.cookies.get("access_token")
    if token:
        # print("DEBUG AUTH: Found token in cookie.")
        pass
    
    if not token:
        # Fallback to header if needed (for API clients)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            print("DEBUG AUTH: Found token in header.")
            
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not token:
        print("DEBUG AUTH: No token found!")
        raise credentials_exception
        
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # print(f"DEBUG AUTH: Token decoded successfully: {payload}")
        username: str = payload.get("sub")
        role: str = payload.get("role")
        user_id: str = payload.get("user_id")
        
        if username is None or role is None:
            print("DEBUG AUTH: Missing sub or role in token.")
            raise credentials_exception
            
        # Verify user exists in DB (Handle deletion)
        try:
            supabase = get_supabase()
            # Check if user exists
            if user_id:
                u_res = supabase.table("users").select("id").eq("id", user_id).maybe_single().execute()
                if not u_res.data:
                    print(f"DEBUG AUTH: User {user_id} deleted (Token Revoked).")
                    raise credentials_exception
        except Exception as e:
            # If DB check fails, we assume auth failure to be safe
            print(f"DEBUG AUTH: DB Verification Failed: {e}")
            raise credentials_exception
            
        return {"username": username, "role": role, "user_id": user_id}
    except JWTError as e:
        print(f"DEBUG AUTH: JWT Error: {e}")
        raise credentials_exception

async def get_current_admin(user: dict = Depends(get_current_user_token)):
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Not authorized")
    return user

async def get_current_faculty(user: dict = Depends(get_current_user_token)):
    if user['role'] != 'faculty':
        raise HTTPException(status_code=403, detail="Not authorized")
    return user

async def get_current_student(user: dict = Depends(get_current_user_token)):
    if user['role'] != 'student':
        raise HTTPException(status_code=403, detail="Not authorized")
    return user
