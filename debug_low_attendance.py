import os
import sys
from dotenv import load_dotenv

# Add backend to path
# Add current dir to path to find backend
sys.path.append(os.getcwd())

from backend.database import get_supabase

load_dotenv()
supabase = get_supabase()

def debug_low_attendance():
    print("--- Debugging Low Attendance Logic ---")
    
    # 1. Get First Faculty (assuming the user is the first/main one for testing)
    # Or strict user_id from previous context if known. I'll just pick a faculty.
    f_res = supabase.table("faculty").select("*").limit(1).execute()
    if not f_res.data:
        print("No faculty found.")
        return

    faculty_id = f_res.data[0]['id']
    print(f"Faculty ID: {faculty_id}")

    # 2. Get Offerings
    off_res = supabase.table("class_offering").select("id, subject_id").eq("faculty_id", faculty_id).eq("is_active", True).execute()
    my_offerings = off_res.data or []
    subject_ids = [o['subject_id'] for o in my_offerings]
    print(f"Subject IDs: {subject_ids}")

    if not subject_ids:
        print("No subjects.")
        return

    # 3. Get Attendance
    att_res = supabase.table("attendance").select("student_id, status").in_("subject_id", subject_ids).execute()
    all_att = att_res.data or []
    print(f"Total Attendance Records: {len(all_att)}")
    
    student_stats = {}
    for a in all_att:
        sid = a['student_id']
        if sid not in student_stats: student_stats[sid] = {'total': 0, 'present': 0}
        student_stats[sid]['total'] += 1
        if str(a['status']).lower() == 'present': # Case insensitive check
             student_stats[sid]['present'] += 1
    
    low_attendance_ids = []
    
    for s, stats in student_stats.items():
        if stats['total'] > 0:
            pct = (stats['present'] / stats['total']) * 100
            if pct < 75:
                print(f"Student ID {s} has low attendance: {pct}%")
                low_attendance_ids.append(s)
    
    print(f"Low Attendance IDs: {low_attendance_ids}")
    
    if low_attendance_ids:
        # 4. Fetch Details
        st_res = supabase.table("student").select("id, name, student_id").in_("id", low_attendance_ids).execute()
        print(f"Student Fetch Result Count: {len(st_res.data) if st_res.data else 0}")
        print(f"Student Data: {st_res.data}")
        
        students_map = {st['id']: st for st in st_res.data or []}
        print(f"Map Keys: {list(students_map.keys())}")
        
        # Check matching
        for sid in low_attendance_ids:
            if sid in students_map:
                print(f"MATCH: {sid} Found.")
            else:
                print(f"MISMATCH: {sid} NOT Found in map.")
                print(f"Type of sid: {type(sid)}")
                if students_map:
                    print(f"Type of map key: {type(list(students_map.keys())[0])}")

if __name__ == "__main__":
    debug_low_attendance()
