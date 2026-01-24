from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
import os
from dotenv import load_dotenv

load_dotenv()

# Updated imports to new file structure
from .routes import auth, health, admin, faculty, student, academic

app = FastAPI(title="CampusIQ")

# CORS - Updated for Cookie Support
origins = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
app.include_router(auth.router, prefix="/api", tags=["Auth"])
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(admin.router)
app.include_router(faculty.router)
app.include_router(student.router)
app.include_router(academic.router)

# Mount Static & Templates
# We are currently in /app/backend inside Docker usually, or ./backend locally
# But templates/static are in root.
# Adjust paths relative to this file: ../templates, ../static

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "backend", "static")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

from .utils import templates

# Root Redirect
@app.get("/")
async def root():
    return RedirectResponse(url="/login")

# Serve Login Page
@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# Fallback for old logout route if accessed via GET
@app.get("/logout")
async def logout_page():
    return RedirectResponse(url="/login")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
