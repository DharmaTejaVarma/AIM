import sys
import os

# Add the current directory to sys.path to allow importing from 'backend'
sys.path.append(os.getcwd())

try:
    from backend.app import app
    with open("routes_utf8.txt", "w", encoding="utf-8") as f:
        f.write("Listing all registered routes:\n")
        f.write("-" * 60 + "\n")
        for route in app.routes:
            name = getattr(route, "name", "N/A")
            path = getattr(route, "path", "N/A")
            methods = getattr(route, "methods", "N/A")
            f.write(f"Name: {name:<30} Path: {path:<50} Methods: {methods}\n")
        f.write("-" * 60 + "\n")
    print("Done. Output written to routes_utf8.txt")
except Exception as e:
    print(f"Error loading app: {e}")
    import traceback
    traceback.print_exc()
