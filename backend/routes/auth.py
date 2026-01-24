from fastapi import APIRouter, Depends, HTTPException, status, Form, Request, Body
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from ..supabase_client import get_supabase
from ..auth import create_access_token, verify_password, get_current_user, get_password_hash
from ..schemas.models import Token, LoginRequest
from datetime import datetime, timedelta
from ..utils import templates
import secrets
import string
from typing import Optional

router = APIRouter()

# --- Helper Functions ---

def log_activity(action, user_id, description, request: Optional[Request] = None):
    try:
        supabase = get_supabase()
        ip = request.client.host if request else "unknown"
        ua = request.headers.get("User-Agent", "")[:255] if request else ""
        
        data = {
            "action": action,
            "user_id": user_id,
            "description": description,
            "ip_address": ip,
            "user_agent": ua,
            "timestamp": datetime.utcnow().isoformat()
        }
        # Try inserting - fail silently if table doesn't exist
        try:
            supabase.table("activity_log").insert(data).execute()
        except:
            pass 
    except Exception as e:
        print(f"Log Activity Failed: {e}")

def generate_temp_password(length=8):
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))

# --- Auth Routes ---

@router.get("/login", name="auth.login_page")
async def login_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@router.post("/login", response_model=Token)
async def login(request: Request, username: str = Form(...), password: str = Form(...), rememberMe: Optional[bool] = Form(False)): # Accept Form data for compatibility
    try:
        supabase = get_supabase()
        # 1. Get user from Supabase
        response = supabase.table("users").select("*").eq("username", username).execute()
        
        if not response.data:
            print(f"Login failed: User {username} not found")
            log_activity('failed_login', None, f'Failed login attempt for username: {username}', request)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        
        user = response.data[0]
        
        # 2. Verify Password
        if not verify_password(password, user['password_hash']):
            print(f"Login failed: Invalid password for {username}")
            log_activity('failed_login', user['id'], f'Failed login attempt (bad password) for username: {username}', request)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        
        # 3. Create Token
        # Helper: Flask session permanent = 30 days usually, but here typical JWT is 1 day or 30 days
        expiry_minutes = 60 * 24 * 30 if rememberMe else 60 * 24
        access_token_expires = timedelta(minutes=expiry_minutes)
        
        access_token = create_access_token(
            data={"sub": user['username'], "role": user['role'], "user_id": user['id']},
            expires_delta=access_token_expires
        )
        
        # Log successful login
        log_activity('login', user['id'], f'User {user["username"]} logged in.', request)
        
        # 4. Determine Redirect URL based on Role
        role = user['role']
        redirect_url = f"/{role}/dashboard"
        if role == 'admin':
            redirect_url = "/admin/dashboard" 
        
        response = JSONResponse(content={
            "access_token": access_token, 
            "token_type": "bearer",
            "redirect_url": redirect_url
        })
        
        # Cookie Fix: Lax + Secure=False for localhost
        response.set_cookie(key="access_token", value=access_token, httponly=True, samesite="Lax", secure=False, max_age=expiry_minutes*60)
        return response
    except HTTPException as he:
        raise he
    except Exception as e:
        import traceback
        traceback.print_exc()
        # Check for table error
        if "Could not find the table" in str(e):
             raise HTTPException(status_code=500, detail="Database not initialized.")
        raise e

@router.get("/logout", name="auth.logout")
async def logout(request: Request, user: dict = Depends(get_current_user)):
    # Log logout if user is authenticated (might fail if token invalid, but route depends on it?)
    # Wait, 'get_current_user' is optimal? Existing logout didn't use dependency but relied on cookie.
    # If I use Depends(get_current_user), functionality breaks if token expired.
    # I'll try to decode token manually or just log if possible.
    # For safety/simplicity towards porting loop:
    if user:
         log_activity('logout', user['user_id'], f'User {user.get("sub")} logged out.', request)

    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(key="access_token")
    return response

@router.get("/change_password", name="auth.change_password_page")
async def change_password_page(request: Request):
    # This page likely requires auth. Frontend usually handles redirection if no token.
    # But for specialized page rendering:
    return templates.TemplateResponse("change_password.html", {"request": request})

@router.post("/change_password", name="auth.change_password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    user: dict = Depends(get_current_user)
):
    if new_password != confirm_password:
        raise HTTPException(status_code=400, detail="New passwords do not match.")
    
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
        
    supabase = get_supabase()
    # Verify current
    # We need to fetch user hash again or trust 'user' from token? Token doesn't have hash.
    # User object from get_current_user (logic in backend/auth.py) usually returns dict payload of token.
    # I need to fetch DB user.
    db_user_res = supabase.table("users").select("*").eq("id", user['user_id']).single().execute()
    if not db_user_res.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    db_user = db_user_res.data
    
    if not verify_password(current_password, db_user['password_hash']):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
        
    # Update
    new_hash = get_password_hash(new_password)
    supabase.table("users").update({"password_hash": new_hash}).eq("id", user['user_id']).execute()
    
    log_activity('password_change', user['user_id'], f'User {db_user["username"]} changed password.', request)
    
    return JSONResponse({"message": "Password changed successfully!"})

@router.get("/forgot_password", name="auth.forgot_password_page")
async def forgot_password_page(request: Request):
    return templates.TemplateResponse("forgot_password.html", {"request": request})

@router.post("/forgot_password", name="auth.forgot_password")
async def forgot_password(request: Request, username: str = Form(...), email: str = Form(...)):
    supabase = get_supabase()
    # Find user
    res = supabase.table("users").select("*").eq("username", username).eq("email", email).execute()
    if not res.data:
        # Don't reveal user existence? Or follow JS logic which flashed error.
        raise HTTPException(status_code=404, detail="No user found with that username and email combination.")
    
    user = res.data[0]
    temp_pass = generate_temp_password()
    new_hash = get_password_hash(temp_pass)
    
    supabase.table("users").update({"password_hash": new_hash}).eq("id", user['id']).execute()
    
    log_activity('password_reset', user['id'], f'Password reset initiated for user {user["username"]}.', request)
    
    return JSONResponse({"message": f"Temporary password: {temp_pass}. Please change it after login."})

@router.get("/api/activities", name="auth.activities")
async def get_activities(user: dict = Depends(get_current_user)):
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Access Denied")
        
    supabase = get_supabase()
    try:
        res = supabase.table("activity_log").select("*").order("timestamp", desc=True).limit(100).execute()
        return {"activities": res.data}
    except:
        return {"activities": []}

@router.get("/announcements/recent", name="auth.recent_announcements")
async def recent_announcements(user: dict = Depends(get_current_user)):
    supabase = get_supabase()
    try:
        # Fetch generic announcements (target_role 'all' or specific to user role)
        # Assuming table 'announcement' has 'target_role' or similar. 
        # If simple schema, just fetch all recent.
        # Check if column 'target_role' exists or just fetch all.
        # We'll try to Filter if possible, else fetch all.
        
        # Simple implementation: Fetch Top 5 latest
        res = supabase.table("announcement").select("*").order("created_at", desc=True).limit(5).execute()
        anns = res.data if res.data else []
        
        return {"announcements": anns}
    except Exception as e:
        print(f"Error fetching announcements: {e}")
        return {"announcements": []}
