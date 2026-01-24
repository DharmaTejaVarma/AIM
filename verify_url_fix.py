import sys
import os
from unittest.mock import MagicMock

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from backend.utils import custom_url_for
from fastapi import Request

def test_url_resolution():
    # Mock FastAPI Request and App
    app = MagicMock()
    
    # Simulate routes
    from starlette.routing import Route, Mount
    
    class MockMount(Mount):
        def __init__(self, name, path):
            self.name = name
            self.path = path
            self.routes = []

    routes = [
        Route("/admin/departments/details/{department_name}", name="admin.department_details", endpoint=lambda: None),
        MockMount("static", "/static")
    ]
    app.routes = routes
    
    request = MagicMock(spec=Request)
    request.app = app
    
    # Mock request.url_for
    def mock_url_for(name, **params):
        if name == "admin.department_details":
            if "department_name" in params and len(params) == 1:
                return f"http://test/admin/departments/details/{params['department_name']}"
        elif name == "static":
            if "path" in params and len(params) == 1:
                return f"http://test/static/{params['path']}"
        
        from starlette.routing import NoMatchFound
        raise NoMatchFound(name, params)
    
    request.url_for.side_effect = mock_url_for

    print("Testing custom_url_for...")
    
    # 1. Test standard route with query params
    print("\n1. Standard route with query params:")
    url1 = custom_url_for(
        request, 
        "admin.department_details", 
        department_name="AI & DS", 
        students_page=2
    )
    print(f"Generated URL: {url1}")
    if "AI%20%26%20DS" in url1 and "students_page=2" in url1:
         print("SUCCESS")
    else:
         print("FAILURE")

    # 2. Test static route
    print("\n2. Static route:")
    url2 = custom_url_for(
        request,
        "static",
        filename="css/main.css"
    )
    print(f"Generated URL: {url2}")
    if "http://test/static/css/main.css" in url2:
         print("SUCCESS")
    else:
         print("FAILURE")

if __name__ == "__main__":
    test_url_resolution()
