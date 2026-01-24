import os
from fastapi import Request
from fastapi.templating import Jinja2Templates

# Path Setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

from starlette.routing import NoMatchFound, Route, Mount
import urllib.parse

def custom_url_for(request: Request, name: str, **path_params):
    # Handle static files mapping
    if name == "static" and "filename" in path_params:
         path_params["path"] = path_params.pop("filename")
    
    # Filter out None values
    path_params = {k: v for k, v in path_params.items() if v is not None}
    
    # Candidates for the route name (with and without prefix)
    names_to_try = [name]
    if name.startswith("admin."):
        names_to_try.append(name.replace("admin.", "", 1))
    elif not name.startswith("admin.") and name not in ["static", "root", "login", "login_page", "logout_page"]:
        names_to_try.append(f"admin.{name}")

    # Find the matching route to identify its path parameters
    target_route = None
    matched_name = None
    
    # We search in the app's routes
    def find_route(routes, target_name):
        for route in routes:
            # Check both Route and Mount for name match
            if getattr(route, 'name', None) == target_name:
                return route
            if isinstance(route, Mount):
                res = find_route(getattr(route, 'routes', []), target_name)
                if res: return res
        return None

    for n in names_to_try:
        target_route = find_route(request.app.routes, n)
        if target_route:
            matched_name = n
            break

    if not target_route:
        # Fallback to Starlette's default error
        raise NoMatchFound(name, path_params)

    # SPECIAL CASE: static route needs 'path' as a path parameter even if not explicitly in brackets
    if matched_name == "static" or isinstance(target_route, Mount):
        # For Mounts (like static), identify 'path' as a path param if present
        actual_path_params = {}
        query_params = {}
        # Mounts usually consume 'path'
        for k, v in path_params.items():
            if k == 'path' or k == 'department_name' or k == 'id': # Common path params
                actual_path_params[k] = v
            else:
                query_params[k] = v
    else:
        # Extract required path parameters from the route's path
        import re
        required_params = re.findall(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", target_route.path)
        
        # Separate path params from query params
        actual_path_params = {}
        query_params = {}
        
        for k, v in path_params.items():
            if k in required_params:
                actual_path_params[k] = v
            else:
                query_params[k] = v
            
    try:
        # Resolve the base URL with the identified path parameters
        url = str(request.url_for(matched_name, **actual_path_params))
        
        # Append query parameters if any
        if query_params:
            connector = "&" if "?" in url else "?"
            url = f"{url}{connector}{urllib.parse.urlencode(query_params)}"
            
        return url
    except Exception as e:
        # Final fallback: just log and raise
        print(f"Error resolving URL for {name} ({matched_name}): {e}")
        raise NoMatchFound(name, path_params)

class FlaskJinja2Templates(Jinja2Templates):
    def TemplateResponse(self, name: str, context: dict, **kwargs):
        if "request" in context:
            request = context["request"]
            context["url_for"] = lambda name, **params: custom_url_for(
                request, name, **params
            )
            
            def get_flashed_messages(with_categories=False, category_filter=()):
                messages = []
                # Map query params to flash categories
                # success -> success
                # error -> danger
                params = request.query_params
                
                if params.get("success"):
                    messages.append(("success", params["success"]) if with_categories else params["success"])
                if params.get("error"):
                    messages.append(("danger", params["error"]) if with_categories else params["error"])
                if params.get("warning"):
                    messages.append(("warning", params["warning"]) if with_categories else params["warning"])
                if params.get("info"):
                    messages.append(("info", params["info"]) if with_categories else params["info"])
                    
                return messages
            
            context["get_flashed_messages"] = get_flashed_messages
        return super().TemplateResponse(name, context, **kwargs)

templates = FlaskJinja2Templates(directory=TEMPLATES_DIR)

# --- Helper Functions for Student Metrics ---

def process_semester_marks(student_id, subjects, marks, published=True):
    """
    Groups marks by semester and calculates totals with detailed internal breakdown.
    """
    semester_data = {}
    
    # Deduplicate marks first
    unique_marks = deduplicate_marks(marks)
    
    # Map marks by subject_id
    marks_map = {}
    for m in unique_marks:
        if m['student_id'] != student_id: continue
        sid = m['subject_id']
        if sid not in marks_map: marks_map[sid] = []
        marks_map[sid].append(m)
        
    for sub in subjects:
        sem = sub['semester']
        if sem not in semester_data:
            semester_data[sem] = {
                'subjects': [],
                'total_credits': 0, 
                'earned_credits': 0,
                'sem_gpa': 0,
                'total_points': 0
            }
            
        credits = sub.get('credits', 3) 
        if not credits: credits = 3
        
        sub_marks = marks_map.get(sub['id'], [])
        
        # Calculate Internals
        internal_stats = calculate_subject_internal_marks(sub['id'], sub_marks, sub.get('type'), {})
        
        # Determine if all entered (simplified)
        all_entered = internal_stats['mid1'] > 0 and internal_stats['mid2'] > 0
        
        # Total Score (Internals + External)
        ext_rec = next((m for m in sub_marks if m['assessment_type'] == 'External'), None)
        ext_marks = ext_rec['marks'] if ext_rec else 0
        
        if all_entered and ext_rec and published:
             total_score = internal_stats['internal_total'] + ext_marks
             passed = total_score >= 40 
             status = 'Pass' if passed else 'Fail'
             
             grade_points = 0
             if passed:
                  # Basic 10-point scale
                  percentage = total_score
                  if percentage >= 90: grade_points = 10
                  elif percentage >= 80: grade_points = 9
                  elif percentage >= 70: grade_points = 8
                  elif percentage >= 60: grade_points = 7
                  elif percentage >= 50: grade_points = 6
                  elif percentage >= 40: grade_points = 5
                  else: grade_points = 0
        else:
             total_score = None
             passed = False
             grade_points = 0
             status = 'Pending'
        
        subject_info = {
            'id': sub['id'],
            'code': sub['code'],
            'name': sub['name'],
            'credits': credits,
            'marks': round(total_score, 2) if total_score is not None else None,
            'total': round(total_score, 2) if total_score is not None else None,
            'grade_points': grade_points * credits if passed else 0,
            'passed': passed,
            'status': status,
            'is_ready': True,
            'has_marks': len(sub_marks) > 0,
            'internal': {
                'totalInternal': internal_stats['internal_total'] if all_entered else None,
                'mid1': internal_stats['mid1'],
                'mid2': internal_stats['mid2'],
                'assignment': internal_stats['assignment_avg'],
                'attendance': internal_stats['attendance_marks'],
                'allInternalMarksEntered': all_entered,
                'maxInternal': 30
            },
            'external': ext_marks if (ext_rec and published) else None
        }
        
        semester_data[sem]['subjects'].append(subject_info)
        semester_data[sem]['total_credits'] += credits
        if passed:
             semester_data[sem]['earned_credits'] += credits
             semester_data[sem]['total_points'] += (grade_points * credits)
             
    # Calculate GPA per sem
    for sem, data in semester_data.items():
        if data['total_credits'] > 0:
            data['sem_gpa'] = round(data['total_points'] / data['total_credits'], 2)
            
    return semester_data

def calculate_cgpa(semester_data):
    """
    Calculates overall CGPA from semester data.
    """
    total_points = 0
    total_credits = 0
    earned_credits = 0
    backlogs = 0
    
    for sem, data in semester_data.items():
        total_points += data['total_points']
        total_credits += data['total_credits']
        earned_credits += data['earned_credits']
        
        for sub in data['subjects']:
            if not sub['passed'] and sub['status'] == 'Fail':
                backlogs += 1
                
    cgpa = 0
    if total_credits > 0:
        cgpa = round(total_points / total_credits, 2)
        
    return {
        'cgpa': cgpa,
        'total_credits': total_credits,
        'earned_credits': earned_credits,
        'backlogs': backlogs
    }

def deduplicate_marks(marks):
    """
    Remove duplicate mark entries, keeping the latest one based on date/id.
    """
    unique_map = {}
    for m in marks:
        # Key by student, subject, assessment_type
        key = f"{m['student_id']}-{m['subject_id']}-{m['assessment_type']}"
        if m.get('assignment_number'):
            key += f"-{m['assignment_number']}"
            
        # If new or newer (by date or ID), replace
        # Assuming input is sorted by date desc, id desc (as per route logic)
        if key not in unique_map:
            unique_map[key] = m
            
    return list(unique_map.values())

def calculate_subject_internal_marks(subject_id, marks, subject_type, all_subjects_map):
    """
    Calculate internal marks structure for a specific subject.
    """
    mid1_marks = 0
    mid2_marks = 0
    assignment_marks = 0
    avg_marks = 0
    attendance_marks = 0 # Placeholder if needed
    
    # Filter for this subject
    sub_marks = [m for m in marks if m['subject_id'] == subject_id]
    
    mid1_rec = next((m for m in sub_marks if m['assessment_type'] == 'mid1'), None)
    mid2_rec = next((m for m in sub_marks if m['assessment_type'] == 'mid2'), None)
    
    if mid1_rec: mid1_marks = mid1_rec['marks']
    if mid2_rec: mid2_marks = mid2_rec['marks']
    
    # Assignments (Average of top X? Or Sum? Simplification: Average)
    assign_recs = [m for m in sub_marks if m['assessment_type'] == 'assignment']
    if assign_recs:
        total_assign = sum([m['marks'] for m in assign_recs])
        assignment_marks = total_assign / len(assign_recs) # Average
        
    # Rule: Max of (Mid1, Mid2) or Average? 
    # Standard: Average of Mids
    avg_marks = (mid1_marks + mid2_marks) / 2
    
    # Total Internals (Weightage might apply)
    # Assuming simple sum for display: Avg Mids + Avg Assignments
    total_internal = avg_marks + assignment_marks
    
    all_entered = mid1_marks > 0 and mid2_marks > 0
    
    return {
        'mid1': mid1_marks,
        'mid2': mid2_marks,
        'assignment_avg': round(assignment_marks, 2),
        'assignments': round(assignment_marks, 2), # Alias for template
        'internal_total': round(total_internal, 2),
        'totalInternal': round(total_internal, 2), # Alias for template
        'allInternalMarksEntered': all_entered,
        'maxInternal': 30, # Default max
        'attendance_marks': 0,
        'day_to_day': 0
    }
